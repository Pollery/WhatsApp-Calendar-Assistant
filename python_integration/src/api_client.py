import requests
from utils.config import load_config

config = load_config()
AUTHENTICATION_API_KEY = config['AUTHENTICATION_API_KEY']
BASE_URL = config['BASE_URL']
INSTANCE_NAME = config['INSTANCE_NAME']
MY_NUMBER = config['MY_NUMBER']

headers = {
    'apikey': AUTHENTICATION_API_KEY,
    'Content-Type': 'application/json'
}
payload = {
    'number': f'{MY_NUMBER}',
    'text': 'Olá!',
    # 'delay': 10000, # simular "digitando"
}
response = requests.post(
    url=f'{BASE_URL}/message/sendText/{INSTANCE_NAME}',
    json=payload,
    headers=headers,
)

print(response.json())

