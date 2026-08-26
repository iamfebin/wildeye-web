from django.core.management.base import BaseCommand
from myapp.mqtt_service import BackendMQTTService


class Command(BaseCommand):
    help = 'Runs the WildEye MQTT Subscriber Daemon to listen for Edge Camera detections and status updates.'

    def add_arguments(self, parser):
        parser.add_argument('--broker', type=str, help='MQTT Broker Host', default=None)
        parser.add_argument('--port', type=int, help='MQTT Broker Port', default=None)

    def handle(self, *args, **options):
        broker = options.get('broker')
        port = options.get('port')
        
        self.stdout.write(self.style.SUCCESS('==================================================='))
        self.stdout.write(self.style.SUCCESS(' Starting WildEye Backend MQTT Subscriber Daemon...'))
        self.stdout.write(self.style.SUCCESS(' Listening on topic: wildeye/camera/+/detection'))
        self.stdout.write(self.style.SUCCESS('==================================================='))
        
        try:
            service = BackendMQTTService(broker_host=broker, broker_port=port)
            service.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nMQTT Subscriber Daemon stopped.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error in MQTT Subscriber Daemon: {e}'))
