# This file is part of RIGEL Engine.
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
helpers/standalone_classifier.py
---------------------------------
Background cache-writer with standalone query classification.

Problem solved
~~~~~~~~~~~~~~
Caching context-dependent phrases like "can we try that again?" or "what
about the other one?" poisons the vector space: their embeddings are
semantically meaningless without the preceding conversational turns.

Solution
~~~~~~~~
After each conversation request finishes, the inference thread enqueues
the (query, answer, tag) triple via ``get_cache_writer_queue().submit()``.
A single long-lived daemon thread drains that queue, classifies each query
with the ``gemma-router`` Ollama model, and only calls
``VectorCache.store()`` when the query is classified as standalone.

Nothing on the hot inference path blocks — ``submit()`` is a
``queue.put_nowait()`` call.

Env vars
--------
STANDALONE_CLASSIFIER_MODEL    : str   (default: "gemma-router")
    Ollama model tag to use for classification.

STANDALONE_CLASSIFIER_TIMEOUT  : int   (default: 10)
    Seconds to wait for the Ollama classify call before giving up.

STANDALONE_CLASSIFIER_ENABLED  : bool  (default: true)
    Set to "false" to disable classification and fall back to the old
    always-store behaviour (useful for debugging).
"""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import urllib.error
import urllib.request
from typing import Optional

# ---------------------------------------------------------------------------
# Logger shim — mirrors the pattern used in vector_cache.py
# ---------------------------------------------------------------------------

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        try:
            from core.logger import SysLog  # noqa: PLC0415
            _logger = SysLog(
                name="CacheWriter",
                level="INFO",
                log_file="server.log",
            )
        except Exception:
            pass
    return _logger


def _log_info(msg: str) -> None:
    lg = _get_logger()
    if lg:
        lg.info(msg)
    else:
        print(msg)


def _log_warning(msg: str) -> None:
    lg = _get_logger()
    if lg:
        lg.warning(msg)
    else:
        print(f"WARNING: {msg}")


def _log_error(msg: str) -> None:
    lg = _get_logger()
    if lg:
        lg.error(msg)
    else:
        print(f"ERROR: {msg}")


# ---------------------------------------------------------------------------
# StandaloneClassifier
# ---------------------------------------------------------------------------

class StandaloneClassifier:
    """
    Classifies a query as standalone (True) or context-dependent (False)
    using the ``gemma-router`` Ollama model.

    Fail-safe: any error (timeout, Ollama unavailable, malformed JSON)
    returns ``False`` — prefer to skip caching rather than store garbage.
    """

    def __init__(self) -> None:
        self._model: str = os.getenv(
            "STANDALONE_CLASSIFIER_MODEL", "gemma-router"
        )
        self._timeout: int = int(
            os.getenv("STANDALONE_CLASSIFIER_TIMEOUT", "10")
        )
        self._ollama_url: str = os.getenv(
            "OLLAMA_HOST", "http://localhost:11434"
        ).rstrip("/") + "/api/chat"

    def classify(self, query: str) -> bool:
        """
        Return True if *query* is standalone (safe to cache), False otherwise.

        Never raises — all exceptions are caught and logged.
        """
        if not query or not query.strip():
            return False

        payload = json.dumps({
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "user", "content": query.strip()},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            self._ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            _log_warning(
                f"[CacheWriter] Classifier: Ollama unavailable ({exc}) — skipping cache"
            )
            return False
        except Exception as exc:
            _log_warning(
                f"[CacheWriter] Classifier: HTTP error ({exc}) — skipping cache"
            )
            return False

        try:
            body = json.loads(raw)
            # Ollama /api/chat wraps content under message.content
            content: str = body["message"]["content"]
        except (KeyError, json.JSONDecodeError) as exc:
            _log_warning(
                f"[CacheWriter] Classifier: Unexpected response shape ({exc}) — skipping cache"
            )
            return False

        return self._parse_classification(content)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_classification(content: str) -> bool:
        """
        Parse ``{"is_standalone": 1}`` (or 0) from the model response.

        The model is instructed to output only a JSON object, but we also
        apply a regex fallback in case there is trailing text or the closing
        brace was consumed by the stop token.
        """
        # Attempt direct JSON parse first (happy path)
        try:
            obj = json.loads(content.strip())
            return bool(obj.get("is_standalone", 0))
        except json.JSONDecodeError:
            pass

        # Regex fallback — tolerate missing closing brace (stop token eats it)
        match = re.search(r'"is_standalone"\s*:\s*([01])', content)
        if match:
            return match.group(1) == "1"

        _log_warning(
            f"[CacheWriter] Classifier: Could not parse response {content!r} — skipping cache"
        )
        return False


# ---------------------------------------------------------------------------
# CacheWriterQueue — module-level singleton
# ---------------------------------------------------------------------------

class _CacheWriterQueue:
    """
    Thread-safe queue + single daemon worker that classifies queries and
    writes to VectorCache only when the query is standalone.

    The worker thread is started lazily on the first ``submit()`` call.
    """

    _SENTINEL = object()  # used to signal worker shutdown (not currently used)

    def __init__(self) -> None:
        self._enabled: bool = (
            os.getenv("STANDALONE_CLASSIFIER_ENABLED", "true").lower() == "true"
        )
        self._q: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._classifier: Optional[StandaloneClassifier] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, query: str, answer: str, tag: str) -> None:
        """
        Enqueue a (query, answer, tag) triple for background classification
        and conditional caching.  Returns immediately — never blocks.
        """
        if not self._enabled:
            # Fall back to always-store (old behaviour)
            self._direct_store(query, answer, tag)
            return

        if not query or not answer or not tag:
            return

        self._ensure_worker_running()
        try:
            self._q.put_nowait((query, answer, tag))
        except queue.Full:
            _log_warning("[CacheWriter] Queue full — dropping cache write request")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_worker_running(self) -> None:
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._worker_loop,
                    name="RigelCacheWriter",
                    daemon=True,
                )
                self._worker_thread.start()
                _log_info("[CacheWriter] Background cache-writer thread started")

    def _get_classifier(self) -> StandaloneClassifier:
        if self._classifier is None:
            self._classifier = StandaloneClassifier()
        return self._classifier

    def _worker_loop(self) -> None:
        """Drain the queue indefinitely, classifying and storing as needed."""
        _log_info("[CacheWriter] Worker loop running")
        while True:
            try:
                item = self._q.get(timeout=5)
            except queue.Empty:
                continue

            if item is self._SENTINEL:
                _log_info("[CacheWriter] Worker received shutdown sentinel")
                self._q.task_done()
                break

            query, answer, tag = item
            try:
                self._process_item(query, answer, tag)
            except Exception as exc:
                _log_error(f"[CacheWriter] Unhandled error processing item: {exc}")
            finally:
                self._q.task_done()

    def _process_item(self, query: str, answer: str, tag: str) -> None:
        """Classify and, if standalone, write to VectorCache."""
        classifier = self._get_classifier()
        is_standalone = classifier.classify(query)

        if is_standalone:
            _log_info(
                f"[CacheWriter] STANDALONE — writing to cache  tag={tag!r}  "
                f"query={query[:80]!r}"
            )
            self._direct_store(query, answer, tag)
        else:
            _log_info(
                f"[CacheWriter] CONTEXT-DEPENDENT — skipping cache  tag={tag!r}  "
                f"query={query[:80]!r}"
            )

    @staticmethod
    def _direct_store(query: str, answer: str, tag: str) -> None:
        """Write directly to VectorCache (used in fallback / classifier=True path)."""
        try:
            from helpers.vector_cache import VectorCache  # noqa: PLC0415
            VectorCache().store(query, answer, tag)
        except Exception as exc:
            _log_warning(f"[CacheWriter] VectorCache.store failed: {exc}")


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_cache_writer_queue: Optional[_CacheWriterQueue] = None
_singleton_lock = threading.Lock()


def get_cache_writer_queue() -> _CacheWriterQueue:
    """
    Return the process-wide ``_CacheWriterQueue`` singleton.

    Thread-safe — safe to call from any thread including the inference thread.
    """
    global _cache_writer_queue
    if _cache_writer_queue is None:
        with _singleton_lock:
            if _cache_writer_queue is None:
                _cache_writer_queue = _CacheWriterQueue()
    return _cache_writer_queue
