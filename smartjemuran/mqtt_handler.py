import paho.mqtt.client as mqtt
import logging
from threading import Lock
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import time
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class JemuranData:
    temperature: float
    humidity: float
    light: int
    rain: bool
    last_update: datetime
    current_hour: int


class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.lock = Lock()
        self.latest_data: Optional[JemuranData] = None
        self.broker = "212.85.27.126"
        self.port = 1883
        self.is_connected = False
        self.servo_status = None

        # Setup callback
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def connect(self):
        """Connect to MQTT broker"""
        try:
            if not self.is_connected:
                logger.info(
                    f"Connecting to MQTT broker {self.broker}:{self.port}...")
                self.client.connect(self.broker, self.port, 60)
                self.client.loop_start()
                self.is_connected = True
                time.sleep(1)
        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT: {e}")
            self.is_connected = False
            raise

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            logger.info("✅ Disconnected from MQTT broker")

    def on_connect(self, client, userdata, flags, rc):
        """Connection callback"""
        if rc == 0:
            self.is_connected = True
            logger.info("✅ Connected to MQTT broker")
            client.subscribe("jemuran/data")
            client.subscribe("jemuran/control")
            client.subscribe("jemuran/status")
            logger.info(
                "🔔 Subscribed to topics: jemuran/data, jemuran/control, jemuran/status")
        else:
            error_codes = {
                1: "Unsupported protocol version",
                2: "Invalid client ID",
                3: "Server unavailable",
                4: "Invalid username/password",
                5: "Not authenticated"
            }
            error_msg = error_codes.get(rc, f"Unknown error code: {rc}")
            logger.error(f"❌ Connection failed: {error_msg}")
            self.is_connected = False

    def on_disconnect(self, client, userdata, rc):
        """Disconnection callback"""
        self.is_connected = False
        if rc == 0:
            logger.info("Disconnected from broker")
        else:
            logger.warning(
                f"⚠️ Unexpected disconnection, trying to reconnect... (RC: {rc})")
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")

    def on_message(self, client, userdata, msg):
        """Message callback"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Message received [{topic}]: {payload}")

            if topic == "jemuran/control":
                logger.info(f" Servo Status: {payload}")
                self.servo_status = payload

            elif topic == "jemuran/status":
                self.servo_status = payload
                logger.info(f"Latest Servo Status: {payload}")

            elif topic == "jemuran/data":
                self.process_sensor_data(payload)

        except UnicodeDecodeError:
            logger.error("Failed to decode payload (not UTF-8)")
        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)

    def parse_rtc_time(self, time_str: str) -> datetime:
        """
        Parse RTC time string to datetime object
        Supports multiple possible RTC time formats
        """
        formats_to_try = [
            "%Y-%m-%d %H:%M:%S",  # Format 1: "2025-06-24 21:28:44"
            "%d/%m/%Y %H:%M:%S",  # Format 2: "24/06/2025 21:28:44"
            "%H:%M:%S %d-%m-%Y",  # Format 3: "21:28:44 24-06-2025"
            "%Y-%m-%dT%H:%M:%S",  # Format 4: "2025-06-24T21:28:44"
        ]

        for fmt in formats_to_try:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue

        logger.warning(
            f"⚠️ Invalid RTC time format: {time_str}, using current time instead")
        return datetime.now()

    def process_sensor_data(self, payload: str):
        """Process sensor data from ESP32"""
        try:
            data_dict = {}
            rtc_time_str = None

            # Parse all key-value pairs from payload
            for pair in payload.split(','):
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    # Handle special cases first
                    if key == 'waktu':
                        rtc_time_str = value
                        continue

                    # Convert data types based on key
                    if key in ['suhu', 'kelembapan', 'heat_index', 'dew_point']:
                        try:
                            value = float(value)
                        except ValueError:
                            logger.warning(f"⚠️ Invalid {key} value: {value}")
                            continue
                    elif key == 'cahaya_analog':
                        try:
                            value = int(value)
                        except ValueError:
                            logger.warning(f"⚠️ Invalid light value: {value}")
                            continue
                    elif key == 'hujan':
                        value = value.lower() not in [
                            'tidak hujan', 'false', '0']

                    data_dict[key] = value

            # Determine the timestamp to use
            if rtc_time_str:
                last_update = self.parse_rtc_time(rtc_time_str)
            else:
                last_update = datetime.now()
                logger.warning(
                    "⚠️ No RTC time provided in payload, using system time")

            current_hour = last_update.hour

            # Map raw field names to standardized names
            field_mapping = {
                'suhu': 'temperature',
                'kelembapan': 'humidity',
                'cahaya_analog': 'light',
                'hujan': 'rain'
            }

            mapped_data = {
                field_mapping.get(k, k): v
                for k, v in data_dict.items()
                if k in field_mapping
            }

            # Create and store the data object
            with self.lock:
                self.latest_data = JemuranData(
                    temperature=mapped_data.get('temperature', 0.0),
                    humidity=mapped_data.get('humidity', 0.0),
                    light=mapped_data.get('light', 0),
                    rain=mapped_data.get('rain', False),
                    last_update=last_update,
                    current_hour=current_hour
                )
                logger.info("💾 Sensor data updated")

        except Exception as e:
            logger.error(
                f"❌ Failed to process sensor data: {e}", exc_info=True)

    def get_formatted_data(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Get latest sensor data in two formats:
        1. For API response with ISO formatted timestamp
        2. For recommendation system input with hour as float
        """
        with self.lock:
            if not self.latest_data:
                return None, None

            # Format 1: For API response
            api_response = {
                "temperature": self.latest_data.temperature,
                "humidity": self.latest_data.humidity,
                "light": self.latest_data.light,
                "rain": self.latest_data.rain,
                "last_update": self.latest_data.last_update.isoformat()
            }

            # Format 2: For recommendation system
            recommendation_input = {
                "temperature": self.latest_data.temperature,
                "humidity": self.latest_data.humidity,
                "light": float(self.latest_data.light),
                "rain": 0.0 if not self.latest_data.rain else 1.0,
                "time": float(self.latest_data.current_hour)
            }

            return api_response, recommendation_input

    async def async_publish_control(self, action: str):
        """Async wrapper for publish_control"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.publish_control, action)

    def publish_control(self, action: str, max_retries: int = 3) -> Tuple[bool, str]:
        """Send control command to ESP32"""
        if action not in ["buka", "tutup"]:
            error_msg = f"Invalid command: {action} (must be 'buka' or 'tutup')"
            logger.error(f"❌ {error_msg}")
            return False, error_msg

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🌀 Attempt {attempt}/{max_retries}: {action}")

                if not self.is_connected:
                    logger.warning(
                        "⚠️ Not connected to broker, trying to reconnect...")
                    self.connect()

                    if not self.is_connected:
                        logger.error("❌ Failed to reconnect to broker")
                        continue

                result = self.client.publish(
                    "jemuran/control",
                    action,
                    qos=1,
                    retain=False
                )

                time.sleep(0.5)

                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"✅ Command '{action}' sent successfully")

                    # Wait for confirmation from ESP32
                    timeout = time.time() + 5
                    while time.time() < timeout:
                        if self.servo_status == action:
                            logger.info(
                                f"🔄 Confirmation received: Servo {action}")
                            return True, f"Servo successfully {action}"
                        time.sleep(0.1)

                    logger.warning(
                        f"⚠️ No confirmation from ESP32 for command {action}")
                    continue

                else:
                    logger.error(f"Failed to send command (RC: {result.rc})")
                    continue

            except Exception as e:
                logger.error(
                    f"Exception during publish_control: {str(e)}", exc_info=True)
                continue

        error_msg = f"Failed to send command {action} after {max_retries} attempts"
        logger.error(f"❌ {error_msg}")
        return False, error_msg

    def get_servo_status(self) -> Optional[str]:
        """Get last known servo status"""
        return self.servo_status
