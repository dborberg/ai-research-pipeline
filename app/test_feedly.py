import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("FEEDLY_TOKEN")

headers = {
    "Authorization": f"Bearer {token}"
}

url = "https://cloud.feedly.com/v3/profile"

response = requests.get(url, headers=headers)

print(response.json())