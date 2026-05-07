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

# ── Shariah-screened tickers ───────────────────────────────────────────────────
TICKERS = [
    "NVDA", "AVGO", "QCOM", "AMAT", "LRCX", "KLAC", "MRVL", "TXN", "ASML", "TSM",
    "GLDM", "CRM", "NOW", "SRPT", "HLAL", "SNOW", "MDB", "HUBS", "WDC", "STX", "BURL",
    "CRWD", "PANW", "FTNT", "ZS", "S", "CYBR", "AAPL" "TSLA", "AMD", "NTRA", "SAP",
    "ARM", "SPRE", "IGDA", "VRSN", "HD", "LOW", "POWL", "BBY", "TMDX", "JCI", "SNPS",
    "ISRG", "ELV", "UNH", "GILD", "DXCM", "SHOP", "XLB", "ADSK", "ADI", "CDNS", "CSCO"
    "XOM", "CVX", "TJX", "ENPH", "FSLR", "ADBE", "TEAM", "ANET", "DOCU", "LLY", "JNJ",
    "UNP", "ROK", "CARR", "GNRC", "HIMS", "TMO", "PG", "ABT", "SYK", "MDT", "DHR", "EGN",
"VRTX", "HD", "LOW", "NKE", "SBUX", "EL", "ELF", "CL", "KMB", "SLB", "EOG", "VLO", "HAL",
]
# ══════════════════════════════════════════════════════════════════════════════
# INDIKATORLAR
# ══════════════════════════════════════════════════════════════════════════════

def compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs    = gain / loss
    return float(100 - (100 / (1 + rs)).iloc[-1])


def compute_atr(high: pd.Series, low: pd.Series,
                close: pd.Series, period: int = 14) -> float:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def compute_macd(close: pd.Series):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(sig.iloc[-1])


def compute_bb(close: pd.Series, period: int = 20):
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    bw    = ((upper - lower) / sma).iloc[-1]
    pct_b = ((close - lower) / (upper - lower)).iloc[-1]
    return float(bw), float(pct_b)


# ══════════════════════════════════════════════════════════════════════════════
# SUPPORT / RESISTANCE ZONALAR
# ══════════════════════════════════════════════════════════════════════════════

def find_sr_zones(high: pd.Series, low: pd.Series,
                  atr: float, lookback: int = 60, n_zones: int = 3):
    """
    So'nggi `lookback` kun ichidan swing high/low larni topib,
    eng kuchli Support va Resistance zonalarini qaytaradi.
    """
    highs = high.iloc[-lookback:]
    lows  = low.iloc[-lookback:]

    swing_highs = []
    swing_lows  = []

    # Har ikki tomonda 3 ta sham bilan solishtirish
    for i in range(3, len(highs) - 3):
        h = highs.iloc[i]
        if h == highs.iloc[i - 3: i + 4].max():
            swing_highs.append(float(h))

        l = lows.iloc[i]
        if l == lows.iloc[i - 3: i + 4].min():
            swing_lows.append(float(l))

    def cluster(levels):
        """Yaqin darajalarni ATR * 0.5 ichida klasterlash."""
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for lv in levels[1:]:
            if lv - clusters[-1][-1] < atr * 0.5:
                clusters[-1].append(lv)
            else:
                clusters.append([lv])
        return [sum(c) / len(c) for c in clusters]

    supports    = cluster(swing_lows)[-n_zones:]    # Eng yuqori support'lar
    resistances = cluster(swing_highs)[:n_zones]    # Eng quyi resistance'lar

    return supports, resistances


def check_support_bounce(price: float, close: pd.Series,
                         supports: list, resistances: list,
                         atr: float) -> dict:
    """
    Narx support zonaga yaqinmi va yuqoriga qaytayotganmi tekshiradi.

    Qaytaradi:
        near_support    : narx support dan 25% ichida
        near_resistance : narx resistance dan 75% ichida
        in_middle       : narx 25–75% oralig'ida (o'rtada)
        bounce          : support dan yuqoriga 3 sham tasdiq
        zone_position   : 0–100% (0 = support, 100 = resistance)
        zone_label      : emoji + matn
        nearest_support / nearest_resistance : eng yaqin qiymatlar
    """
    result = {
        "near_support":       False,
        "near_resistance":    False,
        "in_middle":          False,
        "bounce":             False,
        "nearest_support":    None,
        "nearest_resistance": None,
        "zone_position":      None,
        "zone_label":         "—",
    }

    if not supports or not resistances:
        return result

    below_sup = [s for s in supports    if s < price]
    above_res = [r for r in resistances if r > price]

    if not below_sup or not above_res:
        return result

    nearest_sup = max(below_sup)
    nearest_res = min(above_res)

    result["nearest_support"]    = round(nearest_sup, 2)
    result["nearest_resistance"] = round(nearest_res, 2)

    zone_range = nearest_res - nearest_sup
    if zone_range <= 0:
        return result

    # Narxning zona ichidagi foiz pozitsiyasi
    pos_pct = (price - nearest_sup) / zone_range * 100
    result["zone_position"] = round(pos_pct, 1)

    if pos_pct <= 25:
        result["near_support"] = True
        result["zone_label"]   = "🟢 Support zona"
    elif pos_pct >= 75:
        result["near_resistance"] = True
        result["zone_label"]      = "🔴 Resistance zona"
    else:
        result["in_middle"] = True
        result["zone_label"] = f"🟡 O'rtada ({pos_pct:.0f}%)"

    # Bounce tasdiqlanishi: so'nggi 3 sham yuqoriga yo'nalganmi?
    recent = close.iloc[-4:]
    bounce_up = (
        float(recent.iloc[-1]) > float(recent.iloc[-2]) and
        float(recent.iloc[-2]) > float(recent.iloc[-3]) and
        float(recent.iloc[-1]) > float(recent.iloc[0])
    )

    if result["near_support"] and bounce_up:
        result["bounce"] = True

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL SCORING (0–7)
# ══════════════════════════════════════════════════════════════════════════════

def score_ticker(price, ema20, ema50, sma200,
                 rsi, macd, sig, bb_bw, pct_b, vol_ratio) -> int:
    """
    Filtrlar (0 qaytarsa — signal yo'q):
      - RSI > 70  → overbought, o'tkazib yuboriladi
      - Narx < EMA50 → downtrend, o'tkazib yuboriladi

    Ballar:
      +2  Asosiy trend     : price > EMA20 > EMA50
      +1  Uzoq trend       : price > SMA200
      +1  Pullback zonasi  : RSI 40–60
      +1  MACD bullish     : MACD > Signal va > 0
      +1  Volume tasdiq    : Vol Ratio >= 1.0x
      +1  BB squeeze       : bandwidth < 0.12 va %B < 0.45
    """
    if rsi > 70:
        return 0   # Overbought
    if price < ema50:
        return 0   # Downtrend

    score = 0
    if price > ema20 > ema50:          score += 2
    if price > sma200:                 score += 1
    if 40 <= rsi <= 60:                score += 1
    if macd > sig and macd > 0:        score += 1
    if vol_ratio >= 1.0:               score += 1
    if bb_bw < 0.12 and pct_b < 0.45: score += 1
    return score


def rsi_label(rsi: float) -> str:
    if rsi > 70:  return "🔴 Overbought"
    if rsi > 60:  return "🟡 Yuqori"
    if rsi >= 40: return "🟢 Pullback"
    return              "🔵 Oversold"


# ══════════════════════════════════════════════════════════════════════════════
# HTML HISOBOT
# ══════════════════════════════════════════════════════════════════════════════

def build_html(rows: list[dict]) -> str:
    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    style = """
    <style>
      body  { font-family: Arial, sans-serif; font-size: 13px; color: #1a1a2e; }
      h2    { color: #1a1a2e; margin-bottom: 4px; }
      p     { margin: 4px 0 12px; color: #444; }
      table { border-collapse: collapse; width: 100%; }
      th    { background: #1a1a2e; color: #fff; padding: 9px 10px;
              text-align: left; white-space: nowrap; font-size: 12px; }
      td    { padding: 7px 10px; border-bottom: 1px solid #e8e8e8;
              white-space: nowrap; }
      tr:nth-child(even) td { background: #f9f9f9; }
      tr:hover td { background: #eef3ff; }

      /* Score rengi */
      .s7 { color: #6a0dad; font-weight: bold; }
      .s6 { color: #c0392b; font-weight: bold; }
      .s5 { color: #e67e22; font-weight: bold; }
      .s4 { color: #27ae60; font-weight: bold; }

      /* Ustunlar */
      .ticker { font-weight: bold; font-size: 14px; }
      .bounce { color: #27ae60; font-weight: bold; }
      .mid    { color: #e67e22; }
      .stop   { color: #c0392b; font-weight: bold; }
      .tp     { color: #27ae60; font-weight: bold; }
      .rr     { font-weight: bold; }
      .note   { color: #999; font-size: 11px; margin-top: 16px;
                border-top: 1px solid #eee; padding-top: 10px; }
    </style>
    """

    header = f"""
    <h2>📈 Swing Scanner — {date_str}</h2>
    <p>
      Jami signal: <b>{len(rows)}</b> &nbsp;|&nbsp;
      Filtrlar: RSI ≤ 70 · Narx &gt; EMA50 · Score ≥ 5/7 ·
      <b>Support zona + Bounce tasdiq</b>
    </p>
    """

    thead = """
    <table>
      <thead><tr>
        <th>#</th>
        <th>Ticker</th>
        <th>Narx</th>
        <th>Score</th>
        <th>RSI</th>
        <th>RSI holat</th>
        <th>EMA20</th>
        <th>EMA50</th>
        <th>Vol Ratio</th>
        <th>Support</th>
        <th>Resistance</th>
        <th>Zona pozitsiya</th>
        <th>Bounce</th>
        <th>Stop Loss</th>
        <th>Take Profit</th>
        <th>R:R</th>
      </tr></thead>
      <tbody>
    """

    tbody = ""
    for i, r in enumerate(rows, 1):
        sc   = r["score"]
        cls  = {7: "s7", 6: "s6", 5: "s5"}.get(sc, "s4")
        stars = "★" * sc + "☆" * (7 - sc)
        vol_icon = "✅" if r["vol_ratio"] >= 1.0 else "⚠️"
        bounce_cell = (
            '<span class="bounce">✅ Bounce</span>'
            if r["bounce"] else "—"
        )
        sup_val = f"${r['support']}"  if r["support"]    else "—"
        res_val = f"${r['resistance']}" if r["resistance"] else "—"

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
          <td>{vol_icon} {r['vol_ratio']:.2f}x</td>
          <td>{sup_val}</td>
          <td>{res_val}</td>
          <td>{r['zone_label']}</td>
          <td>{bounce_cell}</td>
          <td class="stop">${r['stop']:.2f}</td>
          <td class="tp">${r['tp']:.2f}</td>
          <td class="rr">{r['rr']:.2f}</td>
        </tr>
        """

    footer = """
      </tbody>
    </table>
    <p class="note">
      ⚠️ Bu faqat ma'lumot uchun. Investitsiya maslahati emas.<br>
      Tickers Shariah compliance asosida tanlangan.
    </p>
    """
    return style + header + thead + tbody + footer


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_USER
    msg["To"]      = RECEIVER_EMAIL
    msg["Subject"] = subject

    plain = (html_body
             .replace("<b>", "").replace("</b>", "")
             .replace("<br>", "\n").replace("<br/>", "\n"))
    msg.attach(MIMEText(plain,     "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("✅ Email yuborildi!")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail autentifikatsiya xatosi — App Password tekshiring")
    except Exception as e:
        print(f"❌ Email xato: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ASOSIY SCREENER
# ══════════════════════════════════════════════════════════════════════════════

def screen_stocks(tickers: list[str]) -> list[dict]:
    results  = []
    filtered = {"overbought": [], "downtrend": [], "middle": [], "low_score": []}

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

            # ── Dastlabki filtrlar ──────────────────────────────────────────
            if rsi > 70:
                filtered["overbought"].append(ticker)
                print(f"  🔴 {ticker}: RSI {rsi:.1f} — Overbought")
                continue

            if price < ema50:
                filtered["downtrend"].append(ticker)
                print(f"  📉 {ticker}: Narx < EMA50 — Downtrend")
                continue

            # ── Support / Resistance ────────────────────────────────────────
            supports, resistances = find_sr_zones(high, low, atr)
            sr = check_support_bounce(price, close, supports, resistances, atr)

            # O'rtada qolgan — kirish joyi emas
            if sr["in_middle"]:
                filtered["middle"].append(ticker)
                print(f"  🟡 {ticker}: O'rtada ({sr['zone_position']}%) — o'tkazildi")
                continue

            # ── Scoring ─────────────────────────────────────────────────────
            sc = score_ticker(
                price, ema20, ema50, sma200,
                rsi, macd, sig, bb_bw, pct_b, vol_ratio
            )

            # Bounce bonus (+1, max 7)
            if sr["bounce"]:
                sc = min(sc + 1, 7)

            # Minimum sifat chegarasi
            # Bounce bo'lsa 4 yetarli, bo'lmasa 5 kerak
            min_score = 4 if sr["bounce"] else 5
            if sc < min_score:
                filtered["low_score"].append(ticker)
                print(f"  ⚪ {ticker}: Score {sc} — yetarli emas")
                continue

            # ── Risk hisoblash ───────────────────────────────────────────────
            stop = round(price - 1.5 * atr, 2)
            tp   = round(price + 3.0 * atr, 2)
            rr   = round((tp - price) / (price - stop), 2) if price > stop else 0.0

            results.append({
                "ticker":     ticker,
                "price":      price,
                "score":      sc,
                "rsi":        rsi,
                "ema20":      ema20,
                "ema50":      ema50,
                "vol_ratio":  vol_ratio,
                "support":    sr["nearest_support"],
                "resistance": sr["nearest_resistance"],
                "zone_label": sr["zone_label"],
                "zone_pct":   sr["zone_position"],
                "bounce":     sr["bounce"],
                "stop":       stop,
                "tp":         tp,
                "rr":         rr,
            })

            bounce_tag = "✅ BOUNCE" if sr["bounce"] else ""
            print(f"  ✅ {ticker}: {sc}/7 | RSI:{rsi:.1f} | "
                  f"Vol:{vol_ratio:.2f}x | {sr['zone_label']} {bounce_tag}")

        except Exception as e:
            print(f"  ⚠️  {ticker}: {e}")

    # Score bo'yicha tartiblash (yuqoridan pastga)
    results.sort(key=lambda x: (x["score"], x["bounce"]), reverse=True)

    # Filtr xulosasi
    print(f"\n  📊 Filtr xulosasi:")
    print(f"     🔴 Overbought  : {len(filtered['overbought'])} — {', '.join(filtered['overbought']) or '—'}")
    print(f"     📉 Downtrend   : {len(filtered['downtrend'])} — {', '.join(filtered['downtrend']) or '—'}")
    print(f"     🟡 O'rtada     : {len(filtered['middle'])} — {', '.join(filtered['middle']) or '—'}")
    print(f"     ⚪ Past score  : {len(filtered['low_score'])} — {', '.join(filtered['low_score']) or '—'}")
    print(f"     ✅ Signal      : {len(results)}\n")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  📈 SWING SCANNER — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"  📋 Tickers: {len(TICKERS)} | Min score: 5/7 (bounce: 4/7)")
    print(f"  🔍 Filtrlar: RSI≤70 · Narx>EMA50 · Support zona · Bounce")
    print(f"{'='*60}\n")

    signals = screen_stocks(TICKERS)

    if signals:
        html = build_html(signals)
        subj = (f"📈 Swing Scanner — {len(signals)} signal "
                f"| {datetime.now().strftime('%d.%m.%Y')}")
        send_email(subj, html)
        print(f"📧 {len(signals)} signal emailga yuborildi.")
    else:
        msg = (
            "<p>Bugun <b>mos signal topilmadi.</b></p>"
            "<p>Sabablar: RSI &gt; 70, Downtrend, O'rtada, yoki Score &lt; 5.</p>"
        )
        send_email("📊 Swing Scanner — signal yo'q", msg)
        print("📭 Signal yo'q — email yuborildi.")
