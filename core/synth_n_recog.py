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
import whisper
import threading
import queue
import time
import re
import math


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

    def _get_model(self, worker_id):
        if self.models[worker_id] is None:
            self.models[worker_id] = whisper.load_model(self.model_name, download_root=self.cache_dir)
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

    def transcribe(self, filepath):
        self.file_path = filepath
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

        return best_text
    
class Synthesizer:
    def __init__(self, mode="chunk"):
        self.mode = mode
        self.threaded_execute_counter = None
        self.synthesis_queue = queue.Queue()
        self.playback_queue = queue.Queue()
        self.piper_path = subprocess.check_output(["which", "piper"], text=True).strip()
        self.model_path = os.path.join(os.path.dirname(__file__), "synthesis_assets", "knight.onnx")

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
            subprocess.run(["paplay", output_file])
            os.remove(output_file)
        except Exception as e:
            print(f"Error playing chunk {chunk_id}: {e}")

    def _split_text_into_chunks(self, text, max_words=80):
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
        def preprocess_for_synthesis(text):
            text = re.sub(r'^\s*\d+\.\s+.*$', '', text, flags=re.MULTILINE)

            text = re.sub(r'^\s*[-*•]\s+.*$', '', text, flags=re.MULTILINE)

            text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)

            text = re.sub(r'\(e\.?g\.?\)', 'example', text, flags=re.IGNORECASE)
            text = re.sub(r'\beg\.\b', 'example', text, flags=re.IGNORECASE)
            text = re.sub(r'\be\.g\.\b', 'example', text, flags=re.IGNORECASE)

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
            
            print(f"Processing {len(chunks)} chunks...")
            
            playback_thread = threading.Thread(
                target=self._play_chunks_sequentially,
                args=(len(chunks),)
            )
            playback_thread.daemon = True
            playback_thread.start()

            synthesis_threads = []
            for i, chunk in enumerate(chunks):
                output_file = f"output_chunk_{i}.wav"
                print(f"Starting synthesis for chunk {i+1}/{len(chunks)}: {chunk}")
                
                thread = threading.Thread(
                    target=self._synthesize_chunk,
                    args=(chunk, i, output_file)
                )
                thread.daemon = True
                thread.start()
                synthesis_threads.append(thread)

            for thread in synthesis_threads:
                thread.join()
            
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
                    subprocess.run(["paplay", output_file])
                else:
                    print("Error synthesizing text")
            except Exception as e:
                print(f"Error processing text: {e}")



if __name__ == "__main__":
    interpreter_location = subprocess.check_output(["which", "python"], text=True).strip()
    print(f"Python interpreter location: {interpreter_location}")

