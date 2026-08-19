#include "cartoon_renderer.h"
#include "character_assets.h"
#include <TFT_eSPI.h>

static TFT_eSPI tft;

static const char* stateName(AnimationState state) {
    switch (state) {
        case AnimationState::Thinking: return "thinking";
        case AnimationState::Talking: return "talking";
        case AnimationState::Happy: return "happy";
        case AnimationState::Sad: return "sad";
        case AnimationState::Angry: return "angry";
        case AnimationState::Surprised: return "surprised";
        case AnimationState::Sleepy: return "sleepy";
        case AnimationState::Offline: return "offline";
        default: return "idle";
    }
}

void CartoonRenderer::begin() {
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(TFT_BLACK);
}

void CartoonRenderer::setTalkingLevel(uint8_t level) { _talkingLevel = level; }

void CartoonRenderer::render(AnimationState state, uint32_t frame) {
    const int16_t cx = tft.width() / 2;
    const int16_t cy = tft.height() / 2;
    const CharacterPose pose = characterPose(stateName(state), frame);
    const int16_t headY = cy - 55 + pose.bodyBob;
    tft.fillScreen(TFT_BLACK);

    uint16_t face = TFT_WHITE;
    if (state == AnimationState::Happy) face = TFT_GREEN;
    else if (state == AnimationState::Sad) face = TFT_CYAN;
    else if (state == AnimationState::Angry) face = TFT_RED;
    else if (state == AnimationState::Surprised) face = TFT_YELLOW;
    else if (state == AnimationState::Sleepy || state == AnimationState::Offline) face = TFT_DARKGREY;

    // Head, ears and simple shoulders give the character a more complete silhouette.
    tft.fillCircle(cx - 72, headY - 68, 30, face);
    tft.fillCircle(cx + 72, headY - 68, 30, face);
    tft.fillCircle(cx, headY, 88, face);
    tft.drawCircle(cx, headY, 88, TFT_WHITE);
    tft.fillRoundRect(cx - 105, headY + 80, 210, 120, 55, face);

    const int16_t eyeY = headY - 20 + pose.eyeOffsetY;
    if (pose.blink) {
        tft.drawFastHLine(cx - 48, eyeY, 34, TFT_BLACK);
        tft.drawFastHLine(cx + 14, eyeY, 34, TFT_BLACK);
    } else {
        const int16_t ex = pose.eyeOffsetX;
        const int16_t radius = state == AnimationState::Surprised ? 17 : 12;
        tft.fillCircle(cx - 28 + ex, eyeY, radius, TFT_BLACK);
        tft.fillCircle(cx + 28 + ex, eyeY, radius, TFT_BLACK);
        tft.fillCircle(cx - 24 + ex, eyeY - 4, 4, TFT_WHITE);
        tft.fillCircle(cx + 32 + ex, eyeY - 4, 4, TFT_WHITE);
    }

    // Eyebrows carry expression independently from the mouth.
    if (state == AnimationState::Angry) {
        tft.drawLine(cx - 50, eyeY - 28, cx - 12, eyeY - 18, TFT_BLACK);
        tft.drawLine(cx + 12, eyeY - 18, cx + 50, eyeY - 28, TFT_BLACK);
    } else if (state == AnimationState::Surprised) {
        tft.drawLine(cx - 48, eyeY - 35, cx - 10, eyeY - 40, TFT_BLACK);
        tft.drawLine(cx + 10, eyeY - 40, cx + 48, eyeY - 35, TFT_BLACK);
    }

    const int16_t mouthW = pose.mouthWidth + (_talkingLevel / 16);
    const int16_t mouthH = pose.mouthHeight;
    if (state == AnimationState::Happy) {
        tft.fillRoundRect(cx - mouthW / 2, headY + 27, mouthW, mouthH + 8, 12, TFT_BLACK);
    } else if (state == AnimationState::Sad) {
        tft.drawArc(cx, headY + 58, mouthW / 2, mouthH, 200, 340, TFT_BLACK);
    } else {
        tft.fillRoundRect(cx - mouthW / 2, headY + 35, mouthW, mouthH, 10, TFT_BLACK);
    }

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.drawString("AI", cx, tft.height() - 18, 2);
}
