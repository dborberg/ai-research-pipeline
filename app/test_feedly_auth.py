import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("FEEDLY_TOKEN")

print("TOKEN RAW:", token)

headers = {
    "Authorization": f"OAuth {token}"
}

url = "https://cloud.feedly.com/v3/search"

response = requests.post(
    url,
    headers=headers,
    json={
        "query": "artificial intelligence",
        "count": 20
    }
)

print("Status:", response.status_code)
print(response.json())