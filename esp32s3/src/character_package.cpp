#include "character_package.h"
#include <SD.h>
#include <ArduinoJson.h>

bool CharacterPackageManager::begin() {
    return true;
}

bool CharacterPackageManager::load(const String& root) {
    String path = root + "/character.json";
    if (!SD.exists(path)) return false;
    File file = SD.open(path, FILE_READ);
    if (!file) return false;
    JsonDocument doc;
    const auto error = deserializeJson(doc, file);
    file.close();
    if (error) return false;

    _active.id = doc["id"] | root.substring(root.lastIndexOf('/') + 1);
    _active.name = doc["name"] | "AI";
    _active.renderer = doc["renderer"] | "cartoon";
    _active.width = doc["resolution"][0] | 320;
    _active.height = doc["resolution"][1] | 480;
    _active.root = root;
    return true;
}

bool CharacterPackageManager::scan() {
    if (!SD.exists("/characters")) return false;
    File dir = SD.open("/characters");
    if (!dir || !dir.isDirectory()) return false;
    File entry = dir.openNextFile();
    while (entry) {
        if (entry.isDirectory()) {
            String root = String(entry.name());
            entry.close();
            if (load(root)) { dir.close(); return true; }
        } else {
            entry.close();
        }
        entry = dir.openNextFile();
    }
    dir.close();
    return false;
}
