#include "character.h"
#include <SD.h>
#include <ArduinoJson.h>

void CharacterController::begin() { _animation.begin(); }
void CharacterController::update() { _animation.update(); }

bool CharacterController::loadFromSD(const char* path) {
    if (!SD.exists(path)) return false;
    File file = SD.open(path, FILE_READ);
    if (!file) return false;
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, file);
    file.close();
    if (error) return false;
    _config.name = doc["name"] | "AI";
    _config.renderer = doc["renderer"] | "cartoon";
    _config.width = doc["resolution"][0] | 320;
    _config.height = doc["resolution"][1] | 480;
    return true;
}

void CharacterController::setAnimation(const String& name, uint32_t durationMs, bool loop) {
    if (name == "thinking") _animation.setState(AnimationState::Thinking, durationMs, loop);
    else if (name == "talking") _animation.setState(AnimationState::Talking, durationMs, loop);
    else if (name == "happy" || name == "excited" || name == "greeting") _animation.setState(AnimationState::Happy, durationMs, loop);
    else if (name == "sad") _animation.setState(AnimationState::Sad, durationMs, loop);
    else if (name == "angry") _animation.setState(AnimationState::Angry, durationMs, loop);
    else if (name == "surprised" || name == "curious") _animation.setState(AnimationState::Surprised, durationMs, loop);
    else if (name == "sleepy") _animation.setState(AnimationState::Sleepy, durationMs, loop);
    else if (name == "offline") _animation.setState(AnimationState::Offline, durationMs, loop);
    else _animation.setState(AnimationState::Idle, durationMs, loop);
}
