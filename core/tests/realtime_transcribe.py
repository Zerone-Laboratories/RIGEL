#!/usr/bin/env python3
"""
Real-time audio transcription using Whisper.

Records audio continuously in fixed-duration chunks, transcribes each chunk
in a background thread using the project's Recognizer, and prints results in
order — giving near real-time speech-to-text output.

Usage:
    python tests/realtime_transcribe.py
    python tests/realtime_transcribe.py --model tiny --chunk-duration 3
    python tests/realtime_transcribe.py --list-devices
"""

import sounddevice as sd
import numpy as np
import wave
import tempfile
import threading
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synth_n_recog import Recognizer


class RealtimeTranscriber:
    """Records audio and transcribes in near real-time using Whisper."""

    def __init__(self, model="tiny", sample_rate=16000, chunk_duration=3):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.blocksize = int(sample_rate * chunk_duration)

        print(f"Loading Whisper model '{model}'...")
        self.recognizer = Recognizer(model=model)

        self.results = {}
        self.results_lock = threading.Lock()
        self.next_chunk_id = 0
        self.next_to_print = 0
        self.chunk_id_lock = threading.Lock()
        self.running = False
        self.active_transcriptions = 0
        self.active_lock = threading.Lock()

    def _save_audio(self, audio_data):
        """Save a numpy audio array to a temporary WAV file."""
        tmpfile = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmpfile.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(self.sample_rate)
            wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        return tmpfile.name

    def _transcribe_chunk(self, chunk_id, audio_data):
        """Transcribe a single audio chunk and store the result."""
        with self.active_lock:
            self.active_transcriptions += 1

        filepath = self._save_audio(audio_data)
        try:
            text = self.recognizer.transcribe(filepath)
            with self.results_lock:
                self.results[chunk_id] = text.strip()
        except Exception as e:
            print(f"\n[error] chunk {chunk_id}: {e}", file=sys.stderr)
            with self.results_lock:
                self.results[chunk_id] = ""
        finally:
            os.unlink(filepath)
            with self.active_lock:
                self.active_transcriptions -= 1

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each complete audio block."""
        if status:
            print(f"\n[audio] {status}", file=sys.stderr)

        with self.chunk_id_lock:
            chunk_id = self.next_chunk_id
            self.next_chunk_id += 1

        audio_copy = indata.copy().flatten()
        thread = threading.Thread(
            target=self._transcribe_chunk, args=(chunk_id, audio_copy), daemon=True
        )
        thread.start()

    def start(self):
        """Start real-time audio capture and transcription."""
        self.running = True

        print(f"\nReal-time transcription active")
        print(f"  Model: {self.recognizer.model_name}")
        print(f"  Sample rate: {self.sample_rate} Hz")
        print(f"  Chunk duration: {self.chunk_duration}s")
        print(f"  Press Ctrl+C to stop.\n")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=self._audio_callback,
                blocksize=self.blocksize,
                dtype=np.float32,
            ):
                while self.running:
                    self._print_ready_results()
                    time.sleep(0.2)

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            # Drain remaining results
            print("\nFinishing pending transcriptions...", file=sys.stderr)
            while True:
                self._print_ready_results()
                with self.active_lock:
                    pending = self.active_transcriptions
                with self.results_lock:
                    remaining = len(self.results)
                if pending == 0 and remaining == 0:
                    break
                time.sleep(0.3)
            print("\nTranscription stopped.")

    def _print_ready_results(self):
        """Print completed results in chunk order."""
        with self.results_lock:
            while self.next_to_print in self.results:
                text = self.results.pop(self.next_to_print)
                if text:
                    print(f"{text} ", end="", flush=True)
                self.next_to_print += 1


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time audio transcription using Whisper"
    )
    parser.add_argument(
        "--model", default="tiny",
        help="Whisper model name: tiny, base, small, medium, large (default: tiny)"
    )
    parser.add_argument(
        "--chunk-duration", type=float, default=3.0,
        help="Audio chunk duration in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--sample-rate", type=int, default=16000,
        help="Audio sample rate in Hz (default: 16000)"
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="List available audio input devices and exit"
    )

    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    transcriber = RealtimeTranscriber(
        model=args.model,
        sample_rate=args.sample_rate,
        chunk_duration=args.chunk_duration,
    )
    transcriber.start()


if __name__ == "__main__":
    main()
