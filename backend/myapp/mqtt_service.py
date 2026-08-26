import json
import logging
import os
import time
from datetime import datetime, date
import paho.mqtt.client as mqtt

from dotenv import load_dotenv

load_dotenv()

# Ensure Django environment is configured if running standalone
import django
from django.utils import timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WildEyeMQTTBackendService")


class BackendMQTTService:
    """
    Backend MQTT Service for listening to Edge Node Camera events
    and saving detection alerts directly into Django database.
    """

    def __init__(self, broker_host=None, broker_port=None):
        self.broker_host = broker_host or os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
        self.broker_port = int(broker_port or os.getenv("MQTT_BROKER_PORT", 1883))
        self.client_id = f"wildeye_backend_{int(time.time())}"
        
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


    def _on_connect(self, client, userdata, flags, rc, properties=None):
        rc_code = rc if isinstance(rc, int) else getattr(rc, "value", 0)
        if rc_code == 0:
            logger.info(f"Backend MQTT: Connected to broker {self.broker_host}:{self.broker_port}")
            # Subscribe to all camera detection events and status heartbeats
            self.client.subscribe("wildeye/camera/+/detection", qos=1)
            self.client.subscribe("wildeye/camera/+/status", qos=0)
            logger.info("Backend MQTT: Subscribed to 'wildeye/camera/+/detection' & 'wildeye/camera/+/status'")
        else:
            logger.warning(f"Backend MQTT: Connection failed with return code {rc}")

    def _on_disconnect(self, client, userdata, flags, rc=None, properties=None):
        logger.warning("Backend MQTT: Disconnected from broker.")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            logger.info(f"Backend MQTT Received [{topic}]: {payload_str[:120]}...")

            if topic.endswith("/detection"):
                self.handle_detection_event(data)
            elif topic.endswith("/status"):
                self.handle_status_event(data)

        except Exception as e:
            logger.error(f"Backend MQTT Error processing message on '{msg.topic}': {e}")

    def handle_detection_event(self, data):
        """
        Parses detection JSON payload and logs it to Django camera_alerts table.
        """
        from myapp.models import camera, animal, camera_alerts

        camera_id = data.get("camera_id")
        animal_name = data.get("animal")
        confidence = data.get("confidence", 0)
        image_path = data.get("image_path", "")
        ts_str = data.get("timestamp")

        if not camera_id and camera_id != 0:
            logger.warning("Backend MQTT: Missing camera_id in detection payload")
            return

        if not animal_name:
            logger.warning("Backend MQTT: Missing animal in detection payload")
            return

        # Parse timestamp or default to now
        alert_date = date.today()
        alert_time = datetime.now().time()
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str)
                alert_date = dt.date()
                alert_time = dt.time()
            except Exception:
                pass

        # Look up Animal object in database
        animal_obj = animal.objects.filter(name__iexact=animal_name).first()
        if not animal_obj:
            logger.warning(f"Backend MQTT: Animal '{animal_name}' not found in DB. Skipping alert creation.")
            return

        # Look up Camera object in database
        camera_obj = None
        if camera_id == 0:
            # Fallback/Image file analysis camera record
            camera_obj, _ = camera.objects.get_or_create(
                camera_id=0,
                defaults={'latitude': 0.0, 'longitude': 0.0}
            )
        else:
            camera_obj = camera.objects.filter(id=camera_id).first()
            if not camera_obj:
                camera_obj = camera.objects.filter(camera_id=camera_id).first()

        if not camera_obj:
            logger.warning(f"Backend MQTT: Camera ID {camera_id} not found in DB. Skipping alert creation.")
            return

        # Create camera_alerts record in Django DB
        new_alert = camera_alerts.objects.create(
            CAMERA=camera_obj,
            ANIMAL=animal_obj,
            image=image_path,
            date=alert_date,
            time=alert_time
        )
        logger.info(f"Backend MQTT: Successfully logged alert ID {new_alert.id} for {animal_name} at Camera {camera_obj.id}")

    def handle_status_event(self, data):
        """
        Processes camera telemetry status update.
        """
        camera_id = data.get("camera_id")
        status = data.get("status")
        logger.info(f"Backend MQTT Telemetry: Camera {camera_id} is {status}")

    def send_command(self, camera_id, command_dict):
        """
        Publishes command dictionary to camera command topic over MQTT.
        """
        topic = f"wildeye/camera/{camera_id}/command"
        payload = json.dumps(command_dict)
        info = self.client.publish(topic, payload, qos=1)
        logger.info(f"Backend MQTT [PUB -> {topic}]: {payload}")
        return info

    def start(self):
        """Starts loop in foreground (blocking) or background."""
        logger.info(f"Starting Backend MQTT Service listening on {self.broker_host}:{self.broker_port}...")
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_forever()


def run_subscriber():
    service = BackendMQTTService()
    service.start()


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wildeye.settings")
    django.setup()
    run_subscriber()
