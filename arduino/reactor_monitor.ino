/*
 * ============================================================
 *  AR-ASSISTED NUCLEAR REACTOR SAFETY MONITORING SYSTEM
 *  Arduino Uno R4 - Sensor Data Collection & Serial Output
 * ============================================================
 *
 *  SENSOR MAPPING:
 *    DHT22         → Pin 2   → Reactor Core Temperature & Humidity
 *    MQ-2 Gas      → Pin A0  → Coolant Leak Detection
 *    UV Sensor     → Pin A1  → Radiation Level Simulation
 *    HC-SR04 Trig  → Pin 9   → Coolant Level (Ultrasonic)
 *    HC-SR04 Echo  → Pin 10  → Coolant Level (Ultrasonic)
 *    I2C LCD       → SDA/SCL → Display (0x27 address)
 *
 *  OUTPUT FORMAT (Serial @ 9600 baud):
 *    JSON string every 2 seconds
 *
 *  Author: Reactor Safety Team
 *  Version: 2.0.0
 * ============================================================
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ─── PIN DEFINITIONS ──────────────────────────────────────
#define DHT_PIN         2
#define DHT_TYPE        DHT22
#define MQ_PIN          A0
#define UV_PIN          A1
#define TRIG_PIN        9
#define ECHO_PIN        10

// ─── SAFETY THRESHOLDS ────────────────────────────────────
#define TEMP_WARNING    50.0   // °C → WARNING level
#define TEMP_CRITICAL   70.0   // °C → CRITICAL level
#define GAS_THRESHOLD   400    // Analog value → Gas Detected
#define UV_WARNING      500    // Analog value → Radiation Warning
#define UV_CRITICAL     700    // Analog value → Radiation Critical
#define COOLANT_LOW     15.0   // cm → Coolant Level Critical (too low)
#define COOLANT_HIGH    80.0   // cm → Tank ceiling (calibration)

// ─── OBJECT INSTANTIATION ─────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);  // 16 cols, 2 rows

// ─── GLOBAL STATE ─────────────────────────────────────────
unsigned long lastReadTime    = 0;
unsigned long lastLCDUpdate   = 0;
int           lcdPage         = 0;     // cycles 0-2 for 3 LCD screens
String        reactorStatus   = "SAFE";

// ─── SETUP ────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  // Sensor pins
  dht.begin();
  pinMode(TRIG_PIN,   OUTPUT);
  pinMode(ECHO_PIN,   INPUT);

  // LCD initialization
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("REACTOR MONITOR");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
  delay(2000);
  lcd.clear();

  Serial.println("{\"status\":\"BOOT\",\"message\":\"Reactor Safety System Online\"}");
}

// ─── MAIN LOOP ────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // Read & transmit sensor data every 2 seconds
  if (now - lastReadTime >= 2000) {
    lastReadTime = now;
    readAndSendData();
  }

  // Rotate LCD pages every 3 seconds
  if (now - lastLCDUpdate >= 3000) {
    lastLCDUpdate = now;
    lcdPage = (lcdPage + 1) % 3;
  }
}

// ─── READ ALL SENSORS & SEND JSON ─────────────────────────
void readAndSendData() {
  // --- DHT22: Temperature & Humidity ---
  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();

  // Fallback if sensor read fails
  if (isnan(temperature)) temperature = 0.0;
  if (isnan(humidity))    humidity    = 0.0;

  // --- MQ Gas Sensor ---
  int   gasRaw      = analogRead(MQ_PIN);
  bool  gasDetected = (gasRaw > GAS_THRESHOLD);

  // --- UV Sensor (Radiation Simulation) ---
  int   uvRaw       = analogRead(UV_PIN);
  float uvIndex     = mapFloat(uvRaw, 0, 1023, 0.0, 11.0);  // 0-11 UV index

  // --- Ultrasonic: Coolant Level ---
  float distance    = readUltrasonic();
  // Convert distance to coolant percentage (closer = more fluid)
  float coolantPct  = constrain(mapFloat(distance, COOLANT_LOW, COOLANT_HIGH, 100.0, 0.0), 0.0, 100.0);

  // --- Determine Reactor Status ---
  reactorStatus = computeStatus(temperature, gasDetected, uvRaw, coolantPct);

  // --- Update LCD ---
  updateLCD(temperature, humidity, gasDetected, uvIndex, coolantPct);

  // --- Build & Send JSON via Serial ---
  Serial.print("{");
  Serial.print("\"temperature\":");    Serial.print(temperature, 1);   Serial.print(",");
  Serial.print("\"humidity\":");       Serial.print(humidity, 1);       Serial.print(",");
  Serial.print("\"gas_raw\":");        Serial.print(gasRaw);            Serial.print(",");
  Serial.print("\"gas_detected\":");   Serial.print(gasDetected ? "true" : "false"); Serial.print(",");
  Serial.print("\"uv_raw\":");         Serial.print(uvRaw);             Serial.print(",");
  Serial.print("\"uv_index\":");       Serial.print(uvIndex, 2);        Serial.print(",");
  Serial.print("\"coolant_level\":");  Serial.print(coolantPct, 1);     Serial.print(",");
  Serial.print("\"distance_cm\":");    Serial.print(distance, 1);       Serial.print(",");
  Serial.print("\"status\":\"");       Serial.print(reactorStatus);     Serial.print("\"");
  Serial.println("}");
}

// ─── COMPUTE REACTOR STATUS ───────────────────────────────
String computeStatus(float temp, bool gas, int uvRaw, float coolant) {
  bool critical = false;
  bool warning  = false;

  if (temp >= TEMP_CRITICAL)    critical = true;
  if (uvRaw >= UV_CRITICAL)     critical = true;
  if (gas && temp >= TEMP_WARNING) critical = true;
  if (coolant < 10.0)           critical = true;

  if (temp >= TEMP_WARNING)     warning = true;
  if (gas)                      warning = true;
  if (uvRaw >= UV_WARNING)      warning = true;
  if (coolant < 30.0)           warning = true;

  if (critical) return "CRITICAL";
  if (warning)  return "WARNING";
  return "SAFE";
}

// ─── LCD DISPLAY (3 rotating pages) ──────────────────────
void updateLCD(float temp, float hum, bool gas, float uvIdx, float coolant) {
  lcd.clear();

  if (lcdPage == 0) {
    // Page 0: Temperature & Status
    lcd.setCursor(0, 0);
    lcd.print("TEMP:");
    lcd.print(temp, 1);
    lcd.print((char)223);  // degree symbol
    lcd.print("C");
    lcd.setCursor(0, 1);
    if (reactorStatus == "CRITICAL") {
      lcd.print("** CRITICAL **  ");
    } else if (reactorStatus == "WARNING") {
      lcd.print("** WARNING **   ");
    } else {
      lcd.print("STATUS: SAFE    ");
    }

  } else if (lcdPage == 1) {
    // Page 1: Gas & Radiation
    lcd.setCursor(0, 0);
    lcd.print("GAS:");
    if (gas) {
      lcd.print("LEAK! WARNING");
    } else {
      lcd.print("OK              ");
    }
    lcd.setCursor(0, 1);
    lcd.print("UV:");
    lcd.print(uvIdx, 1);
    if (uvIdx >= 9.0) {
      lcd.print(" CRITICAL");
    } else if (uvIdx >= 6.0) {
      lcd.print(" WARNING ");
    } else {
      lcd.print(" OK      ");
    }

  } else {
    // Page 2: Coolant Level
    lcd.setCursor(0, 0);
    lcd.print("COOLANT:");
    lcd.print((int)coolant);
    lcd.print("%");
    if (coolant < 10.0) {
      lcd.print(" CRITICAL");
    } else if (coolant < 30.0) {
      lcd.print(" WARNING ");
    }
    lcd.setCursor(0, 1);
    lcd.print("                ");
  }
}

// ─── ULTRASONIC READ ──────────────────────────────────────
float readUltrasonic() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // 30ms timeout
  if (duration == 0) return COOLANT_HIGH;           // Sensor timeout -> assume full
  return (duration * 0.0343) / 2.0;                 // Convert to cm
}

// ─── FLOAT MAP UTILITY ────────────────────────────────────
float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}
