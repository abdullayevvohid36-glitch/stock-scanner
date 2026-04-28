import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram yuborishda xato: {e}")

def screen_swing_setups(tickers):
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="2y", interval="1d", progress=False)
            if data.empty or len(data) < 200: continue
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data['RSI'] = ta.rsi(data['Close'], length=14)
            data['SMA_200'] = ta.sma(data['Close'], length=200)
            data['EMA_20'] = ta.ema(data['Close'], length=20)
            data['EMA_50'] = ta.ema(data['Close'], length=50)
            data['Avg_Vol'] = data['Volume'].rolling(window=20).mean()

            last_row = data.iloc[-1]
            current_price = float(last_row['Close'])
            rsi_val = round(float(last_row['RSI']), 2)
            vol_ratio = round(last_row['Volume'] / last_row['Avg_Vol'], 2)

            if (current_price > last_row['SMA_200'] and rsi_val < 45 and 
                last_row['EMA_20'] > last_row['EMA_50'] and vol_ratio > 1.1):
                msg = (f"🚀 *Yangi Swing Signal!*\n\nTicker: #{ticker}\nNarx: {round(current_price, 2)}$\nRSI: {rsi_val}\nHajm koeff: {vol_ratio}")
                send_telegram_msg(msg)
        except Exception as e:
            print(f"{ticker} xato: {e}")

symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'AMD', 'NFLX', 'DE', 'PLTR', 'UBER', 'CAT', 'GS', 'BA'] # Qisqaroq ro'yxat test uchun

if __name__ == "__main__":
    screen_swing_setups(symbols)
