#include "cartoon_renderer.h"
#include <TFT_eSPI.h>

static TFT_eSPI tft;

void CartoonRenderer::begin() {
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(TFT_BLACK);
}

void CartoonRenderer::setTalkingLevel(uint8_t level) { _talkingLevel = level; }

void CartoonRenderer::render(AnimationState state, uint32_t frame) {
    const int16_t cx = tft.width() / 2;
    const int16_t cy = tft.height() / 2;
    const bool blink = ((frame / 18) % 70) == 0;
    const bool talking = state == AnimationState::Talking;
    const int16_t bob = ((frame / 5) % 6) - 3;
    const int16_t headY = cy - 55 + bob;
    tft.fillScreen(TFT_BLACK);

    uint16_t face = TFT_WHITE;
    if (state == AnimationState::Happy) face = TFT_GREEN;
    if (state == AnimationState::Sad) face = TFT_CYAN;
    if (state == AnimationState::Angry) face = TFT_RED;
    if (state == AnimationState::Surprised) face = TFT_YELLOW;
    if (state == AnimationState::Sleepy || state == AnimationState::Offline) face = TFT_DARKGREY;

    tft.fillCircle(cx, headY, 88, face);
    tft.drawCircle(cx, headY, 88, TFT_WHITE);
    const int16_t eyeY = headY - 20;
    if (blink || state == AnimationState::Sleepy) {
        tft.drawFastHLine(cx - 42, eyeY, 28, TFT_BLACK);
        tft.drawFastHLine(cx + 14, eyeY, 28, TFT_BLACK);
    } else {
        tft.fillCircle(cx - 28, eyeY, 12, TFT_BLACK);
        tft.fillCircle(cx + 28, eyeY, 12, TFT_BLACK);
    }

    if (talking) {
        const int16_t mouth = 10 + (_talkingLevel / 24) + ((frame / 4) % 12);
        tft.fillRoundRect(cx - 24, headY + 30, 48, mouth, 12, TFT_BLACK);
    } else if (state == AnimationState::Happy) {
        tft.drawArc(cx, headY + 18, 35, 20, 20, 160, TFT_BLACK);
    } else if (state == AnimationState::Sad) {
        tft.drawArc(cx, headY + 50, 30, 18, 200, 340, TFT_BLACK);
    } else {
        tft.fillRoundRect(cx - 12, headY + 38, 24, 8, 4, TFT_BLACK);
    }

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.drawString("AI", cx, cy + 95, 2);
}
