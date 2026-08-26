import json
import os
import sys
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

# Add edge_node to sys.path to import mqtt_client if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'edge_node')))
import mqtt_client



def run_test():
    print("=" * 60)
    print(" WildEye MQTT Test Publisher Utility")
    print("=" * 60)

    camera_id = 1
    broker_host = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
    port = int(os.getenv("MQTT_BROKER_PORT", 1883))

    print(f"Connecting to MQTT Broker: {broker_host}:{port} for Camera ID: {camera_id}...")

    client = mqtt_client.WildEyeMQTTClient(camera_id=camera_id, broker_host=broker_host, broker_port=port)
    client.start()
    
    time.sleep(2)

    # 1. Publish Heartbeat / Status
    print("\n[1] Publishing Status (ONLINE)...")
    client.publish_status("ONLINE", telemetry={"battery": "98%", "signal": "STRONG"})
    time.sleep(1)

    # 2. Publish Simulated Animal Detection
    print("\n[2] Publishing Simulated Animal Detection (Elephant, 95% confidence)...")
    client.publish_detection(
        animal_name="elephant",
        confidence=95,
        image_path="Detected_Images_Camera/2026/8/3/elephant_test_1722682620.jpg",
        extra_data={"location": {"lat": 11.2588, "lng": 75.7804}}
    )
    time.sleep(2)

    # 3. Publish Simulated Tiger Detection
    print("\n[3] Publishing Simulated Animal Detection (Tiger, 88% confidence)...")
    client.publish_detection(
        animal_name="tiger",
        confidence=88,
        image_path="Detected_Images_Camera/2026/8/3/tiger_test_1722682630.jpg"
    )
    time.sleep(2)

    client.stop()
    print("\nMQTT Test Publisher completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
