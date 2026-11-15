import os
import sys
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

MQTT_HOST = "localhost"
MQTT_PORT = 1883
BACKEND_USER = os.getenv("MQTT_USER", "energy_backend")
BACKEND_PASS = os.getenv("MQTT_PASS", "")
DEVICE_USER = "esp32_device_1"
DEVICE_PASS = os.getenv("MQTT_PASS", "")

backend_received = []
device_received = []


def on_backend_msg(client, userdata, msg):
    backend_received.append((msg.topic, msg.payload.decode(errors="ignore")))


def on_device_msg(client, userdata, msg):
    device_received.append((msg.topic, msg.payload.decode(errors="ignore")))


backend_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test_backend"
)
backend_client.username_pw_set(BACKEND_USER, BACKEND_PASS)
backend_client.on_message = on_backend_msg
backend_client.connect(MQTT_HOST, MQTT_PORT, 60)
backend_client.subscribe("energy/#", qos=1)
backend_client.loop_start()

device_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="test_device"
)
device_client.username_pw_set(DEVICE_USER, DEVICE_PASS)
device_client.on_message = on_device_msg
device_client.connect(MQTT_HOST, MQTT_PORT, 60)
device_client.subscribe("energy/#", qos=1)
device_client.loop_start()

time.sleep(1)

# Test 1: esp32_device_1 publish to its own topic
print("--- TEST 1: Publish to own topic (energy/esp32_device_1/telemetry) ---")
backend_received.clear()
device_client.publish("energy/esp32_device_1/telemetry", '{"test": 1}', qos=1)
time.sleep(1)
test1_ok = (
    len(backend_received) == 1 and backend_received[0][0] == "energy/esp32_device_1/telemetry"
)
print(
    f"Backend received {len(backend_received)} message(s). Status: {'PASS' if test1_ok else 'FAIL'}"
)

# Test 2: esp32_device_1 publish to another device's topic
print("--- TEST 2: Publish to other topic (energy/device_lain/telemetry) ---")
backend_received.clear()
device_client.publish("energy/device_lain/telemetry", '{"test": 2}', qos=1)
time.sleep(1)
test2_ok = len(backend_received) == 0
print(
    f"Backend received {len(backend_received)} message(s). Status: {'PASS' if test2_ok else 'FAIL'}"
)

# Test 3: backend publishes to energy/esp32_device_1/status and energy/other/status
print("--- TEST 3: Device subscribed to energy/# receiving messages ---")
device_received.clear()
backend_client.publish("energy/esp32_device_1/status", '{"status": "online"}', qos=1)
backend_client.publish("energy/device_lain/telemetry", '{"test": 3}', qos=1)
time.sleep(1)
test3_ok = len(device_received) == 0
print(
    f"Device received {len(device_received)} message(s). Status: {'PASS' if test3_ok else 'FAIL'}"
)

backend_client.loop_stop()
backend_client.disconnect()
device_client.loop_stop()
device_client.disconnect()

if test1_ok and test2_ok and test3_ok:
    print("\nALL ACL TESTS PASSED!")
    sys.exit(0)
else:
    print("\nSOME ACL TESTS FAILED!")
    sys.exit(1)
