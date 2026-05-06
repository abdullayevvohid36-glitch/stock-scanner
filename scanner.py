import yfinance as yf
import pandas as pd
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Email sozlamalari ──────────────────────────────────────────────────────────
EMAIL_USER     = os.getenv("EMAIL_USER", "")
EMAIL_PASS     = os.getenv("EMAIL_PASS", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_USER
    msg["To"]      = RECEIVER_EMAIL
    msg["Subject"] = subject
    plain = html_body.replace("<b>","").replace("</b>","").replace("<br>","\n")
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("✅ Email yuborildi!")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail autentifikatsiya xatosi")
    except Exception as e:
        print(f"❌ Xato: {e}")

# ── Shariah-screened tickers ───────────────────────────────────────────────────
TICKERS = [
    "NVDA", "AVGO", "QCOM", "AMAT", "LRCX", "KLAC", "MRVL", "TXN", "ASML", "TSM", "TSLA",
    "AMD", "MU", "ADI", "CDNS", "ADBE", "SRPT", "PANW", "GILD", "CSCO", "NOW", "TEAM", "VRSN"
    "TJX", "CRM", "NOW", "WDAY", "UNP", "SNOW", "MDB", "HUBS",
    "CRWD", "PANW", "FTNT", "ZS", "S", "CYBR",
    "AAPL", "JCI", "BBY", "TGT", "HD", "LOW",
    "ISRG", "ELV", "UNH", "PG", "DXCM",
    "XOM", "CVX", "NEE", "ENPH", "FSLR",
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

# ── Signal scoring (0–7) ───────────────────────────────────────────────────────
def score_ticker(price, ema20, ema50, sma200,
                 rsi, macd, sig, bb_bw, pct_b, vol_ratio) -> int:

    # ❌ Overbought filtr — darhol chiqarib tashla
    if rsi > 70:
        return 0

    # ❌ Downtrend filtr — narx EMA50 dan past
    if price < ema50:
        return 0

    score = 0

    # 1. Asosiy trend: EMA20 > EMA50, narx ham ustida (+2)
    if price > ema20 > ema50:
        score += 2

    # 2. Uzoq muddatli trend: narx SMA200 dan yuqori (+1)
    if price > sma200:
        score += 1

    # 3. Pullback zonasi: RSI 40–60 (+1)
    if 40 <= rsi <= 60:
        score += 1

    # 4. MACD bullish kesishma (+1)
    if macd > sig and macd > 0:
        score += 1

    # 5. Volume tasdiq: o'rtachadan yuqori (+1)
    if vol_ratio >= 1.0:
        score += 1

    # 6. BB squeeze: narx siqilmoqda, pastda joylashgan (+1)
    if bb_bw < 0.12 and pct_b < 0.45:
        score += 1

    return score

# ── RSI holat belgisi ──────────────────────────────────────────────────────────
def rsi_label(rsi: float) -> str:
    if rsi > 70:   return "🔴 Overbought"
    if rsi > 60:   return "🟡 Yuqori"
    if rsi >= 40:  return "🟢 Pullback"
    return              "🔵 Oversold"

# ── HTML jadval ───────────────────────────────────────────────────────────────
def build_html(rows: list[dict]) -> str:
    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    style = """
    <style>
      body  { font-family: Arial, sans-serif; font-size: 13px; color: #222; }
      h2    { color: #1a1a2e; margin-bottom: 4px; }
      p     { margin: 4px 0 12px; }
      table { border-collapse: collapse; width: 100%; min-width: 700px; }
      th    { background: #1a1a2e; color: #fff; padding: 9px 11px; text-align: left; white-space: nowrap; }
      td    { padding: 7px 11px; border-bottom: 1px solid #e8e8e8; white-space: nowrap; }
      tr:nth-child(even) td { background: #f9f9f9; }
      tr:hover td  { background: #eef3ff; }
      .s7  { color: #7b2d8b; font-weight: bold; }
      .s6  { color: #c0392b; font-weight: bold; }
      .s5  { color: #e67e22; font-weight: bold; }
      .s4  { color: #27ae60; }
      .ticker { font-weight: bold; color: #1a1a2e; font-size: 14px; }
      .stop   { color: #c0392b; font-weight: bold; }
      .tp     { color: #27ae60; font-weight: bold; }
      .rr     { font-weight: bold; }
      .note   { color: #999; font-size: 11px; margin-top: 16px; }
    </style>
    """

    header = f"""
    <h2>📈 Swing Scanner — {date_str}</h2>
    <p>Jami signal: <b>{len(rows)}</b> &nbsp;|&nbsp; Minimum score: <b>5/7</b>
       &nbsp;|&nbsp; Filtrlar: RSI ≤ 70, Narx > EMA50, Vol ≥ 1.0x</p>
    """

    thead = """
    <table>
      <thead><tr>
        <th>#</th><th>Ticker</th><th>Narx</th>
        <th>Score</th><th>RSI</th><th>RSI holat</th>
        <th>EMA20</th><th>EMA50</th><th>Vol Ratio</th>
        <th>Stop Loss</th><th>Take Profit</th><th>R:R</th>
      </tr></thead>
      <tbody>
    """

    tbody = ""
    for i, r in enumerate(rows, 1):
        sc  = r["score"]
        cls = {7:"s7", 6:"s6", 5:"s5"}.get(sc, "s4")
        stars = "★" * sc + "☆" * (7 - sc)
        tbody += f"""
        <tr>
          <td>{i}</td>
          <td class="ticker">{r['ticker']}</td>
          <td>${r['price']:.2f}</td>
          <td class="{cls}">{sc}/7 {stars}</td>
          <td>{r['rsi']:.1f}</td>
          <td>{rsi_label(r['rsi'])}</td>
          <td>{r['ema20']:.2f}</td>
          <td>{r['ema50']:.2f}</td>
          <td>{"✅" if r['vol_ratio']>=1.0 else "⚠️"} {r['vol_ratio']:.2f}x</td>
          <td class="stop">${r['stop']:.2f}</td>
          <td class="tp">${r['tp']:.2f}</td>
          <td class="rr">{r['rr']:.2f}</td>
        </tr>
        """

    footer = """
      </tbody>
    </table>
    <p class="note">⚠️ Bu faqat ma'lumot uchun. Investitsiya maslahati emas.
    Shariah compliance tekshirilgan tickers.</p>
    """
    return style + header + thead + tbody + footer

# ── Asosiy screener ────────────────────────────────────────────────────────────
def screen_stocks(tickers: list[str]) -> list[dict]:
    results   = []
    skipped   = []

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
            vol_ratio = float(vol.iloc[-1]) / vol_avg if vol_avg > 0 else 0.0

            sc = score_ticker(
                price, ema20, ema50, sma200,
                rsi, macd, sig, bb_bw, pct_b, vol_ratio
            )

            # RSI > 70 yoki past trend — skip
            if sc == 0:
                reason = "RSI>70" if rsi > 70 else "Downtrend"
                skipped.append(f"{ticker}({reason})")
                continue

            # Minimum sifat chegarasi
            if sc < 5:
                continue

            stop = round(price - 1.5 * atr, 2)
            tp   = round(price + 3.0 * atr, 2)
            rr   = round((tp - price) / (price - stop), 2) if price > stop else 0.0

            results.append({
                "ticker": ticker, "price": price, "score": sc,
                "rsi": rsi, "ema20": ema20, "ema50": ema50,
                "vol_ratio": vol_ratio, "stop": stop, "tp": tp, "rr": rr,
            })
            print(f"  ✅ {ticker}: {sc}/7 | RSI:{rsi:.1f} | Vol:{vol_ratio:.2f}x")

        except Exception as e:
            print(f"  ⚠️  {ticker}: {e}")

    # Score bo'yicha tartiblash
    results.sort(key=lambda x: x["score"], reverse=True)

    if skipped:
        print(f"\n  🚫 Filtrlangan: {', '.join(skipped)}")

    return results

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔍 {len(TICKERS)} ticker tekshirilmoqda...")
    print(f"📋 Filtrlar: RSI ≤ 70 | Narx > EMA50 | Score ≥ 5/7\n")

    signals = screen_stocks(TICKERS)

    if signals:
        html = build_html(signals)
        subj = f"📈 Swing Scanner — {len(signals)} signal | {datetime.now().strftime('%d.%m.%Y')}"
        send_email(subj, html)
        print(f"\n📧 {len(signals)} signal emailga yuborildi.")
    else:
        msg  = "<p>Bugun <b>mos signal topilmadi</b> (RSI > 70 yoki score < 5).</p>"
        send_email("📊 Swing Scanner — signal yo'q", msg)
        print("\n📭 Signal yo'q — email yuborildi.")
