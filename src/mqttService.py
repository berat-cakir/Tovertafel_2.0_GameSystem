"""
Game system's subscription: receives the PSE output
"""

# Imports
import time
import paho.mqtt.client as mqtt

# IP address and port
mqttIP = "localhost"
mqttPort = 1883
updateService = 10  # Receive updates every x seconds


# Establish connection
def on_connect(gameClient, _, flags, rc):
    gameClient.subscribe("topic/pse_output")


# Dissolve connection
def on_disconnect(gameClient, _, rc=0):
    gameClient.loop_stop()


# Receive message
def on_message(gameClient, _, msg):
    pse_output_msg = msg.payload.decode()
    mood, engagement = pse_output_msg.split(',')
    mqttServ.mood, mqttServ.engagement = mood, engagement
    time.sleep(updateService)


# Define MQTT Service
class MQTTService:
    """
    MQTT Service
    """
    def __init__(self):
        self.state = 1
        self.mood = None
        self.engagement = None

    def update(self):
        """
        Update service
        """
        self.state += 1


# Establish MQTT connection to receive PSE output
mqttServ = MQTTService()
game_client = mqtt.Client()
game_client.connect(mqttIP, mqttPort, 60)
game_client.on_connect, game_client.on_disconnect, game_client.on_message = on_connect, on_disconnect, on_message
game_client.loop_start()  # Start the subscriber loop
