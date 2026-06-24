import pandas as pd
import requests
import time
import os
from datetime import datetime

TOKEN = "8971662894:AAG1nNNaiblQ678wHLthSmbq1YzpMIb2j1c"
CHAT_ID = "6433927898"


print("🚀 Bot Telegram pornit...\n")

while True:

    try:

        print("🚀 Rulez analiza...")

        # Citim semnalele
        data = pd.read_csv("signals.csv")

        # Selectăm semnalele importante
        important = data[
            (data["Signal"] == "STRONG BUY") |
            ((data["Signal"] == "TAKE PROFIT") & (data["RSI"] > 75))
        ]

        # Citim ultimele semnale salvate
        if os.path.exists("last_signals.csv") and os.path.getsize("last_signals.csv") > 0:

            last = pd.read_csv("last_signals.csv")

        else:

            last = pd.DataFrame(columns=["Ticker", "Signal"])

        alerts = []

        # Verificăm schimbările de semnal
        for _, row in important.iterrows():

            ticker = row["Ticker"]
            signal = row["Signal"]

            old = last[last["Ticker"] == ticker]

            # Dacă nu există înainte sau s-a schimbat semnalul
            if old.empty or old.iloc[0]["Signal"] != signal:

                alerts.append(row)

        # Dacă nu există alerte noi
        if len(alerts) == 0:

            print("📭 Nu există schimbări noi de semnal.")
            print("⏳ Aștept 15 minute...\n")

            time.sleep(900)
            continue

        # Construim mesajul Telegram
        message = "🚀 SIGNAL CHANGE ALERTS 🚀\n\n"

        log_rows = []

        for row in alerts:

            if row["Signal"] == "STRONG BUY":
                emoji = "🚀"

            elif row["Signal"] == "TAKE PROFIT":
                emoji = "⚠️"

            else:
                emoji = "📈"

            # Calculăm nivelele
            entry = round(row["Price"], 2)
            target = round(entry * 1.05, 2)
            stop_loss = round(entry * 0.97, 2)

            # Construim mesajul
            message += (
                f"{emoji} {row['Ticker']}\n"
                f"Entry: {entry}\n"
                f"Target: {target}\n"
                f"Stop Loss: {stop_loss}\n"
                f"RSI: {round(row['RSI'], 2)}\n"
                f"Score: {row['Score']}\n"
                f"Signal: {row['Signal']}\n\n"
            )

            # Salvăm în log
            log_rows.append({

                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": row["Ticker"],
                "Entry": entry,
                "Target": target,
                "Stop_Loss": stop_loss,
                "RSI": round(row["RSI"], 2),
                "Score": row["Score"],
                "Signal": row["Signal"]

            })

        # Trimitem pe Telegram
        try:

            response = requests.post(

                f"https://api.telegram.org/bot{TOKEN}/sendMessage",

                data={
                    "chat_id": CHAT_ID,
                    "text": message
                },

                timeout=10
            )

            if response.status_code == 200:

                print("✅ Telegram trimis cu succes.")

            else:

                print("⚠️ Telegram a răspuns cu eroare:")
                print(response.text)

        except Exception as e:

            print("❌ Nu am putut trimite pe Telegram:")
            print(e)

        # Salvăm istoricul alertelor
        log_df = pd.DataFrame(log_rows)

        if os.path.exists("alerts_log.csv"):

            log_df.to_csv(
                "alerts_log.csv",
                mode="a",
                header=False,
                index=False
            )

        else:

            log_df.to_csv(
                "alerts_log.csv",
                index=False
            )

        # Salvăm ultimele semnale
        important[["Ticker", "Signal"]].to_csv(
            "last_signals.csv",
            index=False
        )

        print("✅ Schimbare de semnal salvată.")
        print("⏳ Aștept 15 minute...\n")

    except Exception as e:

        print(f"❌ Eroare generală: {e}")
        print("⏳ Reîncerc în 15 minute...\n")

    # Așteptăm 15 minute
    time.sleep(900)