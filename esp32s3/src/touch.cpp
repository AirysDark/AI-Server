#include "touch.h"
#include "pins.h"

void AiTouch::begin() {
    pinMode(Pins::RTP_CS, OUTPUT);
    digitalWrite(Pins::RTP_CS, HIGH);
}

void AiTouch::update() {
    // Touch controller implementation will be added after the display
    // controller and RTP controller are identified from the hardware.
}
