#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <TinyGPSPlus.h>
#include <QMC5883LCompass.h>
#include <MS5837.h>
#include <math.h>

// ============================================================
// SEAFLOOR INTELLIGENCE
// REAL ESP32 HARDWARE FIRMWARE
// ============================================================

// -------------------- PINS --------------------

#define ONE_WIRE_PIN    4
#define EM_SENSOR_PIN   34

#define INDUCTIVE_PIN   27
#define LED_PIN         2

#define GPS_RX          16
#define GPS_TX          17

// -------------------- OBJECTS --------------------

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature temperatureSensor(&oneWire);

TinyGPSPlus gps;
HardwareSerial GPSserial(2);

QMC5883LCompass compass;
MS5837 depthSensor;

// -------------------- SETTINGS --------------------

const unsigned long SEND_INTERVAL = 1000;

unsigned long lastSend = 0;

// -------------------- SENSOR STATUS --------------------

bool temperatureOK = false;
bool depthOK = false;
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

    } else {

        temperatureOK = false;

        Serial.println("[TEMP] DS18B20 NOT detected");
    }

    // --------------------------------------------------------
    // DEPTH - MS5837
    // --------------------------------------------------------

    if (depthSensor.init()) {

        depthSensor.setModel(MS5837::MS5837_30BA);

        // Seawater density
        depthSensor.setFluidDensity(1029);

        depthOK = true;

        Serial.println("[DEPTH] MS5837 detected");

    } else {

        depthOK = false;

        Serial.println("[DEPTH] MS5837 NOT detected");
    }

    // --------------------------------------------------------
    // MAGNETIC - QMC5883L
    // --------------------------------------------------------

    compass.init();

    compassOK = true;

    Serial.println("[MAG] QMC5883L initialized");

    // --------------------------------------------------------
    // GPS
    // --------------------------------------------------------

    GPSserial.begin(
        9600,
        SERIAL_8N1,
        GPS_RX,
        GPS_TX
    );

    Serial.println("[GPS] GPS serial initialized");

    // --------------------------------------------------------
    // EM SENSOR
    // --------------------------------------------------------

    pinMode(EM_SENSOR_PIN, INPUT);

    Serial.println("[EM] Analog input initialized");

    // --------------------------------------------------------
    // INDUCTIVE SENSOR
    // --------------------------------------------------------

    // PNP sensor output is externally level-shifted to 3.3 V.
    // HIGH = metal detected
    // LOW  = no metal

    pinMode(INDUCTIVE_PIN, INPUT);

    Serial.println("[INDUCTIVE] Sensor input initialized");

    // --------------------------------------------------------
    // LED
    // --------------------------------------------------------

    pinMode(LED_PIN, OUTPUT);

    // Start with LED OFF
    digitalWrite(LED_PIN, LOW);

    Serial.println("[LED] LED initialized");

    // --------------------------------------------------------
    // READY
    // --------------------------------------------------------

    Serial.println("----------------------------------------");
    Serial.println("SYSTEM READY");
    Serial.println("Waiting for sensor readings...");
    Serial.println("----------------------------------------");
}

// ============================================================
// GPS
// ============================================================

void readGPS() {

    while (GPSserial.available()) {

        gps.encode(
            GPSserial.read()
        );
    }
}

// ============================================================
// DEPTH
// ============================================================

float readDepth() {

    if (!depthOK) {

        return -1.0;
    }

    depthSensor.read();

    float depth = depthSensor.depth();

    if (isnan(depth)) {

        return -1.0;
    }

    return depth;
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
// ELECTROMAGNETIC SIGNAL
// ============================================================

float readEM() {

    int raw = analogRead(
        EM_SENSOR_PIN
    );

    float voltage =
        (raw / 4095.0) * 3.3;

    return voltage;
}

// ============================================================
// INDUCTIVE SENSOR
// ============================================================

bool readInductive() {

    return digitalRead(INDUCTIVE_PIN) == HIGH;
}

// ============================================================
// SEND JSON TO COMPUTER
// ============================================================

void sendReading() {

    float depth =
        readDepth();

    float temperature =
        readTemperature();

    float magnetic =
        readMagnetic();

    float em =
        readEM();

    // Read inductive sensor once
    bool metalDetected =
        readInductive();

    // --------------------------------------------------------
    // LED CONTROL
    // --------------------------------------------------------

    if (metalDetected) {

        digitalWrite(LED_PIN, HIGH);

    } else {

        digitalWrite(LED_PIN, LOW);
    }

    double latitude = 0.0;
    double longitude = 0.0;

    int satellites = 0;

    // --------------------------------------------------------
    // GPS
    // --------------------------------------------------------

    if (gps.location.isValid()) {

        latitude =
            gps.location.lat();

        longitude =
            gps.location.lng();
    }

    if (gps.satellites.isValid()) {

        satellites =
            gps.satellites.value();
    }

    // --------------------------------------------------------
    // HUMAN READABLE INDUCTIVE STATUS
    // --------------------------------------------------------

    Serial.print("INDUCTIVE   : ");

    if (metalDetected) {

        Serial.println("METAL DETECTED");

    } else {

        Serial.println("No metal");
    }

    Serial.print("LED         : ");

    if (metalDetected) {

        Serial.println("ON");

    } else {

        Serial.println("OFF");
    }

    // --------------------------------------------------------
    // JSON
    // --------------------------------------------------------

    Serial.print("{");

    Serial.print("\"depth\":");
    Serial.print(depth, 2);

    Serial.print(",");

    Serial.print("\"temperature\":");
    Serial.print(temperature, 2);

    Serial.print(",");

    Serial.print("\"magnetic\":");
    Serial.print(magnetic, 2);

    Serial.print(",");

    Serial.print("\"em\":");
    Serial.print(em, 3);

    Serial.print(",");

    Serial.print("\"lat\":");
    Serial.print(latitude, 6);

    Serial.print(",");

    Serial.print("\"lon\":");
    Serial.print(longitude, 6);

    Serial.print(",");

    Serial.print("\"satellites\":");
    Serial.print(satellites);

    Serial.print(",");

    Serial.print("\"inductive\":");
    Serial.print(
        metalDetected ? "true" : "false"
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

    // Continuously process GPS data
    readGPS();

    unsigned long now =
        millis();

    if (
        now - lastSend >=
        SEND_INTERVAL
    ) {

        lastSend = now;

        sendReading();
    }
}