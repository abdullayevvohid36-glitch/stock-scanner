import yfinance as yf
import pandas as pd
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Email sozlamalari ──────────────────────────────────────────────────────────
EMAIL_USER     = os.getenv("EMAIL_USER", "sizning@gmail.com")
EMAIL_PASS     = os.getenv("EMAIL_PASS", "app_parol")       # Gmail App Password
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "qabul@gmail.com")

def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_USER
    msg["To"]      = RECEIVER_EMAIL
    msg["Subject"] = subject

    # HTML + plain text (ikki versiya)
    plain = html_body.replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("✅ Email yuborildi!")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail autentifikatsiya xatosi — App Password tekshiring")
    except smtplib.SMTPException as e:
        print(f"❌ SMTP xato: {e}")
    except Exception as e:
        print(f"❌ Umumiy xato: {e}")

# ── Tickers (Shariah screened) ─────────────────────────────────────────────────
TICKERS = [
    # Semiconductors
    "NVDA", "AVGO", "QCOM", "AMAT", "LRCX", "KLAC", "MRVL", "TXN", "ASML", "TSM",
    # SaaS & Cloud
    "MSFT", "CRM", "NOW", "WDAY", "DDOG", "SNOW", "MDB", "HUBS",
    # Cybersecurity
    "CRWD", "PANW", "FTNT", "ZS", "S", "CYBR",
    # Consumer & Retail
    "AAPL", "AMZN", "COST", "TGT", "HD", "LOW",
    # Healthcare
    "ISRG", "ELV", "UNH", "VEEV", "DXCM",
    # Energy (Halal)
    "XOM", "CVX", "NEE", "ENPH", "FSLR",
    # Industrials
    "HON", "ROK", "CARR", "GNRC", "AXON",
]

# ── Indikatorlar ───────────────────────────────────────────────────────────────
def compute_rsi(close: pd.Series, period=14) -> float:
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs    = gain / loss
    return float(100 - (100 / (1 + rs)).iloc[-1])

def compute_atr(high, low, close, period=14) -> float:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])

def compute_macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(sig.iloc[-1])

def compute_bb(close: pd.Series, period=20):
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    bw    = ((upper - lower) / sma).iloc[-1]
    pct_b = ((close - lower) / (upper - lower)).iloc[-1]
    return float(bw), float(pct_b)

# ── Signal scoring ─────────────────────────────────────────────────────────────
def score_ticker(price, ema20, ema50, sma200, rsi, macd, sig, bb_bw, pct_b, vol_ratio) -> int:
    score = 0
    if price > ema20 > ema50:   score += 2   # Asosiy trend
    if price > sma200:          score += 1   # Uzoq muddatli trend
    if 40 <= rsi <= 55:         score += 1   # Pullback zonasi
    if macd > sig and macd > 0: score += 1   # MACD bullish
    if vol_ratio >= 1.2:        score += 1   # Volume tasdiq
    if bb_bw < 0.1 and pct_b < 0.4: score += 1  # BB squeeze
    return score

# ── HTML jadval ───────────────────────────────────────────────────────────────
def build_html_table(rows: list[dict]) -> str:
    style = """
    <style>
        body { font-family: Arial, sans-serif; font-size: 14px; }
        h2   { color: #1a1a2e; }
        table { border-collapse: collapse; width: 100%; }
        th   { background: #1a1a2e; color: white; padding: 8px 12px; text-align: left; }
        td   { padding: 7px 12px; border-bottom: 1px solid #e0e0e0; }
        tr:nth-child(even) { background: #f7f7f7; }
        .score5 { color: #c0392b; font-weight: bold; }
        .score4 { color: #e67e22; font-weight: bold; }
        .score3 { color: #27ae60; }
        .buy    { color: #27ae60; font-weight: bold; }
    </style>
    """

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    header = f"<h2>📈 Swing Scanner — {date_str}</h2><p>Jami signal: <b>{len(rows)}</b></p>"

    thead = """
    <table>
      <thead>
        <tr>
          <th>#</th><th>Ticker</th><th>Narx</th><th>Score</th>
          <th>RSI</th><th>EMA20</th><th>EMA50</th><th>Vol Ratio</th>
          <th>Stop Loss</th><th>Take Profit</th><th>R:R</th>
        </tr>
      </thead>
      <tbody>
    """

    tbody = ""
    for i, r in enumerate(rows, 1):
        sc = r["score"]
        cls = "score5" if sc >= 5 else ("score4" if sc == 4 else "score3")
        stars = "★" * sc + "☆" * (7 - sc)
        tbody += f"""
        <tr>
          <td>{i}</td>
          <td class="buy"><b>{r['ticker']}</b></td>
          <td>${r['price']:.2f}</td>
          <td class="{cls}">{sc}/7 {stars}</td>
          <td>{r['rsi']:.1f}</td>
          <td>{r['ema20']:.2f}</td>
          <td>{r['ema50']:.2f}</td>
          <td>{r['vol_ratio']:.2f}x</td>
          <td style="color:#c0392b">${r['stop']:.2f}</td>
          <td style="color:#27ae60">${r['tp']:.2f}</td>
          <td><b>{r['rr']:.2f}</b></td>
        </tr>
        """

    tfoot = "</tbody></table>"
    footer = "<br><p style='color:gray;font-size:12px'>⚠️ Bu faqat ma'lumot uchun. Investitsiya maslahati emas.</p>"

    return style + header + thead + tbody + tfoot + footer

# ── Screener ───────────────────────────────────────────────────────────────────
def screen_stocks(tickers: list[str]) -> list[dict]:
    results = []

    for ticker in tickers:
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if len(df) < 200:
                continue

            close = df["Close"].squeeze()
            high  = df["High"].squeeze()
            low   = df["Low"].squeeze()
            vol   = df["Volume"].squeeze()

            price     = float(close.iloc[-1])
            ema20     = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            ema50     = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            sma200    = float(close.rolling(200).mean().iloc[-1])
            rsi       = compute_rsi(close)
            atr       = compute_atr(high, low, close)
            macd, sig = compute_macd(close)
            bb_bw, pct_b = compute_bb(close)

            vol_avg   = float(vol.rolling(20).mean().iloc[-1])
            vol_ratio = float(vol.iloc[-1]) / vol_avg if vol_avg > 0 else 0

            sc = score_ticker(price, ema20, ema50, sma200, rsi, macd, sig, bb_bw, pct_b, vol_ratio)

            if sc < 4:
                continue

            stop = round(price - 1.5 * atr, 2)
            tp   = round(price + 3.0 * atr, 2)
            rr   = round((tp - price) / (price - stop), 2) if price > stop else 0

            results.append({
                "ticker": ticker, "price": price, "score": sc,
                "rsi": rsi, "ema20": ema20, "ema50": ema50,
                "vol_ratio": vol_ratio, "stop": stop, "tp": tp, "rr": rr,
            })
            print(f"  ✅ {ticker}: {sc}/7")

        except Exception as e:
            print(f"  ⚠️  {ticker}: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔍 {len(TICKERS)} ticker tekshirilmoqda...")
    signals = screen_stocks(TICKERS)

    if signals:
        html  = build_html_table(signals)
        subj  = f"📈 Swing Scanner — {len(signals)} signal | {datetime.now().strftime('%d.%m.%Y')}"
        send_email(subj, html)
    else:
        send_email(
            "📊 Swing Scanner — signal yo'q",
            "<p>Bugun mos signal topilmadi.</p>"
        )
