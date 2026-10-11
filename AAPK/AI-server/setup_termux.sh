#!/data/data/com.termux/files/usr/bin/bash

set -e

echo "Installing AI dependencies..."

pkg update -y
pkg install -y python git cmake clang

pip install -r requirements.txt

mkdir -p model memory

if [ ! -f memory/chats.json ]; then
 echo '[]' > memory/chats.json
fi

if [ ! -f memory/facts.json ]; then
 echo '{"facts":[],"preferences":[]}' > memory/facts.json
fi

echo "AI setup complete"
echo "Place your GGUF model in model/AI.gguf"
