# Piper Engine

This directory contains the isolated Piper TTS engine adapter for AI Server's voice development work.

Piper was selected as the first engine because it is local, offline after model download, lightweight compared with large neural speech models, and supports Linux, Windows, ARM64/Raspberry Pi and Python. The current Piper ecosystem is distributed through `piper-tts` and provides downloadable voice models. See the upstream project before redistributing voice models.

Upstream:
https://github.com/OHF-Voice/piper1-gpl

## Why Piper first

VoxCPM is more capable for expressive synthesis and voice cloning, but Piper is substantially easier to run across the hardware targets used by this project. Piper can run locally without a cloud API and supports many pre-trained voices.

## Installation

```bash
python -m pip install piper-tts
```

The engine wrapper in this directory does not automatically wire itself into the main AI Server.

## Voices

Piper voices normally consist of a model and its JSON configuration, for example:

```text
en_US-lessac-medium.onnx
en_US-lessac-medium.onnx.json
```

Voice licenses vary. Check the model card/license for each voice before redistribution.

## Isolation

This engine is intentionally isolated under `voice/engine/`. It is not imported by `server.py` or the production chat path yet.
