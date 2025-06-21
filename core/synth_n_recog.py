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

class Recognizer:
    def __init__(self, model="tiny"):
        self.model = whisper.load_model(model)
        self.file_path = None
        self.output = None

    def transcribe(self, filepath):
        self.file_path = filepath
        result = self.model.transcribe(self.file_path)
        return result["text"]
    
class Synthesizer:
    def __init__(self, mode="chunk"):
        self.mode = mode
        self.threaded_execute_counter = None
        self.synthesis_queue = queue.Queue()
        self.playback_queue = queue.Queue()
        self.piper_path = subprocess.check_output(["which", "piper"], text=True).strip()
        self.model_path = os.path.join(os.path.dirname(__file__), "synthesis_assets", "jarvis-medium.onnx")

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

    def synthesize(self, text):
        if self.mode == "chunk":
            chunks = re.split(r'[.]\s*', text.strip())
            chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
            
            print(f"Processing {len(chunks)} chunks...")
            
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
            playback_thread = threading.Thread(
                target=self._play_chunks_sequentially,
                args=(len(chunks),)
            )
            playback_thread.daemon = True
            playback_thread.start()
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

