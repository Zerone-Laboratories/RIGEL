#!/usr/bin/env python3
"""Convert MP3 files into a Piper training dataset.

This script converts one or more input MP3 files into WAV segments, transcribes
those segments with Whisper, writes a Piper-compatible metadata.csv file, and
optionally preprocesses the dataset for Piper training.

Example:
  python piper_mp3_dataset.py data/source_audio.mp3 \
      --language "English (U.S.)" \
      --output-name Test \
      --preprocess
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


LANGUAGES: Dict[str, str] = {
    "Català": "ca",
    "Dansk": "da",
    "Deutsch": "de",
    "Ελληνικά": "grc",
    "English (British)": "en",
    "English (U.S.)": "en-us",
    "Español": "es",
    "Español (latinoamericano)": "es-419",
    "Suomi": "fi",
    "Français": "fr",
    "Magyar": "hu",
    "Icelandic": "is",
    "Italiano": "it",
    "ქართული": "ka",
    "қазақша": "kk",
    "Lëtzebuergesch": "lb",
    "नेपाली": "ne",
    "Nederlands": "nl",
    "Norsk": "nb",
    "Polski": "pl",
    "Português (Brasil)": "pt-br",
    "Română": "ro",
    "Русский": "ru",
    "Српски": "sr",
    "Svenska": "sv",
    "Kiswahili": "sw",
    "Türkçe": "tr",
    "украї́нська": "uk",
    "Tiếng Việt": "vi",
    "简体中文": "zh",
}


def find_notebook_root(start_path: Optional[Path] = None) -> Path:
    if start_path is None:
        start_path = Path.cwd()

    for candidate in [start_path] + list(start_path.parents):
        if (candidate / 'piper' / 'src' / 'python').exists():
            return candidate

    raise FileNotFoundError(
        'Unable to locate the notebook root. Place the Piper repository under <root>/piper.'
    )


def check_ffmpeg() -> None:
    if subprocess.run(['which', 'ffmpeg'], capture_output=True).returncode != 0:
        raise RuntimeError('ffmpeg is required by pydub but was not found on PATH.')


def build_monotonic_align(piper_src: Path) -> None:
    monotonic_dir = piper_src / 'piper_train' / 'vits' / 'monotonic_align'
    if not monotonic_dir.exists():
        raise FileNotFoundError(f'Missing monotonic_align directory at {monotonic_dir}')

    so_files = list((monotonic_dir / 'monotonic_align').glob('core*.so'))
    if so_files:
        return

    print('Building monotonic_align extension...')
    subprocess.run(['bash', str(piper_src / 'build_monotonic_align.sh')], check=True)
    so_files = list((monotonic_dir / 'monotonic_align').glob('core*.so'))
    if not so_files:
        raise RuntimeError('Failed to build monotonic_align extension.')
    print('Built monotonic_align extension:', [str(p.name) for p in so_files])


def convert_mp3_to_wavs(mp3_paths: List[Path], output_dir: Path, sample_rate: int) -> List[Path]:
    from pydub import AudioSegment
    from pydub.silence import split_on_silence

    output_dir.mkdir(parents=True, exist_ok=True)
    segments: List[Path] = []
    split_ms = 15000

    for mp3_path in mp3_paths:
        print('Converting', mp3_path)
        audio = AudioSegment.from_file(mp3_path)
        audio = audio.set_frame_rate(sample_rate).set_channels(1).set_sample_width(2)

        chunks = split_on_silence(
            audio,
            min_silence_len=700,
            silence_thresh=audio.dBFS - 14,
            keep_silence=250,
        )

        if 1 < len(chunks) <= 20:
            for idx, chunk in enumerate(chunks, start=1):
                chunk_path = output_dir / f'{mp3_path.stem}_{idx:03d}.wav'
                chunk.export(chunk_path, format='wav')
                segments.append(chunk_path)
        else:
            for idx, start in enumerate(range(0, len(audio), split_ms), start=1):
                chunk = audio[start:start + split_ms]
                chunk_path = output_dir / f'{mp3_path.stem}_{idx:03d}.wav'
                chunk.export(chunk_path, format='wav')
                segments.append(chunk_path)

    if not segments:
        raise RuntimeError('No WAV segments were created from the source mp3 files.')

    print(f'Created {len(segments)} WAV segment(s) in {output_dir}')
    return segments


def transcribe_wavs(wav_paths: List[Path], metadata_path: Path, language_code: str, whisper_model_name: str) -> None:
    import whisper

    print('Loading Whisper model:', whisper_model_name)
    whisper_model = whisper.load_model(whisper_model_name)

    with metadata_path.open('w', encoding='utf-8', newline='') as metadata_file:
        writer = csv.writer(metadata_file, delimiter='|', quoting=csv.QUOTE_MINIMAL)
        for wav_path in wav_paths:
            print('Transcribing', wav_path.name)
            result = whisper_model.transcribe(str(wav_path), language='en' if language_code.startswith('en') else None)
            text = result['text'].strip()
            if not text:
                raise RuntimeError(f'Whisper returned empty transcription for {wav_path.name}')
            writer.writerow([f'wavs/{wav_path.name}', text])

    print('Generated metadata.csv with', len(wav_paths), 'entries.')


def preprocess_dataset(
    piper_src: Path,
    dataset_dir: Path,
    output_dir: Path,
    language_code: str,
    dataset_format: str,
    sample_rate: int,
    single_speaker: bool,
    max_workers: int = 1,
) -> None:
    build_monotonic_align(piper_src)

    flags = ['--single-speaker'] if single_speaker else []

    cmd = [
        sys.executable,
        '-m',
        'piper_train.preprocess',
        '--language', language_code,
        '--input-dir', str(dataset_dir),
        '--output-dir', str(output_dir),
        '--dataset-format', dataset_format,
        '--sample-rate', str(sample_rate),
        '--max-workers', str(max_workers),
    ]
    cmd.extend(flags)

    print('Running preprocess command:')
    print(' '.join(cmd))
    subprocess.run(cmd, cwd=str(piper_src), check=True)
    print('Preprocess finished. Output written to:', output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Convert MP3 files into a Piper dataset and optionally preprocess it.'
    )
    parser.add_argument('mp3_files', nargs='+', type=Path, help='Input MP3 file(s)')
    parser.add_argument('--root', type=Path, default=None,
                        help='Root directory containing the local Piper repository')
    parser.add_argument('--language', type=str, default='English (U.S.)', choices=list(LANGUAGES),
                        help='Language of the audio dataset')
    parser.add_argument('--output-name', type=str, default='Test', help='Model / output folder name')
    parser.add_argument('--output-root', type=Path, default=None,
                        help='Root directory for generated dataset and outputs')
    parser.add_argument('--dataset-format', type=str, default='ljspeech', choices=['ljspeech', 'mycroft'],
                        help='Dataset format for Piper preprocessing')
    parser.add_argument('--single-speaker', action='store_true', default=False,
                        help='Mark dataset as single-speaker')
    parser.add_argument('--sample-rate', type=int, default=22050, choices=[16000, 22050],
                        help='Sample rate for output WAV files and preprocessing')
    parser.add_argument('--whisper-model', type=str, default='small',
                        help='Whisper model name used for transcription')
    parser.add_argument('--preprocess', action='store_true', default=False,
                        help='Run Piper preprocess after creating metadata.csv')
    parser.add_argument('--resample', action='store_true', default=False,
                        help='Resample WAV files after conversion using resample.py')
    parser.add_argument('--max-workers', type=int, default=1,
                        help='Number of workers for Piper preprocessing')
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    for mp3_path in args.mp3_files:
        if not mp3_path.exists():
            print('Input MP3 file not found:', mp3_path, file=sys.stderr)
            return 1

    root = args.root or find_notebook_root()
    print('Notebook root:', root)

    piper_src = root / 'piper' / 'src' / 'python'
    if not piper_src.exists():
        raise FileNotFoundError(f'Local Piper repo not found at {piper_src}')

    check_ffmpeg()

    dataset_root = args.output_root or root / 'dataset'
    wavs_dir = dataset_root / 'wavs'
    wavs_dir.mkdir(parents=True, exist_ok=True)

    segments = convert_mp3_to_wavs(args.mp3_files, wavs_dir, args.sample_rate)

    if args.resample:
        resample_script = root / 'resample.py'
        if not resample_script.exists():
            raise FileNotFoundError(f'Expected resample.py at {resample_script}')
        resampled_dir = dataset_root / 'wavs_resampled'
        print('Resampling WAV files into', resampled_dir)
        subprocess.run([
            sys.executable,
            str(resample_script),
            '--input_dir', str(wavs_dir),
            '--output_dir', str(resampled_dir),
            '--output_sr', str(args.sample_rate),
            '--file_ext', 'wav',
        ], check=True)
        for old_file in wavs_dir.glob('*.wav'):
            old_file.unlink()
        resampled_dir.rename(wavs_dir)
        print('Resampled WAV files saved to', wavs_dir)

    metadata_path = dataset_root / 'metadata.csv'
    transcribe_wavs(segments, metadata_path, LANGUAGES[args.language], args.whisper_model)

    if args.preprocess:
        output_dir = (args.output_root or root / 'piper_output') / args.output_name
        output_dir.mkdir(parents=True, exist_ok=True)
        preprocess_dataset(
            piper_src=piper_src,
            dataset_dir=dataset_root,
            output_dir=output_dir,
            language_code=LANGUAGES[args.language],
            dataset_format=args.dataset_format,
            sample_rate=args.sample_rate,
            single_speaker=args.single_speaker,
            max_workers=args.max_workers,
        )

    print('Done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
