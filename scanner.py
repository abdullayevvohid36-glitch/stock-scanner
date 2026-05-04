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
        print("Hisobot yuborildi!")
    except Exception as e:
        print(f"Xato: {e}")

def screen_stocks(tickers):
    signals = []
    for ticker in tickers:
        try:
            # Ma'lumotlarni yuklash
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if len(data) < 200: continue
            
            close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            
            # SMA 200 ni hisoblash
            sma200 = close.rolling(window=200).mean().iloc[-1]
            current_price = close.iloc[-1]
            
            # RSI ni hisoblash
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # STRATEGIYA: Trend yuqorida (Price > SMA200) va Pullback (RSI < 45)
            # Test uchun RSI < 70 qilib turamiz, signal chiqsa keyin 45 ga tushirasiz
            if current_price > sma200 and rsi < 70:
                signals.append(f"🚀 {ticker}: Narx {round(current_price, 2)}$, RSI: {round(rsi, 2)}")
        except Exception as e:
            print(f"{ticker} da xato: {e}")
            continue
    
    if signals:
        full_msg = "Bugungi Swing savdo uchun topilgan aksiyalar:\n\n" + "\n".join(signals)
        send_email_msg("📈 Fond bozori hisoboti", full_msg)
    else:
        print("Hozircha mos keladigan aksiya topilmadi.")

# O'zingizga kerakli tikerlarni shu yerga qo'shing
symbols = ['NVDA', 'AMD', 'AAPL', 'MSFT', 'TSLA', 'GOOGL', 'AMZN', 'META', 'NFLX', 'PLTR']

if __name__ == "__main__":
    screen_stocks(symbols)
