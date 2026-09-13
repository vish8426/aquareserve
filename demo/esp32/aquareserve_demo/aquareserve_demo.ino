/*
 * AquaReserve tabletop demonstrator - ESP32 firmware
 * ---------------------------------------------------
 * Reads a capacitive soil-moisture sensor, asks the AquaReserve demo bridge what to do and runs a small pump for the commanded time.
 * If WiFi or the bridge is unavailable it falls back to a local soil-moisture threshold (Tier 1), so the experiemental settup always does something sensible.
 *
 * Hardware (see docs/DEMO_BUILD_GUIDE.md):
 *   - Capacitive soil-moisture sensor  -> 3V3, GND, analog out to SOIL_PIN (GPIO 34, input-only)
 *   - Logic-level MOSFET module gate    -> PUMP_PIN (GPIO 26); pump powered from the 5-6 V rail,
 *     NOT from a GPIO pin (a pump draws far more current than a pin can supply)
 *   - Pump sits in the reserve jar, tube runs to the irrigated half of the soil tray
 *
 * Libraries (Arduino Library Manager): "ArduinoJson" by Benoit Blanchon.
 * WiFi and HTTPClient ship with the ESP32 core.
 *
 * SAFETY: low-voltage DC only.
 * Keep water away from mains and keep the board and battery dry.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- configure these ------------------------------------------------------
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
// The machine running scripts/demo_bridge.py, e.g. "http://192.168.1.50:8500/demo/decide".
const char* BRIDGE_URL = "http://192.168.1.50:8500/demo/decide";
const char* ZONE = "tray-1";

// input-only ADC pin
// drives the MOSFET gate
// ADC reading in dry mix (calibrate once)
// ADC reading in wet mix (calibrate once)
const int   SOIL_PIN = 4;     
const int   PUMP_PIN = 5;     
const int   RAW_DRY  = 2200;   
const int   RAW_WET  = 2100;   

// check each minute (shorten for a live demo)
// offline fallback threshold
// offline fallback pump pulse
const unsigned long INTERVAL_MS = 3000; 
const float LOCAL_TRIGGER_PCT   = 35.0;  
const int   LOCAL_PULSE_MS      = 2000;  

// ---------------------------------------------------------------------------
float readMoisturePct() {
  long sum = 0;
  for (int i = 0; i < 16; i++) { sum += analogRead(SOIL_PIN); delay(5); }
  int raw = sum / 16;
  Serial.printf("raw=%d\n", raw);
  float pct = 100.0 * (float)(RAW_DRY - raw) / (float)(RAW_DRY - RAW_WET);
  if (pct < 0) pct = 0; if (pct > 100) pct = 100;
  return pct;
}

void runPump(int ms) {
  if (ms <= 0) return;
  digitalWrite(PUMP_PIN, HIGH);
  delay(ms);
  digitalWrite(PUMP_PIN, LOW);
}

// Ask the bridge; returns pump milliseconds or -1 if the request failed.
int askBridge(float moisturePct) {
  if (WiFi.status() != WL_CONNECTED) return -1;
  HTTPClient http;
  http.begin(BRIDGE_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<192> req;
  req["zone"] = ZONE;
  req["moisture_pct"] = moisturePct;
  // set true during a sensitive growth window
  req["critical_stage"] = false;   
  String body;
  serializeJson(req, body);

  int code = http.POST(body);
  int pump_ms = -1;
  if (code == 200) {
    StaticJsonDocument<256> resp;
    if (!deserializeJson(resp, http.getString())) {
      pump_ms = resp["pump_ms"] | 0;
      Serial.printf("bridge: pump_ms=%d reserve=%.1f%% (%s)\n", 
                    pump_ms, (float)(resp["reserve_pct"] | 0.0),
                    (const char*)(resp["reason"] | ""));
    }
  } else {
    Serial.printf("bridge HTTP %d - falling back to local logic\n", code);
  }
  http.end();
  return pump_ms;
}

void setup() {
  Serial.begin(115200);
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("connecting WiFi");
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) { delay(500); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected" : " offline (local mode)");
}

void loop() {
  float moisture = readMoisturePct();
  Serial.printf("soil moisture: %.1f%%\n", moisture);

  // Tier 2: software-in-the-loop
  // Tier 1 fallback: local threshold
  int pump_ms = askBridge(moisture);          
  if (pump_ms < 0) {                           
    pump_ms = (moisture < LOCAL_TRIGGER_PCT) ? LOCAL_PULSE_MS : 0;
    if (pump_ms) Serial.println("local: watering (below threshold)");
  }

  runPump(pump_ms);
  delay(INTERVAL_MS);
}
