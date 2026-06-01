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

# Rigel Voice Synthesis and Recognition

import subprocess
import os
import shutil
import threading
import queue
import time
import re
import math

try:
    import whisper
    _WHISPER_IMPORT_ERROR = None
except Exception as exc:
    whisper = None
    _WHISPER_IMPORT_ERROR = exc


class RigelSetupError(RuntimeError):
    """Raised when runtime dependencies are missing or misconfigured."""


def _build_setup_guide(message, steps):
    numbered = [f"{i}. {step}" for i, step in enumerate(steps, start=1)]
    return f"{message}\nSetup guide:\n" + "\n".join(numbered)


def _local_core_dir():
    return os.path.dirname(__file__)


def _get_optional_voice_assets_dir(kind):
    try:
        import rigel_voice_assets
    except Exception:
        return None

    if kind == "synthesis":
        return rigel_voice_assets.get_synthesis_assets_dir()
    if kind == "whisper_live":
        return rigel_voice_assets.get_whisper_live_dir()
    return None


def _resolve_synthesis_assets_dir():
    env_path = os.getenv("RIGEL_SYNTHESIS_ASSETS_DIR")
    if env_path:
        return os.path.abspath(env_path)

    local = os.path.join(_local_core_dir(), "synthesis_assets")
    if os.path.isdir(local):
        return local

    optional = _get_optional_voice_assets_dir("synthesis")
    if optional:
        return optional
    return local


def _resolve_whisper_live_dir():
    env_path = os.getenv("RIGEL_WHISPER_LIVE_DIR")
    if env_path:
        return os.path.abspath(env_path)

    local = os.path.join(_local_core_dir(), "whisper_live")
    if os.path.isdir(local):
        return local

    optional = _get_optional_voice_assets_dir("whisper_live")
    if optional:
        return optional
    return local


class Recognizer:
    def __init__(self, model="small"):
        cache_dir = os.environ.get("WHISPER_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", ".cache", "whisper"))
        cache_dir = os.path.abspath(cache_dir)
        self.model_name = model
        self.cache_dir = cache_dir
        self.models = [None, None, None]
        self.model_locks = [threading.Lock(), threading.Lock(), threading.Lock()]
        self.file_path = None
        self.output = None
        self.last_confidence = None
        self.last_text = ""
        self.last_transcribe_at = 0.0
        self._ensure_whisper_available()

    def _ensure_whisper_available(self):
        if whisper is not None:
            return

        raise RigelSetupError(
            _build_setup_guide(
                "Whisper is not available. Install speech recognition dependencies first.",
                [
                    "Install Python dependencies: pip install openai-whisper torch",
                    "Install FFmpeg on your OS and ensure ffmpeg is available in PATH",
                    f"Optional: set WHISPER_CACHE_DIR to control model cache location (current: {self.cache_dir})",
                    "Retry recognition after installing dependencies",
                ],
            ) + f"\nOriginal error: {_WHISPER_IMPORT_ERROR}"
        )

    def _get_model(self, worker_id):
        if self.models[worker_id] is None:
            try:
                self.models[worker_id] = whisper.load_model(self.model_name, download_root=self.cache_dir)
            except Exception as exc:
                raise RigelSetupError(
                    _build_setup_guide(
                        f"Failed to load Whisper model '{self.model_name}'.",
                        [
                            f"Check write permissions for WHISPER_CACHE_DIR: {self.cache_dir}",
                            "Ensure internet access is available for first-time model download",
                            "Verify ffmpeg is installed and callable from PATH",
                            "Try a smaller model first, for example model='tiny'",
                        ],
                    ) + f"\nOriginal error: {exc}"
                ) from exc
        return self.models[worker_id]

    def _extract_confidence(self, result):
        segments = result.get("segments", [])
        confidences = []

        for segment in segments:
            avg_logprob = segment.get("avg_logprob")
            if avg_logprob is not None:
                confidences.append(math.exp(avg_logprob))
                continue

            confidence = segment.get("confidence")
            if confidence is not None:
                confidences.append(confidence)

        if confidences:
            return sum(confidences) / len(confidences)

        avg_logprob = result.get("avg_logprob")
        if avg_logprob is not None:
            return math.exp(avg_logprob)

        return 0.0

    def _transcribe_worker(self, filepath, result_queue, worker_id):
        try:
            model = self._get_model(worker_id)
            with self.model_locks[worker_id]:
                result = model.transcribe(filepath)
            confidence = self._extract_confidence(result)
            result_queue.put((confidence, result.get("text", ""), worker_id))
        except Exception as e:
            print(f"Recognition worker {worker_id} failed: {e}")
            result_queue.put((0.0, "", worker_id))

    def transcribe_with_confidence(self, filepath):
        self.file_path = filepath
        # Preflight so setup/config errors surface clearly before worker threads run.
        self._get_model(0)
        result_queue = queue.Queue()
        threads = []

        for worker_id in range(3):
            thread = threading.Thread(
                target=self._transcribe_worker,
                args=(self.file_path, result_queue, worker_id),
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        best_confidence = -1.0
        best_text = ""
        while not result_queue.empty():
            confidence, text, worker_id = result_queue.get()
            print(f"\n\n\n\n\n\nRecognition worker {worker_id} returned confidence={confidence:.4f}\n\n\n\n\n\n")
            if confidence > best_confidence:
                best_confidence = confidence
                best_text = text

        self.last_confidence = max(0.0, best_confidence)
        self.last_text = best_text or ""
        self.last_transcribe_at = time.time()
        return self.last_text, self.last_confidence

    def transcribe(self, filepath):
        text, _ = self.transcribe_with_confidence(filepath)
        return text
    
class Synthesizer:
    def __init__(self, mode="chunk", voice=None):
        self.mode = mode
        self.threaded_execute_counter = None
        self.synthesis_queue = queue.Queue()
        self.playback_queue = queue.Queue()
        self.piper_path = shutil.which("piper")
        self.paplay_path = shutil.which("paplay")
        self.synthesis_assets_dir = _resolve_synthesis_assets_dir()
        voice = voice or os.getenv("VOICE", "knight")
        self.set_voice(voice)

    def _ensure_runtime_dependencies(self):
        missing_tools = []
        if not self.piper_path:
            missing_tools.append("piper")
        if not self.paplay_path:
            missing_tools.append("paplay")

        if missing_tools:
            raise RigelSetupError(
                _build_setup_guide(
                    f"Speech synthesis dependencies are missing: {', '.join(missing_tools)}.",
                    [
                        "Install Piper TTS and make sure the `piper` command is in PATH",
                        "Install PulseAudio utilities and make sure `paplay` is in PATH",
                        "Install optional voice assets package: pip install rigel-core[voice-assets]",
                        "Or point RIGEL_SYNTHESIS_ASSETS_DIR to a directory with .onnx voice models",
                        "Run synthesis again after dependencies are installed",
                    ],
                )
            )

    def set_voice(self, voice_name):
        """Switch the synthesis voice model. Falls back to 'knight' if the requested model doesn't exist."""
        candidate = os.path.join(self.synthesis_assets_dir, f"{voice_name}.onnx")
        if os.path.exists(candidate):
            self.model_path = candidate
            self.current_voice = voice_name
        else:
            fallback = os.path.join(self.synthesis_assets_dir, "knight.onnx")
            if os.path.exists(fallback):
                self.model_path = fallback
                self.current_voice = "knight"
                print(f"Voice '{voice_name}' not found, falling back to 'knight'")
            else:
                available = self.list_available_voices(self.synthesis_assets_dir)
                raise RigelSetupError(
                    _build_setup_guide(
                        f"Voice model '{voice_name}.onnx' is missing and fallback 'knight.onnx' was not found.",
                        [
                            "Install optional voice assets package: pip install rigel-core[voice-assets]",
                            "Or set RIGEL_SYNTHESIS_ASSETS_DIR to a valid asset directory",
                            "Set VOICE to one of the available model names",
                            f"Available voices detected: {', '.join(available) if available else 'none'}",
                        ],
                    )
                )

    @staticmethod
    def list_available_voices(assets_dir=None):
        """Return a list of available voice names (without .onnx extension)."""
        assets_dir = assets_dir or _resolve_synthesis_assets_dir()
        if not os.path.isdir(assets_dir):
            return []
        voices = []
        for f in os.listdir(assets_dir):
            if f.endswith(".onnx"):
                voices.append(f[:-5])  # strip .onnx
        return sorted(voices)

    def _synthesize_chunk(self, chunk, chunk_id, output_file):
        try:
            piper_process = subprocess.Popen(
                [self.piper_path, "--model", self.model_path, "--output-file", output_file],
                stdin=subprocess.PIPE,
                text=True
            )
            piper_process.communicate(input=chunk)
            
            if piper_process.returncode == 0:
                print(f"Chunk {chunk_id} synthesized successfully")
                self.playback_queue.put((chunk_id, output_file))
            else:
                print(f"Error synthesizing chunk {chunk_id}")
                self.playback_queue.put((chunk_id, None))
        except Exception as e:
            print(f"Error processing chunk {chunk_id}: {e}")
            self.playback_queue.put((chunk_id, None))

    def _play_chunks_sequentially(self, total_chunks):
        played_chunks = 0
        expected_chunk_id = 0
        waiting_chunks = {}
        
        while played_chunks < total_chunks:
            try:
                chunk_id, output_file = self.playback_queue.get(timeout=30)
                
                if output_file is None:
                    print(f"Skipping failed chunk {chunk_id}")
                    played_chunks += 1
                    expected_chunk_id += 1
                    continue

                if chunk_id != expected_chunk_id:
                    waiting_chunks[chunk_id] = output_file
                    continue
                
                self._play_and_cleanup(chunk_id, output_file)
                played_chunks += 1
                expected_chunk_id += 1
                
                while expected_chunk_id in waiting_chunks:
                    output_file = waiting_chunks.pop(expected_chunk_id)
                    self._play_and_cleanup(expected_chunk_id, output_file)
                    played_chunks += 1
                    expected_chunk_id += 1
                    
            except queue.Empty:
                print("Timeout waiting for chunk synthesis")
                break

    def _play_and_cleanup(self, chunk_id, output_file):
        try:
            print(f"Playing chunk {chunk_id}")
            result = subprocess.run([self.paplay_path, output_file], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "paplay returned a non-zero exit code")
            os.remove(output_file)
        except Exception as e:
            print(f"Error playing chunk {chunk_id}: {e}")

    def _split_text_into_chunks(self, text, max_words=80):
        if not text:
            return []
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        chunks = []
        current_words = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            words = sentence.split()
            if len(current_words) + len(words) <= max_words:
                current_words.extend(words)
            else:
                if current_words:
                    chunks.append(' '.join(current_words).strip())
                if len(words) <= max_words:
                    current_words = words
                else:
                    # split oversized sentence into smaller pieces
                    for i in range(0, len(words), max_words):
                        chunks.append(' '.join(words[i:i + max_words]).strip())
                    current_words = []
        if current_words:
            chunks.append(' '.join(current_words).strip())
        return [chunk for chunk in chunks if chunk]

    def synthesize(self, text):
        self._ensure_runtime_dependencies()

        def preprocess_for_synthesis(text):
            text = re.sub(r'^\s*\d+\.\s+.*$', '', text, flags=re.MULTILINE)

            text = re.sub(r'^\s*[-*•]\s+.*$', '', text, flags=re.MULTILINE)

            text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)

            text = re.sub(r'\(e\.?g\.?\)', 'example', text, flags=re.IGNORECASE)
            text = re.sub(r'\beg\.(?![a-zA-Z])', 'example', text, flags=re.IGNORECASE)
            text = re.sub(r'\be\.g\.(?![a-zA-Z])', 'example', text, flags=re.IGNORECASE)

            text = re.sub(r'`[^`]*`', '', text)

            text = re.sub(r'^\s*#{1,6}\s+.*$', '', text, flags=re.MULTILINE)

            text = re.sub(r'\[.*?\]\((?:https?://|www\.)[^)]+\)', ' ', text)
            text = re.sub(r'https?://\S+|www\.\S+', ' ', text, flags=re.IGNORECASE)

            emoji_pattern = re.compile(
                '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U00002600-\U000026FF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF\U00002500-\U00002BEF\U0001F700-\U0001F77F]+'
                , flags=re.UNICODE
            )
            text = emoji_pattern.sub('', text)

            # Convert em/en dashes to comma separators, e.g. "clear—your" -> "clear, your"
            text = re.sub(r'\s*[—–]\s*', ', ', text)

            # Normalize curly apostrophes
            text = text.replace('’', "'").replace('‘', "'")

            text = re.sub(r"[^A-Za-z0-9\s\.\,\?\!\:\;\-']+", ' ', text)
            text = re.sub(r'\n{2,}', '\n', text)

            lines = [line.strip() for line in text.splitlines()]

            lines = [line for line in lines if line]

            result = ' '.join(lines)

            result = re.sub(r' {2,}', ' ', result)

            return result.strip()
        text = preprocess_for_synthesis(text)
        if self.mode == "chunk":
            chunks = self._split_text_into_chunks(text)
            if not chunks:
                return

            print(f"Processing {len(chunks)} chunks with pipeline...")

            # Start playback thread first — it will block on the queue
            # until the first chunk is synthesized.
            playback_thread = threading.Thread(
                target=self._play_chunks_sequentially,
                args=(len(chunks),)
            )
            playback_thread.daemon = True
            playback_thread.start()

            # Pipeline: synthesize chunks sequentially so that chunk N+1
            # is being synthesized while chunk N is playing.
            for i, chunk in enumerate(chunks):
                output_file = f"output_chunk_{i}.wav"
                print(f"Synthesizing chunk {i+1}/{len(chunks)}: {chunk}")
                self._synthesize_chunk(chunk, i, output_file)

            # Wait for the playback thread to finish the final chunk(s).
            playback_thread.join()

            print("All chunks processed and played")
                    
        elif self.mode == "linear":
            print(f"Synthesizing: {text}")
            output_file = "output.wav"
            
            try:
                piper_process = subprocess.Popen(
                    [self.piper_path, "--model", self.model_path, "--output-file", output_file],
                    stdin=subprocess.PIPE,
                    text=True
                )
                piper_process.communicate(input=text)
                
                if piper_process.returncode == 0:
                    result = subprocess.run([self.paplay_path, output_file], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or "paplay returned a non-zero exit code")
                else:
                    print("Error synthesizing text")
            except Exception as e:
                print(f"Error processing text: {e}")



class LiveVoiceRecognizer:
    """Live voice recognition using whisper.cpp binaries (whisper-stream / whisper-cli).

    Two modes:
      - device capture: uses whisper-stream to capture from a local audio device
      - audio data: uses whisper-cli to transcribe raw audio data (WAV/PCM)
    """

    def __init__(self, model="tiny.en", capture_device=-1, threads=8, step=500, length=5000):
        self.model = model
        self.capture_device = capture_device
        self.threads = threads
        self.step = step
        self.length = length
        self.whisper_live_dir = _resolve_whisper_live_dir()
        self.whisper_lib_dir = os.path.join(self.whisper_live_dir, "lib")
        self.whisper_model_dir = os.path.join(self.whisper_live_dir, "models")
        self._stream_process = None
        self._resolve_binaries()

    def _resolve_binaries(self):
        """Locate whisper-stream and whisper-cli binaries."""
        stream_bin = os.path.join(self.whisper_live_dir, "whisper-stream")
        cli_bin = os.path.join(self.whisper_live_dir, "whisper-cli")
        missing = []
        if not os.path.exists(stream_bin):
            missing.append(stream_bin)
        if not os.path.exists(cli_bin):
            missing.append(cli_bin)
        if missing:
            raise RigelSetupError(
                _build_setup_guide(
                    "Live voice recognition binaries are missing.",
                    [
                        f"Ensure these binaries exist and are executable: {', '.join(missing)}",
                        "Install optional voice assets package: pip install rigel-core[voice-assets]",
                        "Or set RIGEL_WHISPER_LIVE_DIR to a directory containing whisper-stream and whisper-cli",
                        "Install required runtime libraries (for example SDL2 and PulseAudio)",
                        "Retry after restoring binaries",
                    ],
                )
            )
        self.stream_bin = stream_bin
        self.cli_bin = cli_bin

    def _get_model_path(self):
        """Resolve model path from model name."""
        model_file = f"ggml-{self.model}.bin"
        model_path = os.path.join(self.whisper_model_dir, model_file)
        if not os.path.exists(model_path):
            available = []
            if os.path.isdir(self.whisper_model_dir):
                for model_name in os.listdir(self.whisper_model_dir):
                    if model_name.startswith("ggml-") and model_name.endswith(".bin"):
                        available.append(model_name.replace("ggml-", "").replace(".bin", ""))
            raise RigelSetupError(
                _build_setup_guide(
                    f"Live recognition model not found: {model_path}",
                    [
                        "Install optional voice assets package: pip install rigel-core[voice-assets]",
                        "Or set RIGEL_WHISPER_LIVE_DIR to a directory containing models/",
                        f"Use one of the available models: {', '.join(sorted(available)) if available else 'none'}",
                        "Pass a valid model name to LiveVoiceRecognizer(model='tiny.en')",
                    ],
                )
            )
        return model_path

    def _env(self):
        """Return environment dict with LD_LIBRARY_PATH set for the bundled libs.

        Forces SDL2 to use PulseAudio so whisper-stream can capture from the
        host audio device even inside Docker (PULSE_SERVER must be set)."""

        env = os.environ.copy()
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{self.whisper_lib_dir}:{existing}" if existing else self.whisper_lib_dir
        env.setdefault("SDL_AUDIODRIVER", "pulseaudio")
        return env

    def start_device_capture(self, callback=None):
        """Start whisper-stream on a capture device.  Transcription lines are read
        from stdout and passed to *callback*(line: str) if given.

        Returns the Popen process handle.
        """
        if self._stream_process is not None:
            raise RuntimeError("Device capture is already running")

        model_path = self._get_model_path()
        cmd = [
            self.stream_bin,
            "-m", model_path,
            "-t", str(self.threads),
            "--step", str(self.step),
            "--length", str(self.length),
            "-c", str(self.capture_device),
        ]
        self._stream_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=self._env(),
        )

        if callback:

            def _reader():
                try:
                    for line in self._stream_process.stdout:
                        line = line.strip()
                        if line:
                            callback(line)
                except Exception:
                    pass

            t = threading.Thread(target=_reader, daemon=True)
            t.start()

        return self._stream_process

    def stop_device_capture(self, timeout=5):
        """Stop a running whisper-stream process."""
        if self._stream_process is None:
            return
        try:
            self._stream_process.terminate()
            self._stream_process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._stream_process.kill()
            self._stream_process.wait()
        finally:
            self._stream_process = None

    def is_capturing(self):
        """Return True if device capture is currently running."""
        return self._stream_process is not None and self._stream_process.poll() is None

    def transcribe_file(self, audio_file_path, extra_args=None):
        """Transcribe an audio file using whisper-cli.

        Returns the transcription string.
        """
        model_path = self._get_model_path()
        cmd = [
            self.cli_bin,
            "-m", model_path,
            "-t", str(self.threads),
            "-np",  # no extra prints, just results
            "-f", audio_file_path,
        ]
        if extra_args:
            cmd.extend(extra_args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self._env(),
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                _build_setup_guide(
                    "whisper-cli failed during transcription.",
                    [
                        "Verify whisper shared libraries are present in lib/",
                        "Verify model and audio input are valid",
                        "Check that PulseAudio/SDL2 runtime dependencies are installed",
                    ],
                ) + f"\nwhisper-cli stderr: {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def transcribe_stream(self, audio_data: bytes, extra_args=None):
        """Transcribe raw audio data (WAV bytes) via whisper-cli.

        Writes data to a temp file then calls whisper-cli.
        Returns the transcription string.
        """
        import tempfile
        suffix = ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        try:
            return self.transcribe_file(tmp_path, extra_args=extra_args)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def transcribe_stream_iter(self, audio_file_path, extra_args=None):
        """Yield transcription lines as they appear from whisper-cli (live mode).

        Uses whisper-cli without -np so each segment is printed line-by-line.
        """
        model_path = self._get_model_path()
        cmd = [
            self.cli_bin,
            "-m", model_path,
            "-t", str(self.threads),
            "-f", audio_file_path,
        ]
        if extra_args:
            cmd.extend(extra_args)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=self._env(),
        )
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    yield line
        finally:
            proc.stdout.close()
            proc.wait()

    def __del__(self):
        self.stop_device_capture()


def clone_voice(mp3_path, voice_name, language="English (U.S.)", whisper_model="small",
                sample_rate=22050, single_speaker=True, preprocess=True):
    """Run the voice cloning pipeline from an MP3 file.

    Spawns piper_mp3_dataset.py as a subprocess to:
    1. Convert MP3 to WAV segments
    2. Transcribe with Whisper
    3. Optionally preprocess for Piper training

    The resulting dataset is placed under core/synthesis_assets/VoiceCloning/dataset/{voice_name}/.

    Returns a dict with status and details.
    """
    script_path = os.path.join(
        os.path.dirname(__file__), "synthesis_assets", "VoiceCloning", "piper_mp3_dataset.py"
    )

    if not os.path.exists(script_path):
        return {"status": "error", "message": f"Voice cloning script not found at {script_path}"}

    if not os.path.exists(mp3_path):
        return {"status": "error", "message": f"MP3 file not found: {mp3_path}"}

    output_root = os.path.join(
        os.path.dirname(__file__), "synthesis_assets", "VoiceCloning", "dataset"
    )

    cmd = [
        "python", script_path,
        mp3_path,
        "--language", language,
        "--output-name", voice_name,
        "--output-root", output_root,
        "--whisper-model", whisper_model,
        "--sample-rate", str(sample_rate),
    ]
    if single_speaker:
        cmd.append("--single-speaker")
    if preprocess:
        cmd.append("--preprocess")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return {
            "status": "started",
            "message": f"Voice cloning pipeline started for '{voice_name}'",
            "pid": proc.pid,
            "output_dir": str(output_root / voice_name),
            "note": "Dataset preparation in progress. After completion, run Piper training to produce the .onnx model.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to start voice cloning: {str(e)}"}


if __name__ == "__main__":
    interpreter_location = subprocess.check_output(["which", "python"], text=True).strip()
    print(f"Python interpreter location: {interpreter_location}")
