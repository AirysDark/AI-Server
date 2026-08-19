# AI Voice Module

This directory is an **isolated voice-development area**. It is deliberately **not wired into `server.py` or the production chat stack yet**.

## Current engine

The module is being built around **Piper**, a fast local neural text-to-speech engine. Piper has downloadable voices for many languages, including English (US/UK), Spanish, French, German, Italian, Portuguese, Chinese, Japanese-adjacent language coverage in the wider ecosystem, and many others. Voice licensing must be checked per model because the voice model licenses can differ. citeturn0search0

Piper voice packages normally contain:

```text
<voice>.onnx
<voice>.onnx.json
```

and the voice files are kept outside the application code under:

```text
voice/voices/
```

Do **not** commit large model files to the application repository unless there is a deliberate reason to do so. Download the voice models separately and review each model card/license before use. citeturn0search0

## Included foundation

```text
voice/
├── voice.py       # existing lightweight Termux interface
├── config.py      # voice/model configuration
├── tts.py         # isolated TTS engine
├── voices/        # local voice models
└── README.md
```

### TTS behavior

`tts.py` provides:

- Local Piper TTS when the `piper` executable and requested voice are available
- Termux `termux-tts-speak` fallback on Android/Termux environments
- Local WAV generation for testing
- Voice discovery from the local `voice/voices/` directory
- Configurable voice selection
- No dependency on the production server

## Free/open voice source

Piper is a good starting point because it is local and has a large collection of downloadable voice models. The upstream project documents many supported languages and provides voice model files through its voice collection. citeturn0search0turn0search1

The important rule is: **free to download does not automatically mean unrestricted for every use**. Check the individual voice's model card/license before distributing or using it commercially. citeturn0search0

## Planned voice features

- Multiple selectable voices
- Automatic voice discovery
- Voice metadata and display names
- Language selection
- Speech speed control
- Pitch control where supported
- Volume control where supported
- Text-to-speech
- Speech-to-text
- Microphone recording
- Wake-word support
- Voice activity detection
- Streaming speech
- Audio playback
- Voice testing page/tool
- Android/Termux support
- Windows support
- Linux support
- Provider/backend abstraction
- Per-AI voice settings

## Testing principle

Voice development must remain isolated until the engine is stable.

```text
AI Server production code
        |
        |  NOT CONNECTED YET
        v
voice/
   |
   +-- TTS
   +-- STT
   +-- voices
   +-- audio tools
   +-- tests
```

Only after TTS/STT and voice selection are working independently should the module be connected to the main AI chat flow.
