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
helpers/vector_cache.py
-----------------------
Two-tier semantic vector cache for RIGEL's Natural Language pipeline.

Two independent namespaces are used (stored as ChromaDB metadata tags):
  - "memory_agent" : caches the routing decision_text produced by the memory agent LLM.
  - "tool_agent"   : caches the full response text produced by the tool agent.

The final output / summarisation agent never reads or writes this cache.

Env vars
--------
VECTOR_CACHE_ENABLED   : "true" | "false"  (default: "true")
VECTOR_CACHE_THRESHOLD : float              (default: 0.85)  cosine similarity threshold
VECTOR_CACHE_N_RESULTS : int                (default: 1)     candidates fetched per lookup
"""

import hashlib
import os
from typing import Optional

import chromadb

_COLLECTION_NAME = "vector_cache"


_cleared_on_startup = False

class VectorCache:
    """
    Semantic cache backed by a dedicated ChromaDB collection named 'vector_cache'.

    Reuses the same PersistentClient that core.rdb.DBConn already opened so we
    never start a second DB process.
    """

    def __init__(self) -> None:
        classifier_model = os.getenv("STANDALONE_CLASSIFIER_MODEL")
        if classifier_model is None:
            self._enabled = False
        else:
            self._enabled: bool = os.getenv("VECTOR_CACHE_ENABLED", "true").lower() == "true"
            if self._enabled:
                ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                try:
                    import urllib.request
                    import json
                    req = urllib.request.Request(f"{ollama_host.rstrip('/')}/api/tags")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        available_models = [m.get("name", "") for m in data.get("models", [])]
                        
                        # Match exact name or assume :latest if no tag was specified
                        match = any(
                            m == classifier_model or m == f"{classifier_model}:latest" 
                            for m in available_models
                        )
                        if not match:
                            self._enabled = False
                            try:
                                _log_warning(f"[VectorCache] Classifier model '{classifier_model}' not found in Ollama. Disabling cache.")
                            except Exception:
                                print(f"WARNING: [VectorCache] Classifier model '{classifier_model}' not found in Ollama. Disabling cache.")
                except Exception as exc:
                    self._enabled = False
                    try:
                        _log_warning(f"[VectorCache] Failed to verify classifier model in Ollama: {exc}. Disabling cache.")
                    except Exception:
                        print(f"WARNING: [VectorCache] Failed to verify classifier model in Ollama: {exc}. Disabling cache.")
                        
        self._threshold: float = float(os.getenv("VECTOR_CACHE_THRESHOLD", "0.85"))
        self._n_results: int = int(os.getenv("VECTOR_CACHE_N_RESULTS", "1"))
        self._collection = None  # lazy — opened on first use

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_collection(self):
        """Return (and lazily create) the vector_cache ChromaDB collection."""
        if self._collection is not None:
            return self._collection

        # Prefer the shared client that rdb.DBConn already opened.
        # Import here to avoid circular imports at module load time.
        try:
            from core.rdb import DBConn  # noqa: PLC0415
            client = DBConn._client
            if client is None:
                # DBConn not yet initialised — create our own connection.
                client = chromadb.PersistentClient(
                    path="db/chroma_db",
                    settings=chromadb.config.Settings(anonymized_telemetry=False),
                )
        except Exception:
            client = chromadb.PersistentClient(
                path="db/chroma_db",
                settings=chromadb.config.Settings(anonymized_telemetry=False),
            )

        global _cleared_on_startup
        if not _cleared_on_startup:
            if os.getenv("CLEAR_VECTOR_CACHE_ON_STARTUP", "false").lower() == "true":
                try:
                    client.delete_collection(name=_COLLECTION_NAME)
                    _log_info("[VectorCache] Cleared vector cache on startup due to CLEAR_VECTOR_CACHE_ON_STARTUP")
                except Exception:
                    pass
            _cleared_on_startup = True

        self._collection = client.get_or_create_collection(name=_COLLECTION_NAME)
        return self._collection

    @staticmethod
    def _doc_id(query: str, tag: str) -> str:
        """Stable, collision-resistant document ID derived from query + tag."""
        raw = f"{tag}::{query}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _distance_to_similarity(distance: float) -> float:
        """Convert ChromaDB L2/cosine distance to a [0, 1] similarity score."""
        # ChromaDB default embedding function uses L2; distance ∈ [0, ∞).
        # Map to similarity via 1/(1+d) so it stays in [0,1].
        # If the collection was created with cosine, distance ∈ [0,2] and
        # similarity = 1 - distance/2.  We use the safe formula either way.
        return 1.0 / (1.0 + distance)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, query: str, tag: str) -> Optional[str]:
        """
        Semantic lookup.

        Parameters
        ----------
        query : str
            The text to search for (raw user query or tool task).
        tag : str
            "memory_agent" or "tool_agent" — isolates the two namespaces.

        Returns
        -------
        str | None
            Cached answer if a sufficiently similar entry exists, else None.
        """
        if not self._enabled or not query or not tag:
            return None

        try:
            collection = self._get_collection()
            results = collection.query(
                query_texts=[query],
                n_results=self._n_results,
                where={"tag": tag},
                include=["documents", "distances", "metadatas"],
            )
        except Exception as exc:
            # Never crash the calling pipeline on a cache miss.
            _log_warning(f"[VectorCache] lookup failed ({tag}): {exc}")
            return None

        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents or not distances:
            return None

        similarity = self._distance_to_similarity(distances[0])
        if similarity >= self._threshold:
            _log_info(
                f"[VectorCache] HIT  tag={tag!r}  similarity={similarity:.3f}  "
                f"query={query[:80]!r}"
            )
            # Answer is stored in metadata; document holds the query for embedding.
            if metadatas:
                return metadatas[0].get("answer", documents[0])
            return documents[0]

        _log_info(
            f"[VectorCache] MISS tag={tag!r}  similarity={similarity:.3f}  "
            f"query={query[:80]!r}"
        )
        return None

    def store(self, query: str, answer: str, tag: str) -> None:
        """
        Upsert a (query → answer) pair into the cache under the given tag.

        Parameters
        ----------
        query  : str  — the lookup key (raw user query or tool task).
        answer : str  — the value to cache (LLM response text).
        tag    : str  — "memory_agent" or "tool_agent".
        """
        if not self._enabled or not query or not answer or not tag:
            return

        # Reject obvious error/empty responses.
        stripped = answer.strip()
        if not stripped or stripped.lower().startswith("error"):
            return

        try:
            collection = self._get_collection()
            doc_id = self._doc_id(query, tag)
            collection.upsert(
                ids=[doc_id],
                # Store the QUERY as the document so embeddings match on lookup.
                # The answer is kept in metadata and retrieved on HIT.
                documents=[query],
                metadatas=[{"tag": tag, "answer": stripped, "query_preview": query[:200]}],
            )
            _log_info(
                f"[VectorCache] STORED tag={tag!r}  query={query[:80]!r}"
            )
        except Exception as exc:
            _log_warning(f"[VectorCache] store failed ({tag}): {exc}")


# ------------------------------------------------------------------
# Tiny logging shims — use the RIGEL logger if available, else print.
# ------------------------------------------------------------------

def _log_info(msg: str) -> None:
    try:
        from core.logger import SysLog  # noqa: PLC0415
        _get_logger().info(msg)
    except Exception:
        print(msg)


def _log_warning(msg: str) -> None:
    try:
        _get_logger().warning(msg)
    except Exception:
        print(f"WARNING: {msg}")


_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        from core.logger import SysLog  # noqa: PLC0415
        _logger = SysLog(name="VectorCache", level="INFO", log_file="server.log")
    return _logger
