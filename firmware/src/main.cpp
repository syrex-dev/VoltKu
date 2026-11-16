#include <Arduino.h>
#include <WiFi.h>
#include <espMqttClient.h>
#include <PZEM004Tv30.h>
#include <esp_task_wdt.h>
#include <time.h>

#if __has_include("../include/config.h")
    #include "../include/config.h"
#elif __has_include("../include/config.example.h")
    #include "../include/config.example.h"
#else
    #define WIFI_SSID "NAMA_WIFI_ANDA"
    #define WIFI_PASS "PASSWORD_WIFI_ANDA"
    #define MQTT_HOST "192.168.1.100"
    #define MQTT_PORT 1883
    #define MQTT_USER "device-01"
    #define MQTT_PASS "PASSWORD_MQTT_ANDA"
    #define DEVICE_ID "device-01"
    #define NTP_SERVER "pool.ntp.org"
    #define PUBLISH_INTERVAL_S 10
    #define FIRMWARE_VERSION "1.0.0"
#endif

#include <payload_formatter.hpp>
#include <ring_buffer.hpp>

// Port Serial PZEM-004T (UART2): RX=GPIO16, TX=GPIO17
HardwareSerial PZEMSerial(2);
PZEM004Tv30 pzem(PZEMSerial, 16, 17);

espMqttClient mqttClient;
energy_core::TelemetryRingBuffer ringBuffer;
energy_core::DrainRateLimiter drainLimiter;

// Buffer penampung payload JSON
char payloadBuffer[256];
char topicTelemetry[64];
char topicStatus[64];

// Timer & State
unsigned long lastSensorReadMs = 0;
unsigned long lastPublishMs = 0;
unsigned long lastPzemSuccessMs = 0;
unsigned long lastDrainMs = 0;
unsigned long lastMqttReconnectAttemptMs = 0;

// Rolling Accumulator PZEM (10 detik)
float vAccum = 0.0f;
float iAccum = 0.0f;
float pAccum = 0.0f;
float fAccum = 0.0f;
float pfAccum = 0.0f;
float lastValidEnergy = 0.0f;
int sampleCount = 0;

bool timeSynchronized = false;

void initTopics() {
    std::snprintf(topicTelemetry, sizeof(topicTelemetry), "energy/%s/telemetry", DEVICE_ID);
    std::snprintf(topicStatus, sizeof(topicStatus), "energy/%s/status", DEVICE_ID);
}

void onMqttConnect(bool sessionPresent) {
    Serial.println("[MQTT] Terhubung ke broker!");
    // Publikasikan status online (retained, QoS 1)
    mqttClient.publish(topicStatus, 1, true, "online");
}

void onMqttDisconnect(espMqttClientTypes::DisconnectReason reason) {
    Serial.printf("[MQTT] Terputus dari broker. Alasan: %u\n", static_cast<unsigned int>(reason));
    ringBuffer.on_disconnect();
}

void onMqttPublish(uint16_t packetId) {
    // Dipanggil saat broker mengirim PUBACK (QoS 1)
    ringBuffer.handle_puback(packetId);
}

void setupWiFi() {
    Serial.print("[WiFi] Menghubungkan ke ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void syncNTP() {
    Serial.print("[NTP] Memulai sinkronisasi waktu dari ");
    Serial.println(NTP_SERVER);
    configTime(0, 0, NTP_SERVER, "time.google.com", "pool.ntp.org");
}

void checkTimeSync() {
    time_t now = time(nullptr);
    // 1735689600 = 2025-01-01 00:00:00 UTC
    if (now >= 1735689600) {
        if (!timeSynchronized) {
            timeSynchronized = true;
            Serial.printf("[NTP] Waktu valid berhasil diperoleh: epoch %lld\n", static_cast<long long>(now));
        }
    } else {
        timeSynchronized = false;
    }
}

void readPZEM() {
    float v = pzem.voltage();
    float i = pzem.current();
    float p = pzem.power();
    float e = pzem.energy();
    float f = pzem.frequency();
    float pf = pzem.pf();

    if (!isnan(v) && !isnan(i) && !isnan(p) && !isnan(e)) {
        vAccum += v;
        iAccum += i;
        pAccum += p;
        fAccum += (!isnan(f) ? f : 50.0f);
        pfAccum += (!isnan(pf) ? pf : 1.0f);
        lastValidEnergy = e;
        ++sampleCount;
        lastPzemSuccessMs = millis();
    } else {
        // PZEM tidak merespons / NaN
        if (millis() - lastPzemSuccessMs > 30000) {
            Serial.println("[PZEM] Tidak ada respons > 30 detik! Me-restart UART2...");
            PZEMSerial.end();
            delay(50);
            PZEMSerial.begin(9600, SERIAL_8N1, 16, 17);
            lastPzemSuccessMs = millis();
        }
    }
}

void drainRingBuffer() {
    if (!mqttClient.connected() || ringBuffer.empty()) {
        return;
    }

    // Rate limiter pengurasan ring buffer: maks 5 sampel / detik via energy_core::DrainRateLimiter
    unsigned long nowMs = millis();
    if (!drainLimiter.can_drain(nowMs)) {
        return;
    }

    size_t slotIdx = 0;
    energy_core::TelemetrySample sample{};
    if (ringBuffer.get_next_pending(slotIdx, sample)) {
        int len = energy_core::format_telemetry_payload(payloadBuffer, sizeof(payloadBuffer), sample);
        if (len > 0) {
            uint16_t packetId = mqttClient.publish(topicTelemetry, 1, false, payloadBuffer);
            if (packetId > 0) {
                ringBuffer.mark_in_flight(slotIdx, packetId);
                drainLimiter.record_drain(nowMs);
                lastDrainMs = nowMs;
            }
        }
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println("\n--- Monitor Listrik Pintar (ESP32 Firmware) ---");

    // Inisialisasi Watchdog Timer Hardware 15 detik
    esp_task_wdt_init(15, true);
    esp_task_wdt_add(NULL);

    initTopics();

    // Inisialisasi UART2 untuk PZEM-004T (RX=16, TX=17)
    PZEMSerial.begin(9600, SERIAL_8N1, 16, 17);
    lastPzemSuccessMs = millis();

    setupWiFi();
    syncNTP();

    // Konfigurasi MQTT Client dengan LWT QoS 1 Retained
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setCredentials(MQTT_USER, MQTT_PASS);
    mqttClient.setClientId(DEVICE_ID);
    mqttClient.setKeepAlive(15);
    mqttClient.setWill(topicStatus, 1, true, "offline");

    mqttClient.onConnect(onMqttConnect);
    mqttClient.onDisconnect(onMqttDisconnect);
    mqttClient.onPublish(onMqttPublish);
}

void loop() {
    // Reset Hardware Watchdog Timer setiap siklus
    esp_task_wdt_reset();

    unsigned long nowMs = millis();

    // 1. Periksa sinkronisasi waktu NTP
    checkTimeSync();

    // 2. Hubungkan kembali MQTT jika terputus (reconnect backoff 5 detik)
    if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
        if (nowMs - lastMqttReconnectAttemptMs >= 5000) {
            lastMqttReconnectAttemptMs = nowMs;
            Serial.println("[MQTT] Mencoba menghubungkan ke broker...");
            mqttClient.connect();
        }
    }

    // 3. Pembacaan sensor PZEM setiap 1 detik
    if (nowMs - lastSensorReadMs >= 1000) {
        lastSensorReadMs = nowMs;
        readPZEM();
    }

    // 4. Agregasi dan pembentukan payload telemetri setiap interval (default 10 detik)
    if (nowMs - lastPublishMs >= (PUBLISH_INTERVAL_S * 1000UL)) {
        lastPublishMs = nowMs;

        // Jangan publikasikan telemetri sebelum waktu valid NTP diperoleh
        if (timeSynchronized && sampleCount > 0) {
            energy_core::TelemetrySample sample{};
            sample.ts = static_cast<int64_t>(time(nullptr));
            sample.v = vAccum / sampleCount;
            sample.i = iAccum / sampleCount;
            sample.p = pAccum / sampleCount;
            sample.e = lastValidEnergy;
            sample.f = fAccum / sampleCount;
            sample.pf = pfAccum / sampleCount;
            sample.rssi = static_cast<int16_t>(WiFi.RSSI());
            std::strncpy(sample.fw, FIRMWARE_VERSION, sizeof(sample.fw) - 1);
            sample.fw[sizeof(sample.fw) - 1] = '\0';

            ringBuffer.push(sample);

            // Reset akumulator
            vAccum = 0.0f;
            iAccum = 0.0f;
            pAccum = 0.0f;
            fAccum = 0.0f;
            pfAccum = 0.0f;
            sampleCount = 0;
        }
    }

    // 5. Kuras ring buffer ke broker MQTT secara berurutan (maks 5 sampel / detik)
    drainRingBuffer();
}
