import os, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = {
    "TXN":  {"name": "Texas Instruments",   "sector": "Semiconductors"},
    "PG":   {"name": "Procter & Gamble",    "sector": "Consumer"},
    "LOW":  {"name": "Lowe's Companies",    "sector": "Retail"},
    "DE":   {"name": "Deere & Company",     "sector": "Industrials"},
    "AMCR": {"name": "Amcor",               "sector": "Packaging"},
    "TM":   {"name": "Toyota Motor",        "sector": "Auto"},
    "EMR":  {"name": "Emerson Electric",    "sector": "Industrials"},
    "MDT":  {"name": "Medtronic",           "sector": "Healthcare"},
    "ABT":  {"name": "Abbott Laboratories", "sector": "Healthcare"},
    "PEP":  {"name": "PepsiCo",             "sector": "Consumer"},
}

CFG = {
    "bb_length": 20, "bb_mult": 2.0,
    "atr_length": 14, "atr_sl_mult": 2.0, "atr_tp_mult": 4.0,
    "direction": 0, "period": "3mo", "interval": "1d",
}

def compute_bb(close, length, mult):
    sma = close.rolling(length).mean()
    std = close.rolling(length).std(ddof=0)
    return sma, sma + mult * std, sma - mult * std

def compute_atr(high, low, close, length):
    prev = close.shift(1)
    tr = pd.concat([high-low,(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    return tr.rolling(length).mean()

def check_signal(ticker):
    try:
        df = yf.download(ticker, period=CFG["period"], interval=CFG["interval"],
                         auto_adjust=True, progress=False, threads=False)
        if df is None or len(df) < CFG["bb_length"] + 5:
            return None
        close = df["Close"].squeeze()
        high  = df["High"].squeeze()
        low   = df["Low"].squeeze()
        sma, upper, lower = compute_bb(close, CFG["bb_length"], CFG["bb_mult"])
        atr = compute_atr(high, low, close, CFG["atr_length"])
        c0,c1    = float(close.iloc[-1]), float(close.iloc[-2])
        lo0,lo1  = float(lower.iloc[-1]), float(lower.iloc[-2])
        up0,up1  = float(upper.iloc[-1]), float(upper.iloc[-2])
        sma0     = float(sma.iloc[-1])
        atr0     = float(atr.iloc[-1])
        date     = close.index[-1].strftime("%Y-%m-%d")
        crossover  = (c1 <= lo1) and (c0 > lo0)
        crossunder = (c1 >= up1) and (c0 < up0)
        if crossover and CFG["direction"] >= 0:
            sl = round(c0 - atr0*CFG["atr_sl_mult"], 2)
            tp = round(c0 + atr0*CFG["atr_tp_mult"], 2)
            return {"ticker":ticker,"side":"LONG 🟢","price":round(c0,2),
                    "sl":sl,"tp":tp,"rr":round(abs(tp-c0)/abs(c0-sl),2),
                    "sma":round(sma0,2),"atr":round(atr0,4),"date":date}
        if crossunder and CFG["direction"] <= 0:
            sl = round(c0 + atr0*CFG["atr_sl_mult"], 2)
            tp = round(c0 - atr0*CFG["atr_tp_mult"], 2)
            return {"ticker":ticker,"side":"SHORT 🔴","price":round(c0,2),
                    "sl":sl,"tp":tp,"rr":round(abs(tp-c0)/abs(sl-c0),2),
                    "sma":round(sma0,2),"atr":round(atr0,4),"date":date}
        return None
    except:
        return None

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message); return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id":TELEGRAM_CHAT_ID,"text":message,"parse_mode":"HTML"},timeout=10)
    except Exception as e:
        print(f"Telegram xatosi: {e}")

def main():
    print(f"BB Signal Bot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    signals = []
    for ticker, info in WATCHLIST.items():
        print(f"  → {ticker}...", end=" ")
        sig = check_signal(ticker)
        if sig:
            signals.append((sig, info))
            print(f"⭐ {sig['side']}")
        else:
            print("signal yo'q")

    if signals:
        for sig, info in signals:
            msg = (
                f"📊 <b>BB BREAKOUT SIGNAL</b>\n"
                f"🏷 <b>{sig['ticker']}</b> — {info['name']}\n"
                f"📂 {info['sector']} | 📅 {sig['date']}\n"
                f"{'─'*28}\n"
                f"📈 <b>{sig['side']}</b>\n"
                f"💵 Narx      : <b>${sig['price']}</b>\n"
                f"🛑 Stop-Loss : ${sig['sl']}\n"
                f"🎯 Take-Prof : ${sig['tp']}\n"
                f"⚖️ R/R       : 1:{sig['rr']}\n"
                f"📉 SMA(20)   : ${sig['sma']}\n"
                f"{'─'*28}\n"
                f"⚠️ Tavsiya emas. O'zingiz tahlil qiling."
            )
            print(msg)
            send_telegram(msg)
    else:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        msg = f"🔍 <b>BB Scan</b> — {now}\n✅ {len(WATCHLIST)} ticker tekshirildi\n💤 Signal yo'q"
        print(msg)
        send_telegram(msg)

if __name__ == "__main__":
    main()
