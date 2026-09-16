#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <QMC5883LCompass.h>
#include <math.h>

// ============================================================
// SEAFLOOR INTELLIGENCE
// ESP32 REAL HARDWARE FIRMWARE
// ============================================================

// -------------------- PINS --------------------

#define ONE_WIRE_PIN    4

#define TRIG_PIN        32
#define ECHO_PIN        33

#define INDUCTIVE_PIN   27

#define BUTTON_PIN      13
#define LED_PIN         2
#define BUZZER_PIN      19

// -------------------- OBJECTS --------------------

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature temperatureSensor(&oneWire);

QMC5883LCompass compass;

// -------------------- SETTINGS --------------------

const unsigned long SEND_INTERVAL = 1000;

unsigned long lastSend = 0;

bool temperatureOK = false;
bool compassOK = false;

// ============================================================
// SETUP
// ============================================================

void setup() {

    Serial.begin(115200);
    delay(1500);

    Serial.println();
    Serial.println("========================================");
    Serial.println("      SEAFLOOR INTELLIGENCE");
    Serial.println("      REAL HARDWARE MODE");
    Serial.println("========================================");

    // --------------------------------------------------------
    // I2C
    // --------------------------------------------------------

    Wire.begin();

    Serial.println("[I2C] Bus initialized");

    // --------------------------------------------------------
    // TEMPERATURE - DS18B20
    // --------------------------------------------------------

    temperatureSensor.begin();

    if (temperatureSensor.getDeviceCount() > 0) {
        temperatureOK = true;
        Serial.println("[TEMP] DS18B20 detected");
    }
    else {
        temperatureOK = false;
        Serial.println("[TEMP] DS18B20 NOT detected");
    }

    // --------------------------------------------------------
    // MAGNETIC - QMC5883L
    // --------------------------------------------------------

    compass.init();
    compassOK = true;

    Serial.println("[MAG] QMC5883L initialized");

    // --------------------------------------------------------
    // HC-SR04
    // --------------------------------------------------------

    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);

    digitalWrite(TRIG_PIN, LOW);

    Serial.println("[ULTRASONIC] HC-SR04 initialized");

    // --------------------------------------------------------
    // INDUCTIVE SENSOR
    // --------------------------------------------------------

    pinMode(INDUCTIVE_PIN, INPUT);

    Serial.println("[INDUCTIVE] Sensor input initialized");

    // --------------------------------------------------------
    // BUTTON
    // --------------------------------------------------------

    pinMode(BUTTON_PIN, INPUT_PULLUP);

    Serial.println("[BUTTON] Button initialized");

    // --------------------------------------------------------
    // LED
    // --------------------------------------------------------

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    // --------------------------------------------------------
    // BUZZER
    // --------------------------------------------------------

    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);

    Serial.println("[OUTPUT] LED and buzzer initialized");

    // --------------------------------------------------------
    // READY
    // --------------------------------------------------------

    Serial.println("----------------------------------------");
    Serial.println("SYSTEM READY");
    Serial.println("----------------------------------------");
}

// ============================================================
// TEMPERATURE
// ============================================================

float readTemperature() {

    if (!temperatureOK) {
        return -1.0;
    }

    temperatureSensor.requestTemperatures();

    float temperature =
        temperatureSensor.getTempCByIndex(0);

    if (temperature == DEVICE_DISCONNECTED_C) {
        return -1.0;
    }

    return temperature;
}

// ============================================================
// MAGNETIC FIELD
// ============================================================

float readMagnetic() {

    if (!compassOK) {
        return -1.0;
    }

    compass.read();

    int x = compass.getX();
    int y = compass.getY();
    int z = compass.getZ();

    float magnitude = sqrt(
        (float)x * x +
        (float)y * y +
        (float)z * z
    );

    return magnitude;
}

// ============================================================
// ULTRASONIC DISTANCE
// ============================================================

float readDistance() {

    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    unsigned long duration =
        pulseIn(ECHO_PIN, HIGH, 30000);

    if (duration == 0) {
        return -1.0;
    }

    float distance =
        (duration * 0.0343) / 2.0;

    return distance;
}

// ============================================================
// INDUCTIVE SENSOR
// PNP sensor:
// HIGH = metal detected
// LOW  = no metal
// ============================================================

bool readInductive() {

    return digitalRead(INDUCTIVE_PIN) == HIGH;
}

// ============================================================
// BUTTON
// ============================================================

bool readButton() {

    return digitalRead(BUTTON_PIN) == LOW;
}

// ============================================================
// SEND JSON
// ============================================================

void sendReading() {

    float temperature =
        readTemperature();

    float magnetic =
        readMagnetic();

    float distance =
        readDistance();

    bool metalDetected =
        readInductive();

    bool buttonPressed =
        readButton();

    // --------------------------------------------------------
    // LED + BUZZER
    // --------------------------------------------------------

    digitalWrite(
        LED_PIN,
        metalDetected ? HIGH : LOW
    );

    digitalWrite(
        BUZZER_PIN,
        metalDetected ? HIGH : LOW
    );

    // --------------------------------------------------------
    // HUMAN READABLE DEBUG
    // --------------------------------------------------------

    Serial.println();
    Serial.println("========================================");

    Serial.print("MAGNETIC    : ");
    Serial.println(magnetic);

    Serial.print("TEMPERATURE : ");
    Serial.print(temperature);
    Serial.println(" °C");

    Serial.print("DISTANCE    : ");
    Serial.print(distance);
    Serial.println(" cm");

    Serial.print("INDUCTIVE   : ");
    Serial.println(
        metalDetected ? "METAL DETECTED" : "No metal"
    );

    Serial.print("BUTTON      : ");
    Serial.println(
        buttonPressed ? "Pressed" : "Released"
    );

    Serial.println("========================================");

    // --------------------------------------------------------
    // JSON FOR PYTHON BACKEND / DASHBOARD
    // --------------------------------------------------------

    Serial.print("{");

    Serial.print("\"depth\":");
    Serial.print(distance, 2);

    Serial.print(",");

    Serial.print("\"temperature\":");
    Serial.print(temperature, 2);

    Serial.print(",");

    Serial.print("\"magnetic\":");
    Serial.print(magnetic, 2);

    Serial.print(",");

    // We aren't using an EM sensor in this hardware setup.
    Serial.print("\"em\":-1");

    Serial.print(",");

    // No GPS in this prototype.
    Serial.print("\"lat\":0");

    Serial.print(",");

    Serial.print("\"lon\":0");

    Serial.print(",");

    Serial.print("\"satellites\":0");

    Serial.print(",");

    Serial.print("\"inductive\":");
    Serial.print(
        metalDetected ? "true" : "false"
    );

    Serial.print(",");

    Serial.print("\"button\":");
    Serial.print(
        buttonPressed ? "true" : "false"
    );

    Serial.print(",");

    Serial.print("\"hardware\":true");

    Serial.print(",");

    Serial.print("\"probe\":\"PROBE-01\"");

    Serial.println("}");
}

// ============================================================
// LOOP
// ============================================================

void loop() {

    unsigned long now = millis();

    if (now - lastSend >= SEND_INTERVAL) {

        lastSend = now;

        sendReading();
    }
}