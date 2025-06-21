# RIGEL Engine Changelog

All notable changes to RIGEL Engine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.X] - 2025-06-21

### Added
- **Voice Synthesis & Recognition**: Complete local voice capabilities
  - Text-to-Speech (TTS) using Piper with Jarvis voice model
  - Speech-to-Text (STT) using OpenAI Whisper
  - Chunked streaming audio for better performance
  - Multiple synthesis modes: chunk and linear
  - Multiple Whisper model sizes: tiny, base, small, medium, large
  - D-Bus endpoints: `SynthesizeText` and `RecognizeAudio`
  - Voice components in `core/synth_n_recog.py`
  - Voice test suite in `test_voice_features.py`

- **Enhanced D-Bus Server**: 
  - Voice synthesis endpoint with mode selection
  - Audio recognition endpoint with model selection
  - Improved error handling for voice components
  - License information endpoint for AGPL compliance

- **Documentation Updates**:
  - Comprehensive voice features documentation
  - Installation guide for voice dependencies
  - Voice API reference and examples
  - Updated project structure with voice assets
  - Enhanced demo client with voice testing

### Enhanced
- **Demo Client**: Extended `demo_client.py` with voice feature testing
- **Requirements**: Added voice dependencies (whisper, torch, torchaudio)
- **CI/CD**: Updated health check workflow to test voice module imports
- **Repository Topics**: Added voice-related GitHub topics

### Dependencies
- `openai-whisper==20240930` - Speech recognition
- `torch==2.5.1` - PyTorch for Whisper
- `torchvision==0.20.1` - PyTorch vision components
- `torchaudio==2.5.1` - PyTorch audio processing

### System Requirements
- **Piper TTS**: Required for voice synthesis
- **PulseAudio**: Required for audio playback
- **FFmpeg**: Required for audio processing (CI/CD)

### Voice Models
- **Piper**: `jarvis-medium.onnx` - High-quality TTS voice model
- **Whisper**: Auto-downloaded on first use (tiny to large models)

### Breaking Changes
- None in this release

### Security
- Voice operations respect system permissions
- Audio files processed locally (no cloud dependencies)
- Secure file handling for audio transcription

### Known Issues
- Voice components require system audio setup
- Large Whisper models may require significant disk space
- Voice synthesis requires Piper binary in PATH

---

## Previous Releases

### [4.0.0] - 2025-01-XX
- Initial release with Ollama and Groq backends
- D-Bus server implementation
- MCP (Model Context Protocol) tools support
- Memory management and conversation threads
- RAG support with ChromaDB
- Basic inference and thinking capabilities

---

**Note**: RIGEL Engine is currently in developer beta. Features and APIs may change.
