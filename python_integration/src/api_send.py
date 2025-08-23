import requests
from utils.config import load_config


config = load_config()


class EvolutionAPI:

    BASE_URL = config["BASE_URL"]
    INSTANCE_NAME = config["INSTANCE_NAME"]

    def __init__(self):
        self.__api_key = config["AUTHENTICATION_API_KEY"]
        self.__headers = {
            "apikey": self.__api_key,
            "Content-Type": "application/json",
        }

    def send_message(self, number, text):
        payload = {
            "number": number,
            "text": text,
        }
        response = requests.post(
            url=f"{self.BASE_URL}/message/sendText/{self.INSTANCE_NAME}",
            headers=self.__headers,
            json=payload,
        )
        return response.json()
