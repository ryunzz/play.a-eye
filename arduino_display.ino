#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define I2C_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Buffers for the two lines
String lastTranscript  = "";
String lastTranslation = "";

void setup() {
  Serial.begin(9600);
  if (!display.begin(SSD1306_SWITCHCAPVCC, I2C_ADDRESS)) {
    Serial.println("SSD1306 allocation failed");
    while (true) delay(1000);
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextWrap(true);
  display.setTextSize(1);

  // initial welcome screen
  lastTranscript  = "Ready";
  lastTranslation = "";
  redrawDisplay();

  Serial.println("Ready");
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  // Route incoming serial by prefix
  if (line.startsWith("T:")) {
    lastTranscript = line.substring(2);
  }
  else if (line.startsWith("R:")) {
    lastTranslation = line.substring(2);
  }
  else if (line.startsWith("LANG:")) {
    lastTranscript  = "Lang: " + line.substring(5);
    lastTranslation = "";
  }
  else if (line.startsWith("CONV:START")) {
    lastTranscript  = "Conversation";
    lastTranslation = "started";
  }
  else if (line.startsWith("CONV:END")) {
    lastTranscript  = "Conversation";
    lastTranslation = "ended";
  }
  else if (line == "TEST") {
    lastTranscript  = "TEST OK";
    lastTranslation = "";
  }
  else if (line.startsWith("A:")) {
    // if you want AI replies on line 3, you could add a third buffer
    lastTranslation = "(AI) " + line.substring(2);
  }

  redrawDisplay();

  // send back ACK so Python knows it arrived
  Serial.print("ACK:");
  Serial.println(line);
}

void redrawDisplay() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println(lastTranscript);

  // leave a small gap, then draw translation
  display.setCursor(0, 16);
  display.println(lastTranslation);

  display.display();
}
