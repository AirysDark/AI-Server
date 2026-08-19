#include "character_library.h"
#include <string.h>

static const CharacterDefinition characters[] = {
    {"ai", "AI", "cartoon", 320, 480},
    {"kitty", "Kitty", "cartoon", 320, 480},
    {"3d", "AI 3D", "3d", 320, 480}
};

const CharacterDefinition* findCharacter(const String& id) {
    for (const auto& character : characters) {
        if (id.equalsIgnoreCase(character.id)) return &character;
    }
    return &characters[0];
}
