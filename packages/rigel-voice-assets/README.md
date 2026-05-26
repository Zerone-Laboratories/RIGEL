# rigel-voice-assets

Optional companion package for `rigel-engine-core` voice features.

This package provides a standard location contract for voice assets so `rigel-engine-core` can discover them without changing Docker workflows.

## Asset layout

Default root:

`~/.cache/rigel/voice-assets`

Expected directories:

- `synthesis_assets/` (Piper `.onnx` voice files)
- `whisper_live/` (`whisper-stream`, `whisper-cli`, `lib/`, `models/`)

Override with env vars:

- `RIGEL_VOICE_ASSETS_DIR`
- `RIGEL_SYNTHESIS_ASSETS_DIR`
- `RIGEL_WHISPER_LIVE_DIR`

## Guide

Run:

```bash
python -m rigel_voice_assets
```

or:

```bash
rigel-voice-assets-guide
```
