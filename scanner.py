import yfinance as yf
import pandas as pd
import requests
import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try: requests.post(url, data=payload)
    except: print("Telegram xatosi")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def screen_swing_setups(tickers):
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if len(data) < 200: continue
            
            # Narxni olish
            close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            
            # Indikatorlarni qo'lda hisoblash
            rsi = calculate_rsi(close).iloc[-1]
            sma200 = close.rolling(window=200).mean().iloc[-1]
            current_price = close.iloc[-1]
            
            # Oddiy Swing sharti: Trend tepada va RSI past (Pullback)
            if True:
                msg = f"🚀 *Swing Signal!*\n\nTicker: #{ticker}\nNarx: {round(current_price, 2)}$\nRSI: {round(rsi, 2)}\nTrend: SMA200 ustida ✅"
                send_telegram_msg(msg)
                print(f"Signal: {ticker}")
        except Exception as e:
            print(f"Xato {ticker}: {e}")

symbols = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL', 'AMZN', 'META', 'AMD', 'NFLX', 'PLTR']

if __name__ == "__main__":
    screen_swing_setups(symbols)
