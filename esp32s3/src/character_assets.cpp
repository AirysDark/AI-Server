#include "character_assets.h"
#include <string.h>

CharacterPose characterPose(const char* animation, uint32_t frame) {
    CharacterPose p{0, 0, 32, 10, static_cast<int16_t>((frame / 6) % 5) - 2, 0};
    const uint32_t blinkCycle = frame % 180;
    p.blink = (blinkCycle >= 174) ? 1 : 0;

    if (!strcmp(animation, "thinking")) { p.eyeOffsetX = 8; p.mouthWidth = 20; p.mouthHeight = 7; }
    else if (!strcmp(animation, "happy")) { p.mouthWidth = 42; p.mouthHeight = 16; p.bodyBob += 2; }
    else if (!strcmp(animation, "sad")) { p.mouthWidth = 28; p.mouthHeight = 14; p.bodyBob -= 1; }
    else if (!strcmp(animation, "angry")) { p.eyeOffsetY = -4; p.mouthWidth = 26; p.mouthHeight = 8; }
    else if (!strcmp(animation, "surprised")) { p.mouthWidth = 18; p.mouthHeight = 25; }
    else if (!strcmp(animation, "sleepy")) { p.blink = 1; p.eyeOffsetY = 5; }
    else if (!strcmp(animation, "offline")) { p.blink = 1; p.mouthWidth = 20; }
    else if (!strcmp(animation, "talking")) {
        p.mouthWidth = 24 + ((frame / 3) % 22);
        p.mouthHeight = 8 + ((frame / 4) % 15);
    }
    return p;
}
