import os
import subprocess


def speak(text):
    try:
        subprocess.run(['termux-tts-speak', text])
    except Exception:
        print(text)


def listen():
    return ''


if __name__=='__main__':
    speak('AI voice system ready')
