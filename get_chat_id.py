import requests

TOKEN = "8971662894:AAGMxvrTkzPB_4qYR15Rg7BF29hPTZ9If1o"

url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

response = requests.get(url)

print(response.text)