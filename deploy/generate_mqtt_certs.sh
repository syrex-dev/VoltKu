#!/usr/bin/env bash
# Membuat sertifikat CA & Server self-signed untuk Mosquitto TLS (Port 8883).
# Pemakaian: ./deploy/generate_mqtt_certs.sh <DOMAIN_ATAU_IP_SERVER>

set -euo pipefail

TARGET_HOST="${1:-voltku.synemax.web.id}"
CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$CERT_DIR"

echo "[1/3] Membuat Root CA VoltKu MQTT..."
openssl genrsa -out "$CERT_DIR/ca.key" 4096
openssl req -new -x509 -days 3650 -key "$CERT_DIR/ca.key" \
  -subj "/CN=VoltKu-MQTT-CA" \
  -out "$CERT_DIR/ca.crt"

echo "[2/3] Membuat Key & CSR Broker ($TARGET_HOST)..."
openssl genrsa -out "$CERT_DIR/server.key" 2048
openssl req -new -key "$CERT_DIR/server.key" \
  -subj "/CN=$TARGET_HOST" \
  -out "$CERT_DIR/server.csr"

SAN_EXT="subjectAltName=DNS:mosquitto,DNS:localhost,IP:127.0.0.1"
if [[ "$TARGET_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN_EXT="${SAN_EXT},IP:${TARGET_HOST}"
else
  SAN_EXT="${SAN_EXT},DNS:${TARGET_HOST}"
fi

echo "[3/3] Menandatangani Sertifikat Broker (valid 10 tahun)..."
openssl x509 -req -in "$CERT_DIR/server.csr" \
  -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
  -out "$CERT_DIR/server.crt" -days 3650 -sha256 \
  -extfile <(printf "%s\n" "$SAN_EXT")

rm -f "$CERT_DIR/server.csr" "$CERT_DIR/ca.srl"
chmod 644 "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/ca.key" "$CERT_DIR/server.key"

echo "Selesai! File sertifikat berada di: $CERT_DIR"
echo "Tempel isi ca.crt ke MQTT_CA_CERT pada firmware/include/config.h jika memakai MQTT_USE_TLS=1."

