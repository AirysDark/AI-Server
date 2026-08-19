#pragma once

#include <Arduino.h>

namespace Pins {

// -----------------------------------------------------------------------------
// Power
// -----------------------------------------------------------------------------
// TFT VCC: 3.3V
// TFT GND: GND

// -----------------------------------------------------------------------------
// Shared SPI bus
// -----------------------------------------------------------------------------
constexpr int SPI_SCK  = 12;
constexpr int SPI_MOSI = 11;
constexpr int SPI_MISO = 13;

// -----------------------------------------------------------------------------
// TFT display
// -----------------------------------------------------------------------------
constexpr int TFT_SCK    = SPI_SCK;
constexpr int TFT_SDI    = SPI_MOSI;
constexpr int TFT_SDO    = SPI_MISO;
constexpr int TFT_CS     = 10;
constexpr int TFT_DC     = 9;
constexpr int TFT_RESET  = 8;
constexpr int TFT_LED    = 7;

// -----------------------------------------------------------------------------
// Resistive touch / RTP interface
// Board labels: T_IRQ, T_SDO, T_SDI, T_CS, T_CLK
// -----------------------------------------------------------------------------
constexpr int RTP_IRQ = 6;
constexpr int RTP_SDO = SPI_MISO;
constexpr int RTP_SDI = SPI_MOSI;
constexpr int RTP_CS  = 5;
constexpr int RTP_CLK = SPI_SCK;

// -----------------------------------------------------------------------------
// Capacitive touch / CTP interface
// Board labels: INT, NC, SDA, RST, SCL
// -----------------------------------------------------------------------------
constexpr int CTP_INT = 15;
constexpr int CTP_NC  = -1;
constexpr int CTP_SDA = 16;
constexpr int CTP_RST = 17;
constexpr int CTP_SCL = 18;

// -----------------------------------------------------------------------------
// SD card
// Uses the same SPI SCK/MOSI/MISO bus as the TFT.
// Only chip select is separate.
// -----------------------------------------------------------------------------
constexpr int SD_SCK  = SPI_SCK;
constexpr int SD_MOSI = SPI_MOSI;
constexpr int SD_MISO = SPI_MISO;
constexpr int SD_CS   = 14;

// -----------------------------------------------------------------------------
// Convenience aliases matching common library terminology
// -----------------------------------------------------------------------------
constexpr int DISPLAY_SCK  = TFT_SCK;
constexpr int DISPLAY_MOSI = TFT_SDI;
constexpr int DISPLAY_MISO = TFT_SDO;
constexpr int DISPLAY_CS   = TFT_CS;
constexpr int DISPLAY_DC   = TFT_DC;
constexpr int DISPLAY_RST  = TFT_RESET;
constexpr int BACKLIGHT    = TFT_LED;

} // namespace Pins
