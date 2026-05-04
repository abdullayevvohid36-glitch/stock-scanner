import yfinance as yf
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

def send_email_msg(subject, message):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("Email yuborildi!")
    except Exception as e:
        print(f"Xato: {e}")

def screen_stocks(tickers):
    signals = []
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if len(data) < 200: continue
            close = data['Close']
            # RSI va SMA hisoblash
            sma200 = close.rolling(window=200).mean().iloc[-1]
            current_price = close.iloc[-1]
            
            # Test uchun RSI o'rniga oddiy narx trendini tekshiramiz (Xabar borishi uchun)
            if current_price > 0: 
                signals.append(f"{ticker}: {round(current_price, 2)}$")
        except: continue
    
    if signals:
        send_email_msg("📈 Stock Scanner Test", "\n".join(signals))

symbols = ['AAPL', 'NVDA', 'TSLA', 'AMD', 'MSFT']
if __name__ == "__main__":
    screen_stocks(symbols)
