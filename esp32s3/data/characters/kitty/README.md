# Kitty character package

Copy this directory to the ESP32-S3 SD card under `/characters/kitty/`.

Animation directories can contain numbered BMP frames:

- `idle/frame_0000.bmp`
- `idle/frame_0001.bmp`
- `talking/frame_0000.bmp`
- `happy/frame_0000.bmp`
- `thinking/frame_0000.bmp`

The frame player uses 24-bit BMP files and advances them according to the selected FPS. Missing frame directories automatically fall back to the procedural renderer.
