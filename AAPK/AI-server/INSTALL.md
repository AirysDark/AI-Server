# AI Server Local AI Setup

## Termux

```bash
pkg update
pkg install python git cmake clang
pip install -r requirements.txt
```

## First boot

```bash
python startup/AI_boot.py
python server.py
```

## Architecture

- Flask web server
- Local GGUF model support
- Persistent memory
- Personality instructions
- Termux voice support

AI is designed around a small local model plus memory instead of model retraining.
