#include <Arduino.h>
#include <WiFi.h>
#include <espMqttClient.h>
#include <PZEM004Tv30.h>
#include <esp_task_wdt.h>
#include <time.h>

#if __has_include("../include/config.h")
    #include "../include/config.h"
#elif __has_include("../include/config.example.h")
    #warning "config.h tidak ditemukan! Menggunakan konfigurasi default dari config.example.h untuk kompilasi."
    #include "../include/config.example.h"
#else
    #error "config.h maupun config.example.h tidak ditemukan!"
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

// Non-blocking reconnect backoff (5 - 60 detik)
unsigned long lastWifiReconnectAttemptMs = 0;
unsigned long wifiReconnectBackoffMs = 5000;
unsigned long lastMqttReconnectAttemptMs = 0;
unsigned long mqttReconnectBackoffMs = 5000;

// Overflow tracking
uint32_t lastReportedOverflow = 0;
bool pzemErrorActive = false;

// Rolling Accumulator PZEM (10 detik)
float vAccum = 0.0f;
float iAccum = 0.0f;
float pAccum = 0.0f;
float fAccum = 0.0f;
float pfAccum = 0.0f;
float lastValidEnergy = 0.0f;
float lastValidF = 50.0f;
float lastValidPf = 1.0f;
int sampleCount = 0;
int fSampleCount = 0;
int pfSampleCount = 0;
int64_t lastPublishedTs = 0;

bool timeSynchronized = false;

void initTopics() {
    std::snprintf(topicTelemetry, sizeof(topicTelemetry), "energy/%s/telemetry", DEVICE_ID);
    std::snprintf(topicStatus, sizeof(topicStatus), "energy/%s/status", DEVICE_ID);
}

void onMqttConnect(bool sessionPresent) {
    Serial.println("[MQTT] Terhubung ke broker!");
    mqttReconnectBackoffMs = 5000; // Reset backoff saat berhasil tersambung
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
    Serial.println(WIFI_SSID); // Hanya mencetak SSID, password tidak pernah dicetak
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
        lastValidEnergy = e;
        ++sampleCount;
        lastPzemSuccessMs = millis();

        // Frekuensi: jangan mengarang 50.0 saat NaN, lewati sampel dan gunakan nilai valid terakhir
        if (!isnan(f)) {
            fAccum += f;
            ++fSampleCount;
            lastValidF = f;
        } else {
            Serial.println("[PZEM] Frekuensi bernilai NaN, melewati akumulasi dan menandai penggunaan nilai valid terakhir.");
        }

        // Power factor: jangan mengarang 1.0 saat NaN, lewati sampel dan gunakan nilai valid terakhir
        if (!isnan(pf)) {
            pfAccum += pf;
            ++pfSampleCount;
            lastValidPf = pf;
        } else {
            Serial.println("[PZEM] Power factor bernilai NaN, melewati akumulasi dan menandai penggunaan nilai valid terakhir.");
        }

        if (pzemErrorActive) {
            pzemErrorActive = false;
            Serial.println("[PZEM] Sensor pulih dan kembali membaca data normal.");
        }
    } else {
        // PZEM tidak merespons / bernilai NaN
        if (millis() - lastPzemSuccessMs > 30000) {
            Serial.println("[PZEM] Tidak ada respons > 30 detik! Me-restart UART2...");
            pzemErrorActive = true;
            // Tanpa delay blocking (millis loop) dan tanpa publish status error_pzem ke broker
            PZEMSerial.end();
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

    // Inisialisasi Watchdog Timer Hardware 15 detik (API Arduino Core 2.0.17 / ESP-IDF)
    esp_err_t wdt_init_ret = esp_task_wdt_init(15, true);
    esp_err_t wdt_add_ret = esp_task_wdt_add(NULL);
    Serial.printf("[WDT] Inisialisasi Hardware WDT (15s): init_ret=%d, add_ret=%d\n", wdt_init_ret, wdt_add_ret);

    initTopics();

    // Inisialisasi UART2 untuk PZEM-004T (RX=16, TX=17)
    PZEMSerial.begin(9600, SERIAL_8N1, 16, 17);
    lastPzemSuccessMs = millis();

    setupWiFi();
    syncNTP();

    // Konfigurasi MQTT Client dengan LWT QoS 1 Retained
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setCredentials(MQTT_USER, MQTT_PASS); // Kredensial tidak pernah dicetak ke Serial
    mqttClient.setClientId(DEVICE_ID);
    mqttClient.setKeepAlive(15);
    mqttClient.setWill(topicStatus, 1, true, "offline");

    mqttClient.onConnect(onMqttConnect);
    mqttClient.onDisconnect(onMqttDisconnect);
    mqttClient.onPublish(onMqttPublish);
}

void loop() {
    // Reset Hardware Watchdog Timer setiap siklus loop utama
    esp_task_wdt_reset();

    unsigned long nowMs = millis();

    // 1. Reconnect WiFi non-blocking dengan backoff eksponensial (5s - 60s)
    if (WiFi.status() != WL_CONNECTED) {
        if (nowMs - lastWifiReconnectAttemptMs >= wifiReconnectBackoffMs) {
            lastWifiReconnectAttemptMs = nowMs;
            Serial.printf("[WiFi] Mencoba menyambung kembali (backoff %lus)...\n", wifiReconnectBackoffMs / 1000UL);
            WiFi.disconnect();
            WiFi.reconnect();
            wifiReconnectBackoffMs = (wifiReconnectBackoffMs * 2 > 60000) ? 60000 : wifiReconnectBackoffMs * 2;
        }
    } else {
        wifiReconnectBackoffMs = 5000;
    }

    // 2. Periksa sinkronisasi waktu NTP
    checkTimeSync();

    // 3. Reconnect MQTT non-blocking dengan backoff eksponensial (5s - 60s)
    if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
        if (nowMs - lastMqttReconnectAttemptMs >= mqttReconnectBackoffMs) {
            lastMqttReconnectAttemptMs = nowMs;
            Serial.printf("[MQTT] Mencoba menyambung ke broker (backoff %lus)...\n", mqttReconnectBackoffMs / 1000UL);
            mqttClient.connect();
            mqttReconnectBackoffMs = (mqttReconnectBackoffMs * 2 > 60000) ? 60000 : mqttReconnectBackoffMs * 2;
        }
    }

    // 4. Pembacaan sensor PZEM setiap 1 detik
    if (nowMs - lastSensorReadMs >= 1000) {
        lastSensorReadMs = nowMs;
        readPZEM();
    }

    // 5. Agregasi dan pembentukan payload telemetri setiap interval (default 10 detik)
    if (nowMs - lastPublishMs >= (PUBLISH_INTERVAL_S * 1000UL)) {
        lastPublishMs = nowMs;

        // Jangan publikasikan telemetri sebelum waktu valid NTP diperoleh
        if (timeSynchronized && sampleCount > 0) {
            int64_t currentTs = static_cast<int64_t>(time(nullptr));

            // Hindari duplikasi timestamp: lewati jika timestamp sama dengan sampel sebelumnya
            if (currentTs == lastPublishedTs) {
                Serial.println("[BUFFER] Timestamp sama dengan sampel sebelumnya, melewati push.");
            } else {
                lastPublishedTs = currentTs;
                energy_core::TelemetrySample sample{};
                sample.ts = currentTs;
                sample.v = vAccum / sampleCount;
                sample.i = iAccum / sampleCount;
                sample.p = pAccum / sampleCount;
                sample.e = lastValidEnergy;
                sample.f = (fSampleCount > 0) ? (fAccum / fSampleCount) : lastValidF;
                sample.pf = (pfSampleCount > 0) ? (pfAccum / pfSampleCount) : lastValidPf;
                sample.rssi = static_cast<int16_t>(WiFi.RSSI());
                std::strncpy(sample.fw, FIRMWARE_VERSION, sizeof(sample.fw) - 1);
                sample.fw[sizeof(sample.fw) - 1] = '\0';

                ringBuffer.push(sample);

                // Periksa apakah ada buffer overflow yang terjadi
                if (ringBuffer.overflow_count() > lastReportedOverflow) {
                    Serial.printf(
                        "[BUFFER] Peringatan: Overflow terjadi! Total sampel terbuang: %u\n",
                        ringBuffer.overflow_count()
                    );
                    lastReportedOverflow = ringBuffer.overflow_count();
                }
            }

            // Reset akumulator rolling window
            vAccum = 0.0f;
            iAccum = 0.0f;
            pAccum = 0.0f;
            fAccum = 0.0f;
            pfAccum = 0.0f;
            sampleCount = 0;
            fSampleCount = 0;
            pfSampleCount = 0;
        }
    }

    // 6. Kuras ring buffer ke broker MQTT secara berurutan (maks 5 sampel / detik)
    drainRingBuffer();
}
