#include "ai_events.h"
#include <ArduinoJson.h>

AnimationState animationStateFromName(const String& name) {
    if (name == "thinking") return AnimationState::Thinking;
    if (name == "talking") return AnimationState::Talking;
    if (name == "happy") return AnimationState::Happy;
    if (name == "sad") return AnimationState::Sad;
    if (name == "angry") return AnimationState::Angry;
    if (name == "surprised") return AnimationState::Surprised;
    if (name == "sleepy") return AnimationState::Sleepy;
    if (name == "offline") return AnimationState::Offline;
    return AnimationState::Idle;
}

bool parseAnimationCommand(const String& json, AiAnimationCommand& command) {
    JsonDocument doc;
    if (deserializeJson(doc, json)) return false;
    command.character = doc["character"] | "ai";
    command.animation = doc["animation"] | "idle";
    command.fps = doc["fps"] | 12;
    command.durationMs = doc["duration_ms"] | 0UL;
    command.loop = doc["loop"] | true;
    return true;
}
