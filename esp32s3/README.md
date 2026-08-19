# ESP32-S3 AI Server Client

ESP32-S3 touchscreen client for AI Server.

## Purpose

The ESP32-S3 is the device/UI layer. AI Server remains responsible for AI conversations, personalities, history, images and server-side processing.

## Hardware

- ESP32-S3
- 3.5-inch SPI TFT
- Resistive touch (RTP)
- microSD

Pin assignments are centralized in `include/pins.h`.

## Build

Open this directory as a PlatformIO project and configure Wi-Fi credentials through local build flags or `include/config.h` without committing real credentials.
