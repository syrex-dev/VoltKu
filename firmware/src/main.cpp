#include <Arduino.h>
#include <ArduinoJson.h>
#include <DNSServer.h>
#if !defined(SENSOR_DRIVER_BL0942) || !SENSOR_DRIVER_BL0942
#include <PZEM004Tv30.h>
#endif
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <espMqttClient.h>
#include <esp_task_wdt.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <time.h>

#if __has_include("../include/config.h")
#include "../include/config.h"
#elif __has_include("../include/config.example.h")
#warning                                                                       \
    "config.h tidak ditemukan! Menggunakan konfigurasi default dari config.example.h untuk kompilasi."
#include "../include/config.example.h"
#else
#error "config.h maupun config.example.h tidak ditemukan!"
#endif

#ifndef PAIRING_BUTTON_PIN
#define PAIRING_BUTTON_PIN 0
#endif

#ifndef STATUS_LED_PIN
#define STATUS_LED_PIN 2
#endif

#ifndef PUBLISH_INTERVAL_S
#define PUBLISH_INTERVAL_S 10
#endif

#ifndef FIRMWARE_VERSION
#if defined(VOLTKU_V3_HARDWARE) && VOLTKU_V3_HARDWARE
#define FIRMWARE_VERSION "3.0.0"
#else
#define FIRMWARE_VERSION "1.1.0"
#endif
#endif

#ifndef SENSOR_RX_PIN
#if defined(VOLTKU_V3_HARDWARE) && VOLTKU_V3_HARDWARE
#define SENSOR_RX_PIN 0
#else
#define SENSOR_RX_PIN 16
#endif
#endif

#ifndef SENSOR_TX_PIN
#if defined(VOLTKU_V3_HARDWARE) && VOLTKU_V3_HARDWARE
#define SENSOR_TX_PIN 1
#else
#define SENSOR_TX_PIN 17
#endif
#endif

#include <bl0942_driver.hpp>
#include <calibration.hpp>
#include <payload_formatter.hpp>
#include <provisioning_helper.hpp>
#include <ring_buffer.hpp>
#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY
#include "display_ui.hpp"
#endif

#if defined(SENSOR_DRIVER_BL0942) && SENSOR_DRIVER_BL0942
HardwareSerial SensorSerial(1);
#else
// Port Serial PZEM-004T (UART2): RX=GPIO16, TX=GPIO17
HardwareSerial PZEMSerial(2);
PZEM004Tv30 pzem(PZEMSerial, SENSOR_RX_PIN, SENSOR_TX_PIN);
#endif

#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY
voltku_ui::DisplayController displayCtrl;
unsigned long lastDisplayUpdateMs = 0;
#endif

espMqttClient mqttClient;
Preferences preferences;
WebServer portalServer(80);
DNSServer dnsServer;

energy_core::TelemetryRingBuffer ringBuffer;
energy_core::DrainRateLimiter drainLimiter;

// Mutex rekursif pengaman akses ringBuffer di antara loopTask dan task mqttclient
SemaphoreHandle_t ringBufferMutex = nullptr;

struct RingBufferLock {
  RingBufferLock() {
    if (ringBufferMutex) {
      xSemaphoreTakeRecursive(ringBufferMutex, portMAX_DELAY);
    }
  }
  ~RingBufferLock() {
    if (ringBufferMutex) {
      xSemaphoreGiveRecursive(ringBufferMutex);
    }
  }
};

// Konfigurasi runtime (NVS -> fallback config.h -> auto MAC)
char runtimeWifiSsid[65] = {0};
char runtimeWifiPass[97] = {0};
char runtimeMqttHost[97] = {0};
uint16_t runtimeMqttPort = 1883;
char runtimeMqttUser[65] = {0};
char runtimeMqttPass[97] = {0};
char runtimeDeviceId[65] = {0};
char softApSsid[48] = {0};

// Buffer penampung payload JSON & topik MQTT
char payloadBuffer[256];
char topicTelemetry[96];
char topicStatus[96];

// Mode Provisioning / Captive Portal
bool pairingMode = false;
bool portalRunning = false;
bool pendingRestart = false;
unsigned long pendingRestartAtMs = 0;
bool wifiScanTriggered = false;

// Deteksi tombol pairing non-blocking (active-LOW pada GPIO0 / BOOT)
unsigned long pairingBtnPressStartMs = 0;
bool pairingBtnHeldHandled = false;

// Indikator LED status non-blocking
unsigned long lastLedToggleMs = 0;
bool ledState = false;

// Timer & State Telemetri
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

// Kalibrasi presisi multi-titik, tracker harian Rupiah, dan pelacak puncak inrush
energy_core::CalibrationConfig calConfig;
energy_core::DailyRupiahTracker dailyTracker(144470, 0);
energy_core::PeakTracker peakTracker;
energy_core::CalibratedReading latestReading{};
unsigned long lastCalSampleMs = 0;
uint32_t runtimeTariffSen = 144470;

static void copyBounded(char *dest, size_t destSize, const char *src) {
  if (!dest || destSize == 0) {
    return;
  }
  if (!src) {
    dest[0] = '\0';
    return;
  }
  std::strncpy(dest, src, destSize - 1);
  dest[destSize - 1] = '\0';
}

void loadRuntimeConfig() {
  preferences.begin("energy_cfg", true);
  String nvsSsid = preferences.getString("wifi_ssid", "");
  String nvsPass = preferences.getString("wifi_pass", "");
  String nvsMqttHost = preferences.getString("mqtt_host", "");
  uint16_t nvsMqttPort =
      static_cast<uint16_t>(preferences.getUShort("mqtt_port", 0));
  String nvsMqttUser = preferences.getString("mqtt_user", "");
  String nvsMqttPass = preferences.getString("mqtt_pass", "");
  String nvsDevId = preferences.getString("device_id", "");
  calConfig.v_gain = preferences.getFloat("v_gain", 1.0f);
  calConfig.v_offset = preferences.getFloat("v_offset", 0.0f);
  calConfig.i_gain = preferences.getFloat("i_gain", 1.0f);
  calConfig.i_offset = preferences.getFloat("i_offset", 0.0f);
  calConfig.p_gain = preferences.getFloat("p_gain", 1.0f);
  calConfig.p_low_corr_w = preferences.getFloat("p_low_corr", 0.0f);
  calConfig.ct_rating_a = preferences.getUShort("ct_rating", 100);
  runtimeTariffSen = preferences.getULong("tariff_sen", 144470UL);
  preferences.end();
  energy_core::sanitize_calibration(calConfig);
  dailyTracker.set_tariff(runtimeTariffSen, 0);

  if (nvsSsid.length() > 0) {
    copyBounded(runtimeWifiSsid, sizeof(runtimeWifiSsid), nvsSsid.c_str());
    copyBounded(runtimeWifiPass, sizeof(runtimeWifiPass), nvsPass.c_str());
  } else if (!energy_core::is_placeholder_value(WIFI_SSID)) {
    copyBounded(runtimeWifiSsid, sizeof(runtimeWifiSsid), WIFI_SSID);
    copyBounded(runtimeWifiPass, sizeof(runtimeWifiPass), WIFI_PASS);
  } else {
    runtimeWifiSsid[0] = '\0';
    runtimeWifiPass[0] = '\0';
  }

  copyBounded(
      runtimeMqttHost, sizeof(runtimeMqttHost),
      nvsMqttHost.length() > 0 ? nvsMqttHost.c_str() : MQTT_HOST);
  runtimeMqttPort = (nvsMqttPort > 0) ? nvsMqttPort : MQTT_PORT;
  copyBounded(
      runtimeMqttUser, sizeof(runtimeMqttUser),
      nvsMqttUser.length() > 0 ? nvsMqttUser.c_str() : MQTT_USER);
  copyBounded(
      runtimeMqttPass, sizeof(runtimeMqttPass),
      nvsMqttPass.length() > 0 ? nvsMqttPass.c_str() : MQTT_PASS);

  if (nvsDevId.length() > 0 && energy_core::is_valid_device_id(nvsDevId.c_str())) {
    copyBounded(runtimeDeviceId, sizeof(runtimeDeviceId), nvsDevId.c_str());
  } else if (!energy_core::is_placeholder_value(DEVICE_ID) &&
             energy_core::is_valid_device_id(DEVICE_ID)) {
    copyBounded(runtimeDeviceId, sizeof(runtimeDeviceId), DEVICE_ID);
  } else {
    energy_core::format_device_id_from_mac(
        ESP.getEfuseMac(), runtimeDeviceId, sizeof(runtimeDeviceId));
  }

  energy_core::format_ap_ssid_from_device_id(
      runtimeDeviceId, softApSsid, sizeof(softApSsid));
}

void initTopics() {
  std::snprintf(topicTelemetry, sizeof(topicTelemetry), "energy/%s/telemetry",
                runtimeDeviceId);
  std::snprintf(topicStatus, sizeof(topicStatus), "energy/%s/status",
                runtimeDeviceId);
}

void handlePortalRoot() {
  String html =
      "<!DOCTYPE html><html lang='id'><head><meta charset='UTF-8'>"
      "<meta name='viewport' content='width=device-width,initial-scale=1'>"
      "<title>Setup VoltKu</title>"
      "<style>"
      "body{font-family:system-ui,-apple-system,sans-serif;background:#f1f5f9;"
      "color:#0f172a;margin:0;padding:16px;}"
      ".card{max-width:440px;margin:0 auto;background:#fff;border-radius:16px;"
      "padding:20px;box-shadow:0 4px 20px rgba(0,0,0,.08);}"
      "h1{font-size:20px;margin:0 0 4px 0;color:#0284c7;}"
      ".sub{font-size:13px;color:#475569;margin-bottom:14px;}"
      ".idbox{background:#e0f2fe;border:1px solid #7dd3fc;border-radius:10px;"
      "padding:10px 12px;margin-bottom:14px;font-size:13px;}"
      ".idval{font-family:monospace;font-size:16px;font-weight:700;color:#0369a1;}"
      "label{display:block;font-size:13px;font-weight:600;margin:10px 0 4px;}"
      "input,select{width:100%;box-sizing:border-box;padding:10px 12px;"
      "border:1px solid #cbd5e1;border-radius:10px;font-size:14px;}"
      "button{width:100%;margin-top:16px;padding:12px;border:none;"
      "border-radius:10px;background:#0284c7;color:#fff;font-size:15px;"
      "font-weight:700;cursor:pointer;}"
      ".scanbtn{margin-top:8px;background:#e2e8f0;color:#0f172a;font-size:13px;"
      "padding:8px;}"
      ".wifilist{margin-top:8px;display:flex;flex-direction:column;gap:6px;}"
      ".wifiitem{padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;"
      "cursor:pointer;display:flex;justify-content:space-between;font-size:13px;}"
      ".wifiitem:hover{background:#f8fafc;border-color:#0284c7;}"
      "details{margin-top:14px;font-size:12px;color:#475569;}"
      "</style></head><body><div class='card'>"
      "<h1>VoltKu</h1>"
      "<p class='sub'>Sambungkan alat ke Wi-Fi rumah (hanya mendukung 2,4 GHz)</p>"
      "<div class='idbox'>Kode Perangkat Anda (catat untuk di aplikasi):<br>"
      "<span class='idval'>" + String(runtimeDeviceId) + "</span></div>"
      "<button type='button' class='scanbtn' onclick='scanWifi()'>"
      "Cari Jaringan Wi-Fi Sekitar</button>"
      "<div id='wlist' class='wifilist'></div>"
      "<form method='POST' action='/save'>"
      "<label>Nama Wi-Fi Rumah (SSID)</label>"
      "<input id='ssid' name='ssid' required placeholder='Pilih dari daftar atau ketik'>"
      "<label>Password Wi-Fi</label>"
      "<input id='pass' name='pass' type='password' placeholder='Password Wi-Fi rumah'>"
      "<details><summary>Pengaturan Lanjutan Server (Opsional)</summary>"
      "<label>Alamat Server MQTT</label>"
      "<input name='mqtt_host' value='" + String(runtimeMqttHost) + "'>"
      "<label>Port MQTT</label>"
      "<input name='mqtt_port' type='number' value='" + String(runtimeMqttPort) + "'>"
      "<label>Profil CT Clamp (A)</label>"
      "<select name='ct_rating'>"
      "<option value='30'" + String(calConfig.ct_rating_a == 30 ? " selected" : "") + ">30A (Rumah <= 6.6kW)</option>"
      "<option value='50'" + String(calConfig.ct_rating_a == 50 ? " selected" : "") + ">50A (Rumah <= 11kW)</option>"
      "<option value='100'" + String(calConfig.ct_rating_a == 100 ? " selected" : "") + ">100A (Universal / Ruko)</option>"
      "</select>"
      "<label>Gain Kalibrasi (V / I / P)</label>"
      "<input name='v_gain' type='number' step='0.001' value='" + String(calConfig.v_gain, 3) + "'>"
      "<input name='i_gain' type='number' step='0.001' value='" + String(calConfig.i_gain, 3) + "' style='margin-top:4px'>"
      "<input name='p_gain' type='number' step='0.001' value='" + String(calConfig.p_gain, 3) + "' style='margin-top:4px'>"
      "<label>Koreksi Beban Rendah (W)</label>"
      "<input name='p_low_corr' type='number' step='0.1' value='" + String(calConfig.p_low_corr_w, 1) + "'>"
      "<label>Tarif Listrik Layar (sen/kWh, mis. 144470 = Rp1.444,70)</label>"
      "<input name='tariff_sen' type='number' value='" + String(runtimeTariffSen) + "'>"
      "</details>"
      "<button type='submit'>Simpan &amp; Hubungkan</button>"
      "</form></div>"
      "<script>"
      "async function scanWifi(){"
      "const el=document.getElementById('wlist');"
      "el.innerHTML='<small>Memindai Wi-Fi 2.4 GHz...</small>';"
      "try{const r=await fetch('/scan');const d=await r.json();"
      "if(d.scanning){setTimeout(scanWifi,1500);return;}"
      "if(!d.networks||!d.networks.length){el.innerHTML='<small>Tidak ditemukan, coba lagi.</small>';return;}"
      "el.innerHTML='';d.networks.forEach(n=>{"
      "const b=document.createElement('div');b.className='wifiitem';"
      "const s1=document.createElement('span');s1.textContent=n.ssid;"
      "const s2=document.createElement('span');s2.textContent=n.rssi+' dBm';"
      "b.appendChild(s1);b.appendChild(s2);"
      "b.onclick=()=>{document.getElementById('ssid').value=n.ssid;document.getElementById('pass').focus();};"
      "el.appendChild(b);});"
      "}catch(e){el.innerHTML='<small>Gagal scan, ketik SSID manual.</small>';}"
      "}"
      "scanWifi();"
      "</script></body></html>";
  portalServer.send(200, "text/html", html);
}

void handlePortalScan() {
  int n = WiFi.scanComplete();
  JsonDocument doc;
  if (n == WIFI_SCAN_FAILED) {
    if (!wifiScanTriggered) {
      WiFi.scanNetworks(true);
      wifiScanTriggered = true;
    }
    doc["scanning"] = true;
  } else if (n == WIFI_SCAN_RUNNING) {
    doc["scanning"] = true;
  } else {
    wifiScanTriggered = false;
    doc["scanning"] = false;
    JsonArray arr = doc["networks"].to<JsonArray>();
    for (int i = 0; i < n && i < 15; ++i) {
      String s = WiFi.SSID(i);
      if (s.length() > 0) {
        JsonObject item = arr.add<JsonObject>();
        item["ssid"] = s;
        item["rssi"] = WiFi.RSSI(i);
      }
    }
    WiFi.scanDelete();
  }
  String out;
  serializeJson(doc, out);
  portalServer.send(200, "application/json", out);
}

void handlePortalSave() {
  String ssid = portalServer.arg("ssid");
  ssid.trim();
  String pass = portalServer.arg("pass");
  String mhost = portalServer.arg("mqtt_host");
  mhost.trim();
  String mportStr = portalServer.arg("mqtt_port");
  int mport = mportStr.toInt();

  if (ssid.length() == 0 || ssid.length() > 64) {
    portalServer.send(400, "text/html",
                      "<h3>Nama Wi-Fi tidak valid. <a href='/'>Kembali</a></h3>");
    return;
  }

  preferences.begin("energy_cfg", false);
  preferences.putString("wifi_ssid", ssid);
  preferences.putString("wifi_pass", pass);
  if (mhost.length() > 0 && mhost.length() <= 96) {
    preferences.putString("mqtt_host", mhost);
  }
  if (mport > 0 && mport <= 65535) {
    preferences.putUShort("mqtt_port", static_cast<uint16_t>(mport));
  }
  if (portalServer.hasArg("ct_rating")) {
    uint16_t ct = static_cast<uint16_t>(portalServer.arg("ct_rating").toInt());
    if (ct == 30 || ct == 50 || ct == 100) {
      preferences.putUShort("ct_rating", ct);
    }
  }
  if (portalServer.hasArg("v_gain")) {
    preferences.putFloat("v_gain", portalServer.arg("v_gain").toFloat());
  }
  if (portalServer.hasArg("i_gain")) {
    preferences.putFloat("i_gain", portalServer.arg("i_gain").toFloat());
  }
  if (portalServer.hasArg("p_gain")) {
    preferences.putFloat("p_gain", portalServer.arg("p_gain").toFloat());
  }
  if (portalServer.hasArg("p_low_corr")) {
    preferences.putFloat("p_low_corr", portalServer.arg("p_low_corr").toFloat());
  }
  if (portalServer.hasArg("tariff_sen")) {
    unsigned long tsen = static_cast<unsigned long>(portalServer.arg("tariff_sen").toInt());
    if (tsen >= 10000UL && tsen <= 1000000UL) {
      preferences.putULong("tariff_sen", tsen);
    }
  }
  preferences.end();

  // Password tidak pernah dicetak ke Serial
  Serial.print("[PROVISION] Konfigurasi Wi-Fi disimpan untuk SSID: ");
  Serial.println(ssid);

  String okHtml =
      "<!DOCTYPE html><html lang='id'><head><meta charset='UTF-8'>"
      "<meta name='viewport' content='width=device-width,initial-scale=1'>"
      "<title>Tersimpan</title></head>"
      "<body style='font-family:system-ui;padding:24px;text-align:center'>"
      "<h2 style='color:#059669'>Wi-Fi Berhasil Disimpan!</h2>"
      "<p>Alat <b>" + String(runtimeDeviceId) + "</b> sedang memulai ulang "
      "dan menyambung ke <b>" + ssid + "</b>.</p>"
      "<p>Silakan kembali ke aplikasi/dashboard VoltKu untuk "
      "menyelesaikan penambahan perangkat.</p></body></html>";
  portalServer.send(200, "text/html", okHtml);

  pendingRestart = true;
  pendingRestartAtMs = millis();
}

void handlePortalRedirect() {
  portalServer.sendHeader("Location", "http://192.168.4.1/", true);
  portalServer.send(302, "text/plain", "");
}

void startPairingPortal() {
  if (portalRunning) {
    return;
  }
  pairingMode = true;
  portalRunning = true;

  mqttClient.disconnect();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(softApSsid);

  IPAddress apIp = WiFi.softAPIP();
  dnsServer.start(53, "*", apIp);

  portalServer.on("/", HTTP_GET, handlePortalRoot);
  portalServer.on("/scan", HTTP_GET, handlePortalScan);
  portalServer.on("/save", HTTP_POST, handlePortalSave);
  portalServer.on("/generate_204", HTTP_GET, handlePortalRedirect);
  portalServer.on("/hotspot-detect.html", HTTP_GET, handlePortalRedirect);
  portalServer.on("/fwlink", HTTP_GET, handlePortalRedirect);
  portalServer.onNotFound(handlePortalRedirect);
  portalServer.begin();

  WiFi.scanNetworks(true);
  wifiScanTriggered = true;

  Serial.print("[PAIRING] Mode Captive Portal aktif! SSID Hotspot: ");
  Serial.print(softApSsid);
  Serial.print(" | IP: ");
  Serial.println(apIp);
  Serial.print("[PAIRING] Kode Perangkat (Device ID): ");
  Serial.println(runtimeDeviceId);
}

void onMqttConnect(bool sessionPresent) {
  Serial.println("[MQTT] Terhubung ke broker!");
  mqttReconnectBackoffMs = 5000;
  mqttClient.publish(topicStatus, 1, true, "online");
}

void onMqttDisconnect(espMqttClientTypes::DisconnectReason reason) {
  Serial.printf("[MQTT] Terputus dari broker. Alasan: %u\n",
                static_cast<unsigned int>(reason));
  RingBufferLock lock;
  ringBuffer.on_disconnect();
}

void onMqttPublish(uint16_t packetId) {
  RingBufferLock lock;
  ringBuffer.handle_puback(packetId);
}

void setupWiFi() {
  Serial.print("[WiFi] Menghubungkan ke ");
  Serial.println(runtimeWifiSsid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(runtimeWifiSsid, runtimeWifiPass);
}

void syncNTP() {
  Serial.print("[NTP] Memulai sinkronisasi waktu dari ");
  Serial.println(NTP_SERVER);
  configTime(0, 0, NTP_SERVER, "time.google.com", "pool.ntp.org");
}

void checkTimeSync() {
  time_t now = time(nullptr);
  if (now >= 1735689600) {
    if (!timeSynchronized) {
      timeSynchronized = true;
      Serial.printf("[NTP] Waktu valid berhasil diperoleh: epoch %lld\n",
                    static_cast<long long>(now));
    }
  } else {
    timeSynchronized = false;
  }
}

void initSensorPort() {
#if defined(SENSOR_DRIVER_BL0942) && SENSOR_DRIVER_BL0942
  SensorSerial.begin(4800, SERIAL_8N1, SENSOR_RX_PIN, SENSOR_TX_PIN);
#else
  PZEMSerial.begin(9600, SERIAL_8N1, SENSOR_RX_PIN, SENSOR_TX_PIN);
#endif
}

bool readRawSensor(
    float &rawV,
    float &rawI,
    float &rawP,
    float &rawE,
    float &rawF,
    float &rawPf
) {
#if defined(SENSOR_DRIVER_BL0942) && SENSOR_DRIVER_BL0942
  while (SensorSerial.available() > 0) {
    SensorSerial.read();
  }
  const uint8_t req[2] = {
      energy_core::BL0942_READ_CMD_BYTE,
      energy_core::BL0942_READ_ALL_ADDR,
  };
  SensorSerial.write(req, sizeof(req));
  SensorSerial.flush();

  uint8_t pkt[energy_core::BL0942_FULL_PACKET_LEN] = {0};
  size_t idx = 0;
  unsigned long waitStart = millis();
  while (idx < energy_core::BL0942_FULL_PACKET_LEN &&
         (millis() - waitStart) < 90UL) {
    if (SensorSerial.available() > 0) {
      uint8_t b = static_cast<uint8_t>(SensorSerial.read());
      if (idx == 0 && b != energy_core::BL0942_FRAME_HEAD) {
        continue;
      }
      pkt[idx++] = b;
    }
  }

  energy_core::BL0942HardwareScale hw{};
  hw.ct_ratio = energy_core::ct_turns_ratio_for_rating(calConfig.ct_rating_a);
  energy_core::BL0942Reading br =
      energy_core::parse_bl0942_full_packet(pkt, idx, hw);
  if (!br.valid) {
    return false;
  }
  rawV = br.v;
  rawI = br.i;
  rawP = br.p;
  rawE = br.e_kwh;
  rawF = br.f;
  rawPf = br.pf;
  return true;
#else
  rawV = pzem.voltage();
  rawI = pzem.current();
  rawP = pzem.power();
  rawE = pzem.energy();
  rawF = pzem.frequency();
  rawPf = pzem.pf();
  return !isnan(rawV) && !isnan(rawI) && !isnan(rawP) && !isnan(rawE);
#endif
}

void readEnergySensor() {
  float rawV = NAN, rawI = NAN, rawP = NAN, rawE = NAN, rawF = NAN, rawPf = NAN;
  unsigned long nowMs = millis();

  if (readRawSensor(rawV, rawI, rawP, rawE, rawF, rawPf)) {
    energy_core::CalibratedReading cal = energy_core::apply_calibration(
        rawV, rawI, rawP, rawF, rawPf, calConfig);
    latestReading = cal;

    vAccum += cal.v;
    iAccum += cal.i;
    pAccum += cal.p;
    lastValidEnergy = rawE;
    ++sampleCount;
    lastPzemSuccessMs = nowMs;

    fAccum += cal.f;
    ++fSampleCount;
    lastValidF = cal.f;

    pfAccum += cal.pf;
    ++pfSampleCount;
    lastValidPf = cal.pf;

    peakTracker.observe(cal.p, cal.i);

    if (lastCalSampleMs > 0) {
      uint32_t dtMs = static_cast<uint32_t>(nowMs - lastCalSampleMs);
      if (dtMs > 0 && dtMs <= 10000UL) {
        int dayKey = -1;
        if (timeSynchronized) {
          time_t nowWib = time(nullptr) + (7 * 3600);
          dayKey = static_cast<int>(nowWib / 86400);
        }
        dailyTracker.add_power_sample(cal.p, dtMs, dayKey);
      }
    }
    lastCalSampleMs = nowMs;

    if (pzemErrorActive) {
      pzemErrorActive = false;
      Serial.println("[SENSOR] Sensor pulih dan kembali membaca data normal.");
    }
  } else {
    if (nowMs - lastPzemSuccessMs > 30000UL) {
      Serial.println(
          "[SENSOR] Tidak ada respons > 30 detik! Me-restart port serial...");
      pzemErrorActive = true;
#if defined(SENSOR_DRIVER_BL0942) && SENSOR_DRIVER_BL0942
      SensorSerial.end();
#else
      PZEMSerial.end();
#endif
      initSensorPort();
      lastPzemSuccessMs = nowMs;
    }
  }
}

void drainRingBuffer() {
  if (!mqttClient.connected()) {
    return;
  }

  {
    RingBufferLock lock;
    if (ringBuffer.empty()) {
      return;
    }
  }

  unsigned long nowMs = millis();
  if (!drainLimiter.can_drain(nowMs)) {
    return;
  }

  size_t slotIdx = 0;
  energy_core::TelemetrySample sample{};
  bool hasPending = false;
  {
    RingBufferLock lock;
    hasPending = ringBuffer.get_next_pending(slotIdx, sample);
  }

  if (hasPending) {
    int len = energy_core::format_telemetry_payload(
        payloadBuffer, sizeof(payloadBuffer), sample);
    if (len > 0) {
      uint16_t packetId =
          mqttClient.publish(topicTelemetry, 1, false, payloadBuffer);
      if (packetId > 0) {
        RingBufferLock lock;
        ringBuffer.mark_in_flight(slotIdx, packetId);
        drainLimiter.record_drain(nowMs);
        lastDrainMs = nowMs;
      }
    }
  }
}

void handlePairingButton(unsigned long nowMs) {
  if (digitalRead(PAIRING_BUTTON_PIN) == LOW) {
    if (pairingBtnPressStartMs == 0) {
      pairingBtnPressStartMs = nowMs;
      pairingBtnHeldHandled = false;
    } else if (!pairingBtnHeldHandled &&
               (nowMs - pairingBtnPressStartMs >= 3000UL)) {
      pairingBtnHeldHandled = true;
      Serial.println("[BUTTON] Tombol pairing ditahan >= 3 detik.");
      startPairingPortal();
    }
  } else {
    if (pairingBtnPressStartMs > 0 && !pairingBtnHeldHandled &&
        (nowMs - pairingBtnPressStartMs >= 45UL)) {
#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY
      displayCtrl.next_page();
#endif
    }
    pairingBtnPressStartMs = 0;
    pairingBtnHeldHandled = false;
  }
}

void updateStatusLed(unsigned long nowMs) {
  if (pairingMode) {
    if (nowMs - lastLedToggleMs >= 200UL) {
      lastLedToggleMs = nowMs;
      ledState = !ledState;
      digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
    }
  } else if (WiFi.status() == WL_CONNECTED && mqttClient.connected()) {
    digitalWrite(STATUS_LED_PIN, HIGH);
  } else {
    if (nowMs - lastLedToggleMs >= 1000UL) {
      lastLedToggleMs = nowMs;
      ledState = !ledState;
      digitalWrite(STATUS_LED_PIN, ledState ? HIGH : LOW);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- VoltKu (ESP32 Firmware) ---");

  pinMode(PAIRING_BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  ringBufferMutex = xSemaphoreCreateRecursiveMutex();

  esp_err_t wdt_init_ret = esp_task_wdt_init(15, true);
  esp_err_t wdt_add_ret = esp_task_wdt_add(NULL);
  Serial.printf(
      "[WDT] Inisialisasi Hardware WDT (15s): init_ret=%d, add_ret=%d\n",
      wdt_init_ret, wdt_add_ret);

  loadRuntimeConfig();
  initTopics();

  Serial.print("[DEVICE] ID Perangkat: ");
  Serial.println(runtimeDeviceId);

  initSensorPort();
  lastPzemSuccessMs = millis();

#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY
  displayCtrl.begin();
#endif

  if (energy_core::is_placeholder_value(runtimeWifiSsid)) {
    Serial.println("[PROVISION] Belum ada Wi-Fi tersimpan, membuka Captive Portal...");
    startPairingPortal();
    return;
  }

  setupWiFi();
  syncNTP();

  mqttClient.setServer(runtimeMqttHost, runtimeMqttPort);
  mqttClient.setCredentials(runtimeMqttUser, runtimeMqttPass);
  mqttClient.setClientId(runtimeDeviceId);
  mqttClient.setKeepAlive(15);
  mqttClient.setWill(topicStatus, 1, true, "offline");

  mqttClient.onConnect(onMqttConnect);
  mqttClient.onDisconnect(onMqttDisconnect);
  mqttClient.onPublish(onMqttPublish);
}

void loop() {
  esp_task_wdt_reset();

  unsigned long nowMs = millis();

  handlePairingButton(nowMs);
  updateStatusLed(nowMs);

  if (pendingRestart && (nowMs - pendingRestartAtMs >= 1500UL)) {
    Serial.println("[SYSTEM] Restart untuk menerapkan konfigurasi Wi-Fi baru...");
    ESP.restart();
  }

#if defined(ENABLE_TFT_DISPLAY) && ENABLE_TFT_DISPLAY
  if (nowMs - lastDisplayUpdateMs >= 500UL) {
    lastDisplayUpdateMs = nowMs;
    voltku_ui::DisplaySnapshot snap{};
    snap.v = latestReading.v;
    snap.i = latestReading.i;
    snap.p = latestReading.p;
    snap.e_kwh = lastValidEnergy;
    snap.f = latestReading.f > 0.0f ? latestReading.f : lastValidF;
    snap.pf = latestReading.pf;
    snap.peak_w = peakTracker.peak_power_w();
    snap.cost_rp = dailyTracker.cost_rp();
    snap.rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -99;
    {
      RingBufferLock lock;
      snap.buf_count = ringBuffer.size();
    }
    snap.ct_rating_a = calConfig.ct_rating_a;
    snap.wifi_ok = (WiFi.status() == WL_CONNECTED);
    snap.mqtt_ok = mqttClient.connected();
    snap.sensor_ok = !pzemErrorActive;
    snap.pairing_mode = pairingMode;
    snap.device_id = runtimeDeviceId;
    snap.ap_ssid = softApSsid;
#if defined(SENSOR_DRIVER_BL0942) && SENSOR_DRIVER_BL0942
    snap.driver_name = "BL0942";
#else
    snap.driver_name = "PZEM";
#endif
    displayCtrl.render(snap);
  }
#endif

  if (pairingMode) {
    dnsServer.processNextRequest();
    portalServer.handleClient();
    return;
  }

  // 1. Reconnect WiFi non-blocking dengan backoff eksponensial (5s - 60s)
  if (WiFi.status() != WL_CONNECTED) {
    if (nowMs - lastWifiReconnectAttemptMs >= wifiReconnectBackoffMs) {
      lastWifiReconnectAttemptMs = nowMs;
      Serial.printf("[WiFi] Mencoba menyambung kembali (backoff %lus)...\n",
                    wifiReconnectBackoffMs / 1000UL);
      WiFi.disconnect();
      WiFi.reconnect();
      wifiReconnectBackoffMs = (wifiReconnectBackoffMs * 2 > 60000)
                                   ? 60000
                                   : wifiReconnectBackoffMs * 2;
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
      Serial.printf("[MQTT] Mencoba menyambung ke broker (backoff %lus)...\n",
                    mqttReconnectBackoffMs / 1000UL);
      mqttClient.connect();
      mqttReconnectBackoffMs = (mqttReconnectBackoffMs * 2 > 60000)
                                   ? 60000
                                   : mqttReconnectBackoffMs * 2;
    }
  }

  // 4. Pembacaan sensor energi setiap 1 detik
  if (nowMs - lastSensorReadMs >= 1000) {
    lastSensorReadMs = nowMs;
    readEnergySensor();
  }

  // 5. Agregasi dan pembentukan payload telemetri setiap interval
  if (nowMs - lastPublishMs >= (PUBLISH_INTERVAL_S * 1000UL)) {
    lastPublishMs = nowMs;

    if (timeSynchronized && sampleCount > 0) {
      int64_t currentTs = static_cast<int64_t>(time(nullptr));

      if (currentTs == lastPublishedTs) {
        Serial.println(
            "[BUFFER] Timestamp sama dengan sampel sebelumnya, melewati push.");
      } else {
        lastPublishedTs = currentTs;
        energy_core::TelemetrySample sample{};
        sample.ts = currentTs;
        sample.v = vAccum / sampleCount;
        sample.i = iAccum / sampleCount;
        sample.p = pAccum / sampleCount;
        sample.e = lastValidEnergy;
        sample.f = (fSampleCount > 0) ? (fAccum / fSampleCount) : lastValidF;
        sample.pf =
            (pfSampleCount > 0) ? (pfAccum / pfSampleCount) : lastValidPf;
        sample.rssi = static_cast<int16_t>(WiFi.RSSI());
        std::strncpy(sample.fw, FIRMWARE_VERSION, sizeof(sample.fw) - 1);
        sample.fw[sizeof(sample.fw) - 1] = '\0';

        RingBufferLock lock;
        ringBuffer.push(sample);

        if (ringBuffer.overflow_count() > lastReportedOverflow) {
          Serial.printf("[BUFFER] Peringatan: Overflow terjadi! Total sampel "
                        "terbuang: %u\n",
                        ringBuffer.overflow_count());
          lastReportedOverflow = ringBuffer.overflow_count();
        }
      }

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

  // 6. Kuras ring buffer ke broker MQTT secara berurutan
  drainRingBuffer();
}
