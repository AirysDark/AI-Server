#pragma once

#include <Arduino.h>

class AiDisplay {
public:
    void begin();
    void showBoot();
    void showWiFi(const String& status);
    void showServer(const String& status);
    void showMessage(const String& sender, const String& message);
    void showError(const String& message);
};
