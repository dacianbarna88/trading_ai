import os

import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

if not TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN must be set in the environment.")

url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

response = requests.get(url)

print(response.text)