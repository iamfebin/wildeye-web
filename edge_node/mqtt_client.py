import json
import logging
import os
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WildEyeMQTTClient")


class WildEyeMQTTClient:
    """
    MQTT Client manager for WildEye Edge Node Cameras.
    Handles publishing animal detection events, telemetry heartbeats,
    and subscribing to remote camera control commands.
    """

    def __init__(self, camera_id, broker_host=None, broker_port=None, client_id=None):
        self.camera_id = camera_id
        self.broker_host = broker_host or os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
        self.broker_port = int(broker_port or os.getenv("MQTT_BROKER_PORT", 1883))
        self.client_id = client_id or f"wildeye_camera_{camera_id}_{int(time.time())}"
        
        self.is_connected = False
        self.command_callback = None

        # Paho MQTT 2.x compatibility
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        except AttributeError:
            self.client = mqtt.Client(client_id=self.client_id)

        username = os.getenv("MQTT_USERNAME", "").strip()
        password = os.getenv("MQTT_PASSWORD", "").strip()
        if username:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message


        # Topic definitions
        self.detection_topic = f"wildeye/camera/{self.camera_id}/detection"
        self.status_topic = f"wildeye/camera/{self.camera_id}/status"
        self.command_topic = f"wildeye/camera/{self.camera_id}/command"

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        rc_code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
        if rc_code == 0:
            self.is_connected = True
            logger.info(f"MQTT: Connected to broker {self.broker_host}:{self.broker_port}")
            # Subscribe to camera commands
            self.client.subscribe(self.command_topic)
            logger.info(f"MQTT: Subscribed to command topic '{self.command_topic}'")
            # Send initial online status
            self.publish_status("ONLINE")
        else:
            logger.warning(f"MQTT: Connection failed with return code {rc}")

    def _on_disconnect(self, client, userdata, flags, rc=None, properties=None):
        self.is_connected = False
        logger.warning("MQTT: Disconnected from broker.")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
            logger.info(f"MQTT: Command received on '{msg.topic}': {payload_str}")
            data = json.loads(payload_str)
            if self.command_callback:
                self.command_callback(data)
        except Exception as e:
            logger.error(f"MQTT: Error processing message: {e}")

    def start(self):
        """Starts background MQTT client network loop."""
        try:
            logger.info(f"MQTT: Connecting to {self.broker_host}:{self.broker_port}...")
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT: Could not start MQTT client loop: {e}")

    def stop(self):
        """Publishes offline status and stops MQTT network loop."""
        if self.is_connected:
            self.publish_status("OFFLINE")
        self.client.loop_stop()
        self.client.disconnect()

    def set_command_callback(self, callback_fn):
        """Sets callback function for incoming commands from backend."""
        self.command_callback = callback_fn

    def publish_detection(self, animal_name, confidence, image_path="", extra_data=None):
        """
        Publishes animal detection event payload to MQTT topic.
        """
        payload = {
            "camera_id": self.camera_id,
            "animal": animal_name,
            "confidence": confidence,
            "image_path": image_path,
            "timestamp": datetime.now().isoformat(),
            "event": "ANIMAL_DETECTED"
        }
        if extra_data:
            payload.update(extra_data)

        payload_json = json.dumps(payload)
        info = self.client.publish(self.detection_topic, payload_json, qos=1)
        logger.info(f"MQTT [PUB -> {self.detection_topic}]: {animal_name} ({confidence}%)")
        return info

    def publish_status(self, status="ONLINE", telemetry=None):
        """
        Publishes telemetry / heartbeat payload to MQTT topic.
        """
        payload = {
            "camera_id": self.camera_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "telemetry": telemetry or {}
        }
        payload_json = json.dumps(payload)
        info = self.client.publish(self.status_topic, payload_json, qos=0, retain=True)
        logger.info(f"MQTT [PUB -> {self.status_topic}]: Status '{status}'")
        return info


if __name__ == "__main__":
    # Test script for mqtt_client
    print("Testing WildEyeMQTTClient...")
    mqtt_cam = WildEyeMQTTClient(camera_id=1)
    mqtt_cam.start()
    time.sleep(2)
    mqtt_cam.publish_detection(animal_name="elephant", confidence=92, image_path="sample/path.jpg")
    time.sleep(2)
    mqtt_cam.stop()
    print("Test finished.")
