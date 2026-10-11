import subprocess
import os
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "AI.gguf")

if platform.system() == "Windows":
    possible_paths = [
        r"D:\llama.cpp\build\bin\llama-cli.exe",
        r"D:\llama.cpp\build\bin\Release\llama-cli.exe"
    ]
else:
    possible_paths = [
        "/data/data/com.termux/files/home/llama.cpp/build/bin/llama-cli"
    ]

LLAMA_BIN = next((p for p in possible_paths if os.path.exists(p)), None)


def ask_local_model(prompt):
    print("LLAMA START")
    print("MODEL:", MODEL_PATH)
    print("BIN:", LLAMA_BIN)

    if not os.path.exists(MODEL_PATH):
        return "Local model missing: " + MODEL_PATH

    if not LLAMA_BIN:
        return "llama-cli executable missing: " + str(possible_paths)

    try:
        result = subprocess.run(
            [
                LLAMA_BIN,
                "-m",
                MODEL_PATH,
                "-p",
                prompt,
                "-n",
                "64",
                "--temp",
                "0.7"
            ],
            cwd=os.path.dirname(LLAMA_BIN),
            capture_output=True,
            text=True,
            timeout=180
        )

        print("LLAMA EXIT:", result.returncode)
        print("STDERR:", result.stderr[-1000:])

        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip()

        return output

    except subprocess.TimeoutExpired:
        return "AI timed out while llama.cpp was generating."
    except Exception as e:
        return "AI error: " + repr(e)
