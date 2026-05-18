import yfinance as yf
import pandas as pd
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Email sozlamalari ──────────────────────────────────────────────────────────
EMAIL_USER     = os.getenv("EMAIL_USER", "")
EMAIL_PASS     = os.getenv("EMAIL_PASS", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

# ── Vaqt zonasi ───────────────────────────────────────────────────────────────
ET = ZoneInfo("America/New_York")

# ── Shariah-screened tickers ───────────────────────────────────────────────────
TICKERS = [
    "NVDA", "AVGO", "QCOM", "AMAT", "LRCX", "KLAC", "MRVL", "TXN", "ASML", "TSM",
    "GLDM", "CRM", "NOW", "SRPT", "HLAL", "SNOW", "MDB", "HUBS", "WDC", "STX", "BURL",
    "CRWD", "PANW", "FTNT", "ZS", "S", "CYBR", "AAPL", "TSLA", "AMD", "NTRA", "SAP",
    "ARM", "SPRE", "IGDA", "VRSN", "HD", "LOW", "POWL", "BBY", "TMDX", "JCI", "SNPS",
    "ISRG", "ELV", "UNH", "GILD", "DXCM", "SHOP", "XLB", "ADSK", "ADI", "CDNS", "CSCO",
    "XOM", "CVX", "TJX", "ENPH", "FSLR", "ADBE", "TEAM", "ANET", "DOCU", "LLY", "JNJ",
    "UNP", "ROK", "CARR", "GNRC", "HIMS", "TMO", "PG", "ABT", "SYK", "MDT", "DHR", "EGN",
    "VRTX", "LIN", "NKE", "SBUX", "EL", "ELF", "CL", "KMB", "SLB", "EOG", "VLO", "HAL",    
    "APD", "DD", "ECL", "ALB", "GE", "ETN", "EMR", "PH", "ITW", "V", "MA", "SPGI","MSCI",
    "SAP", "ULTA", "AZN", "RIO", "BHP", "UBER", "TTD", "HSY", "MCK", "UPS", "ORLY", "AZO",
    "IDXX", "ZTS", "CARR", "TT", "OTIS", "ROST", "PKG", "FAST", "ODFL",
]


# ══════════════════════════════════════════════════════════════════════════════
# 4H RESAMPLE
# ══════════════════════════════════════════════════════════════════════════════

def download_4h(ticker: str) -> pd.DataFrame:
    """
    yfinance 4H intervalini qo'llab-quvvatlamaydi.
    1H yuklab, 4H ga resample qilamiz.
    60 kun = ~97 ta 4H bar (6.5 soat/kun ÷ 4 = ~1.6 bar/kun).
    """
    df = yf.download(
        ticker,
        period="60d",
        interval="1h",
        progress=False,
        prepost=False,
    )
    if df.empty:
        return df

    # Multi-level columns → tekis
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 4H resample (US market: 09:30–16:00 ET)
    df4 = df.resample("4h", closed="left", label="left").agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna(subset=["Close"])

    return df4


# ══════════════════════════════════════════════════════════════════════════════
# BOZOR SESSIYASI
# ══════════════════════════════════════════════════════════════════════════════

def get_market_session() -> dict:
    now  = datetime.now(ET)
    hour = now.hour + now.minute / 60

    if now.weekday() >= 5:
        return {"name": "Weekend",     "emoji": "🔴", "extended": False,
                "label": "Bozor yopiq (Weekend)", "warning": ""}
    if 4.0 <= hour < 9.5:
        return {"name": "Pre-Market",  "emoji": "🌅", "extended": True,
                "label": "04:00–09:30 ET",
                "warning": "⚠️ Pre-Market: Likvidlik past. Regular ochilishni kuting."}
    elif 9.5 <= hour < 16.0:
        return {"name": "Regular",     "emoji": "🟢", "extended": False,
                "label": "09:30–16:00 ET", "warning": ""}
    elif 16.0 <= hour < 20.0:
        return {"name": "After-Hours", "emoji": "🌙", "extended": True,
                "label": "16:00–20:00 ET",
                "warning": "⚠️ After-Hours: Spread katta bo'lishi mumkin."}
    else:
        return {"name": "Yopiq",       "emoji": "🔴", "extended": False,
                "label": "20:00–04:00 ET", "warning": ""}


def get_extended_price(ticker: str) -> dict:
    result = {"ext_price": None, "ext_change": None}
    try:
        info       = yf.Ticker(ticker).fast_info
        ext_price  = getattr(info, "last_price",     None)
        prev_close = getattr(info, "previous_close", None)
        if ext_price:
            result["ext_price"] = round(float(ext_price), 2)
        if ext_price and prev_close and float(prev_close) > 0:
            result["ext_change"] = round(
                (float(ext_price) - float(prev_close)) / float(prev_close) * 100, 2
            )
    except Exception:
        pass
    return result


# ══════════════════════════════════════════════════════════════════════════════
# INDIKATORLAR (4H barlar ustida)
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
# SUPPORT / RESISTANCE ZONALAR (4H uchun moslashtirilgan)
# ══════════════════════════════════════════════════════════════════════════════

def find_sr_zones(high: pd.Series, low: pd.Series,
                  atr: float, lookback: int = 40, n_zones: int = 3):
    """
    4H uchun lookback=40 bar (~10 kun).
    1D da 60 kun edi → 4H da 40 bar taxminan o'xshash davr.
    """
    highs = high.iloc[-lookback:]
    lows  = low.iloc[-lookback:]

    swing_highs, swing_lows = [], []
    for i in range(3, len(highs) - 3):
        h = highs.iloc[i]
        if h == highs.iloc[i - 3: i + 4].max():
            swing_highs.append(float(h))
        l = lows.iloc[i]
        if l == lows.iloc[i - 3: i + 4].min():
            swing_lows.append(float(l))

    def cluster(levels):
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

    supports    = cluster(swing_lows)[-n_zones:]
    resistances = cluster(swing_highs)[:n_zones]
    return supports, resistances


def check_support_bounce(price: float, close: pd.Series,
                         supports: list, resistances: list,
                         atr: float, is_extended: bool = False) -> dict:
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

    pos_pct = (price - nearest_sup) / zone_range * 100
    result["zone_position"] = round(pos_pct, 1)

    sup_threshold = 30 if is_extended else 25
    res_threshold = 70 if is_extended else 75

    if pos_pct <= sup_threshold:
        result["near_support"] = True
        result["zone_label"]   = "🟢 Support zona"
    elif pos_pct >= res_threshold:
        result["near_resistance"] = True
        result["zone_label"]      = "🔴 Resistance zona"
    else:
        result["in_middle"] = True
        result["zone_label"] = f"🟡 O'rtada ({pos_pct:.0f}%)"

    # 4H bounce: oxirgi 3 bar yuqoriga qarab borishi
    recent    = close.iloc[-4:]
    bounce_up = (
        float(recent.iloc[-1]) > float(recent.iloc[-2]) and
        float(recent.iloc[-2]) > float(recent.iloc[-3]) and
        float(recent.iloc[-1]) > float(recent.iloc[0])
    )

    if result["near_support"]:
        result["bounce"] = True if is_extended else bounce_up

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL SCORING (0–7) — 4H uchun
# SMA200 o'rniga EMA50 > EMA20 trend tasdiq
# ══════════════════════════════════════════════════════════════════════════════

def score_ticker(price, ema20, ema50,
                 rsi, macd, sig, bb_bw, pct_b, vol_ratio) -> int:
    """
    4H da SMA200 yo'q (bar yetarli emas).
    O'rniga: price > ema50 > ema20 trend tasdiq ishlatiladi.
    Max score: 7
    """
    if rsi > 70:       return 0   # Overbought
    if price < ema50:  return 0   # Downtrend

    score = 0
    if price > ema20 > ema50:          score += 2   # Bullish alignment
    if ema50 > ema20 * 0.98:           score += 1   # EMA50 rising (proxy for trend)
    if 40 <= rsi <= 60:                score += 1   # Pullback zone
    if macd > sig and macd > 0:        score += 1   # MACD bullish
    if vol_ratio >= 1.0:               score += 1   # Volume confirmation
    if bb_bw < 0.12 and pct_b < 0.45: score += 1   # BB squeeze / low side
    return score


def rsi_label(rsi: float) -> str:
    if rsi > 70:  return "🔴 Overbought"
    if rsi > 60:  return "🟡 Yuqori"
    if rsi >= 40: return "🟢 Pullback"
    return              "🔵 Oversold"


# ══════════════════════════════════════════════════════════════════════════════
# HTML HISOBOT
# ══════════════════════════════════════════════════════════════════════════════

def build_html(rows: list[dict], session: dict) -> str:
    date_str = datetime.now(ET).strftime("%d.%m.%Y %H:%M ET")

    style = """
    <style>
      body  { font-family: Arial, sans-serif; font-size: 13px; color: #1a1a2e; }
      h2    { color: #1a1a2e; margin-bottom: 4px; }
      .sub  { margin: 4px 0 8px; color: #444; }
      .warn { background: #fff8e1; border-left: 4px solid #f9a825;
              padding: 8px 12px; margin-bottom: 12px; border-radius: 4px; }
      .badge { display:inline-block; padding:3px 10px; border-radius:12px;
               font-size:12px; font-weight:bold; margin-left:8px; }
      .pre  { background:#fff3e0; color:#e65100; }
      .reg  { background:#e8f5e9; color:#2e7d32; }
      .aft  { background:#e8eaf6; color:#283593; }
      .cls  { background:#fce4ec; color:#880e4f; }
      table { border-collapse:collapse; width:100%; }
      th    { background:#1a1a2e; color:#fff; padding:9px 10px;
              text-align:left; white-space:nowrap; font-size:12px; }
      td    { padding:7px 10px; border-bottom:1px solid #e8e8e8; white-space:nowrap; }
      tr:nth-child(even) td { background:#f9f9f9; }
      tr:hover td           { background:#eef3ff; }
      .s7 { color:#6a0dad; font-weight:bold; }
      .s6 { color:#c0392b; font-weight:bold; }
      .s5 { color:#e67e22; font-weight:bold; }
      .s4 { color:#27ae60; font-weight:bold; }
      .ticker { font-weight:bold; font-size:14px; }
      .bounce { color:#27ae60; font-weight:bold; }
      .stop   { color:#c0392b; font-weight:bold; }
      .tp     { color:#27ae60; font-weight:bold; }
      .rr     { font-weight:bold; }
      .note   { color:#999; font-size:11px; margin-top:16px;
                border-top:1px solid #eee; padding-top:10px; }
    </style>
    """

    badge_cls = {"Pre-Market": "pre", "Regular": "reg",
                 "After-Hours": "aft"}.get(session["name"], "cls")

    header = f"""
    <h2>📈 Swing Scanner 4H — {date_str}
      <span class="badge {badge_cls}">
        {session['emoji']} {session['name']} · {session['label']}
      </span>
    </h2>
    <p class="sub">Jami signal: <b>{len(rows)}</b> &nbsp;|&nbsp;
    Taymfreym: <b>4H</b> &nbsp;|&nbsp;
    Filtrlar: RSI ≤ 70 · Narx &gt; EMA50 · Score ≥ 5/7 · Support zona · Bounce</p>
    """

    warning_block = ""
    if session.get("warning"):
        warning_block = f'<div class="warn">{session["warning"]}</div>'

    thead = """
    <table><thead><tr>
      <th>#</th><th>Ticker</th><th>Close (4H)</th>
      <th>Ext Narx</th><th>Ext %</th>
      <th>Score</th><th>RSI (4H)</th><th>RSI holat</th>
      <th>EMA20</th><th>EMA50</th><th>Vol Ratio</th>
      <th>Support</th><th>Resistance</th><th>Zona</th><th>Bounce</th>
      <th>Stop Loss</th><th>Take Profit</th><th>R:R</th>
    </tr></thead><tbody>
    """

    tbody = ""
    for i, r in enumerate(rows, 1):
        sc    = r["score"]
        cls   = {7: "s7", 6: "s6", 5: "s5"}.get(sc, "s4")
        stars = "★" * sc + "☆" * (7 - sc)
        vol_icon = "✅" if r["vol_ratio"] >= 1.0 else "⚠️"

        ext_price_cell = f"<b>${r['ext_price']}</b>" if r["ext_price"] else "—"

        ext_change_cell = "—"
        if r["ext_change"] is not None:
            color = "#27ae60" if r["ext_change"] >= 0 else "#c0392b"
            sign  = "+" if r["ext_change"] >= 0 else ""
            ext_change_cell = (f'<span style="color:{color};font-weight:bold">'
                               f'{sign}{r["ext_change"]}%</span>')

        sup_val    = f"${r['support']}"    if r["support"]    else "—"
        res_val    = f"${r['resistance']}" if r["resistance"] else "—"
        bounce_cell = '<span class="bounce">✅ Bounce</span>' if r["bounce"] else "—"

        tbody += f"""
        <tr>
          <td>{i}</td>
          <td class="ticker">{r['ticker']}</td>
          <td>${r['price']:.2f}</td>
          <td>{ext_price_cell}</td>
          <td>{ext_change_cell}</td>
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
        </tr>"""

    footer = """
    </tbody></table>
    <p class="note">
      ⚠️ Bu faqat ma'lumot uchun. Investitsiya maslahati emas.<br>
      Taymfreym: 4H (1H resample). Bar soni: ~97 (60 kun).<br>
      SMA200 o'rniga EMA50 trend tasdiq ishlatiladi.<br>
      Pre-Market va After-Hours signallari regular sessiyada tasdiqlaning.<br>
      Tickers Shariah compliance asosida tanlangan.
    </p>"""

    return style + header + warning_block + thead + tbody + footer


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

def screen_stocks(tickers: list[str], session: dict) -> list[dict]:
    results  = []
    filtered = {
        "overbought": [], "downtrend":  [],
        "middle":     [], "low_score":  [], "resistance": [],
        "no_data":    [],
    }
    is_extended = session["extended"]

    for ticker in tickers:
        try:
            # ── 4H ma'lumot yukla ──────────────────────────────────────────
            df = download_4h(ticker)

            if df is None or len(df) < 60:
                filtered["no_data"].append(ticker)
                print(f"  ⚠️  {ticker}: Yetarli 4H bar yo'q ({len(df) if df is not None else 0})")
                continue

            close = df["Close"].squeeze()
            high  = df["High"].squeeze()
            low   = df["Low"].squeeze()
            vol   = df["Volume"].squeeze()

            price  = float(close.iloc[-1])
            ema20  = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            ema50  = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            rsi    = compute_rsi(close)
            atr    = compute_atr(high, low, close)
            macd, sig    = compute_macd(close)
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

            # ── Extended hours narx ─────────────────────────────────────────
            ext_data    = {"ext_price": None, "ext_change": None}
            check_price = price

            if is_extended:
                ext_data    = get_extended_price(ticker)
                check_price = ext_data.get("ext_price") or price

            # ── Support / Resistance (4H lookback=40) ──────────────────────
            supports, resistances = find_sr_zones(high, low, atr, lookback=40)
            sr = check_support_bounce(
                check_price, close, supports, resistances,
                atr, is_extended=is_extended
            )

            if sr["in_middle"]:
                filtered["middle"].append(ticker)
                print(f"  🟡 {ticker}: O'rtada ({sr['zone_position']}%) — o'tkazildi")
                continue

            if sr["near_resistance"]:
                filtered["resistance"].append(ticker)
                print(f"  🔴 {ticker}: Resistance zonada — o'tkazildi")
                continue

            # ── Scoring (SMA200 yo'q, EMA50 trend tasdiq) ──────────────────
            sc = score_ticker(
                price, ema20, ema50,
                rsi, macd, sig, bb_bw, pct_b, vol_ratio
            )

            if sr["bounce"]:
                sc = min(sc + 1, 7)

            min_score = 4 if (sr["bounce"] or is_extended) else 5
            if sc < min_score:
                filtered["low_score"].append(ticker)
                print(f"  ⚪ {ticker}: Score {sc} — yetarli emas")
                continue

            # ── Risk hisoblash (4H ATR) ─────────────────────────────────────
            base = check_price
            stop = round(base - 1.5 * atr, 2)
            tp   = round(base + 3.0 * atr, 2)
            rr   = round((tp - base) / (base - stop), 2) if base > stop else 0.0

            results.append({
                "ticker":     ticker,
                "price":      price,
                "ext_price":  ext_data["ext_price"],
                "ext_change": ext_data["ext_change"],
                "score":      sc,
                "rsi":        rsi,
                "ema20":      ema20,
                "ema50":      ema50,
                "vol_ratio":  vol_ratio,
                "support":    sr["nearest_support"],
                "resistance": sr["nearest_resistance"],
                "zone_label": sr["zone_label"],
                "bounce":     sr["bounce"],
                "stop":       stop,
                "tp":         tp,
                "rr":         rr,
            })

            ext_tag    = f"| Ext:${ext_data['ext_price']}" if ext_data["ext_price"] else ""
            bounce_tag = "✅ BOUNCE" if sr["bounce"] else ""
            print(f"  ✅ {ticker}: {sc}/7 | RSI(4H):{rsi:.1f} | "
                  f"Vol:{vol_ratio:.2f}x | {sr['zone_label']} {ext_tag} {bounce_tag}")

        except Exception as e:
            print(f"  ⚠️  {ticker}: {e}")

    results.sort(key=lambda x: (x["score"], x["bounce"]), reverse=True)

    print(f"\n  📊 Filtr xulosasi (4H):")
    print(f"     🔴 Overbought  : {len(filtered['overbought'])} — {', '.join(filtered['overbought'])}")
    print(f"     📉 Downtrend   : {len(filtered['downtrend'])} — {', '.join(filtered['downtrend'])}")
    print(f"     🟡 O'rtada     : {len(filtered['middle'])} — {', '.join(filtered['middle'])}")
    print(f"     🔴 Resistance  : {len(filtered['resistance'])} — {', '.join(filtered['resistance'])}")
    print(f"     ⚪ Low Score   : {len(filtered['low_score'])} — {', '.join(filtered['low_score'])}")
    print(f"     ❌ No Data     : {len(filtered['no_data'])} — {', '.join(filtered['no_data'])}")
    print(f"     ✅ Signal      : {len(results)}")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    session = get_market_session()
    print(f"\n{'='*60}")
    print(f"📈 Swing Scanner 4H — {datetime.now(ET).strftime('%d.%m.%Y %H:%M ET')}")
    print(f"   Sessiya: {session['emoji']} {session['name']} ({session['label']})")
    if session["warning"]:
        print(f"   {session['warning']}")
    print(f"{'='*60}\n")

    results = screen_stocks(TICKERS, session)

    print(f"\n{'='*60}")
    print(f"✅ Jami signal: {len(results)}")
    print(f"{'='*60}\n")

    if not results:
        print("📭 Signal topilmadi.")
        return

    html    = build_html(results, session)
    subject = (f"📈 Swing Scanner 4H — {len(results)} signal | "
               f"{datetime.now(ET).strftime('%d.%m.%Y %H:%M')}")

    if EMAIL_USER and EMAIL_PASS and RECEIVER_EMAIL:
        send_email(subject, html)
    else:
        print("⚠️  Email sozlanmagan. EMAIL_USER/EMAIL_PASS/RECEIVER_EMAIL env belgilang.")
        # Lokal saqlash
        out = f"scanner_4h_{datetime.now(ET).strftime('%Y%m%d_%H%M')}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"💾 HTML saqlandi: {out}")


if __name__ == "__main__":
    main()
