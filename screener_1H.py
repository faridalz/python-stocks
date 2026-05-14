"""
=============================================================
  CONFLUENCE SCREENER — 1 Saatlıq Şam
  Amerika Səhmləri + Kripto
=============================================================
  İndikatorlar:
    • EMA 9 / 21 / 50  → Trend istiqaməti
    • RSI 14            → Momentum (30/50/70)
    • MACD 12/26/9      → Crossover + histogram
    • Həcm              → 20 periyod ortalamasına görə təsdiq

  ALIŞ Siqnalı  : 3/4 və ya 4/4 indikator bullish istiqamətdə
  SATIŞ Siqnalı : 3/4 və ya 4/4 indikator bearish istiqamətdə

  Quraşdırma:
    pip install yfinance pandas numpy tqdm

  İstifadə:
    python confluence_screener.py

  Email üçün mühit dəyişənləri (.env və ya GitHub Secrets):
    EMAIL_SENDER   → göndərən Gmail ünvanı
    EMAIL_PASSWORD → Gmail App Password (16 hərf)
    EMAIL_RECEIVER → alan email ünvanı
=============================================================
"""

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─── PARAMETRLƏR ─────────────────────────────────────────────
WORKERS         = 20       # Paralel thread sayı
BARS            = 200      # Neçə saatlıq şam çəkilsin (minimum 60 tövsiyə olunur)
MIN_SCORE       = 3        # Neçə indikator eyni istiqamətdə olmalıdır (3 və ya 4)
VOL_MULTIPLIER  = 1.20     # Həcm ortalamanın neçə qatı olmalıdır (%20 artıq)

# EMA periyodları
EMA_FAST   = 9
EMA_MID    = 21
EMA_SLOW   = 50

# RSI
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_MID        = 50
RSI_OVERBOUGHT = 70

# MACD
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# Həcm MA
VOL_PERIOD = 20
# ─────────────────────────────────────────────────────────────

# ── Səhm Siyahısı ─────────────────────────────────────────────
STOCK_TICKERS = [
    # Mega Cap Tech
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","ORCL","CRM",
    "ADBE","AMD","QCOM","TXN","INTC","AMAT","LRCX","KLAC","SNPS","CDNS",
    "MU","MCHP","NXPI","FTNT","PANW","CRWD","NOW","SNOW","PLTR","INTU",
    "ANET","CTSH","AKAM","EPAM","NET","DDOG","ZS","WDAY","APP","ADSK",
    "ARM","MRVL","ON","SMCI","TEAM","VRSK","TTD","PYPL","HUBS","MDB",
    "OKTA","VEEV","GTLB","MNDY","MELI","PDD","SE","SHOP","SQ","COIN",
    "HOOD","SOFI","UPST","AFRM","DASH","UBER","LYFT","ABNB","BKNG","ROKU",
    # Maliyyə
    "JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP","V","MA","COF",
    "USB","PNC","TFC","MTB","CFG","HBAN","KEY","RF","FITB","STT","BK",
    "NTRS","CME","ICE","NDAQ","SPGI","MCO","MSCI","FIS","GPN","AMP",
    "PRU","MET","AFL","ALL","TRV","PGR","CB","HIG","RJF","ACGL","WRB",
    "RYAN","AON","AJG","BRO","MKL","AFG",
    # Səhiyyə
    "UNH","JNJ","LLY","ABBV","MRK","PFE","TMO","ABT","DHR","BMY","AMGN",
    "GILD","REGN","VRTX","ISRG","BSX","MDT","EW","SYK","ZTS","IDXX",
    "DXCM","PODD","ALGN","RVTY","IQV","LH","DGX","CRL","TECH","HSIC",
    "VTRS","MRNA","BIIB","INCY","ALNY","MOH","CNC","ELV","HUM","CVS","CI",
    # İstehlak & Pərakəndə
    "WMT","PG","KO","PEP","COST","MCD","PM","MO","CL","MDLZ","KMB","GIS",
    "CPB","CAG","HRL","TSN","MKC","CLX","CHD","EL","KR","TGT","DLTR","DG",
    "ULTA","ROST","TJX","BBY","HD","LOW","ORLY","AZO","TSCO","NKE","LULU",
    "TPR","RL","SBUX","CMG","YUM","DPZ","QSR",
    # Enerji
    "XOM","CVX","COP","EOG","SLB","OXY","MPC","VLO","PSX","DVN","FANG",
    "APA","HAL","BKR","OKE","WMB","KMI","LNG","EQT","TRGP","CNX","RRC","AR",
    # Sənaye & Aviasiya
    "HON","GE","RTX","LMT","NOC","GD","BA","TDG","HWM","AXON","LDOS",
    "CAT","DE","EMR","ETN","ITW","ROK","DOV","PH","AME","ROP","FAST","GWW",
    "MSI","HUBB","GNRC","XYL","UPS","FDX","UNP","NSC","CSX","WAB","TT",
    "CARR","OTIS","JCI","EXPD","JBHT","XPO","ODFL","SAIA",
    # Daşınmaz Əmlak & Kommunal
    "PLD","AMT","EQIX","CCI","SPG","O","WELL","PSA","EXR","AVB","VICI",
    "NEE","DUK","SO","AEP","EXC","SRE","ED","PEG","XEL","NRG","VST","CEG",
    # Material & Rabitə
    "LIN","APD","ECL","SHW","PPG","NEM","FCX","NUE","STLD","VMC","MLM",
    "NFLX","DIS","CMCSA","T","VZ","CHTR","TMUS","WBD","FOX","NYT","OMC",
    "TTWO","EA","RBLX","MTCH","PINS","SNAP","SPOT","LYV",
    # Avtomobil & Əyləncə
    "GM","F","RIVN","LCID","NIO","LI","XPEV","DAL","UAL","LUV","AAL",
    "MAR","HLT","CCL","RCL","NCLH","DKNG","MGM","WYNN","LVS","CZR",
    # Müxtəlif
    "BRK-B","MMM","ITW","EMR","ROP","AME","SWK","SNA","ADP","PAYX","FICO",
    "GDDY","MANH","HPQ","HPE","DELL","WDC","STX","NTAP","PSTG","NTNX",
    "ENPH","SEDG","FSLR","BE","PLUG","MPWR","SWKS","QRVO","LITE",
]

# ── Kripto Siyahısı ───────────────────────────────────────────
CRYPTO_TICKERS = [
    "BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD","DOGE-USD","ADA-USD",
    "AVAX-USD","LINK-USD","DOT-USD","MATIC-USD","UNI-USD","LTC-USD","BCH-USD",
    "ATOM-USD","XLM-USD","ALGO-USD","VET-USD","ICP-USD","FIL-USD","NEAR-USD",
    "APT-USD","ARB-USD","OP-USD","INJ-USD","SUI-USD","SEI-USD","TIA-USD",
    "RNDR-USD","FET-USD","GRT-USD","SAND-USD","MANA-USD","AXS-USD","ENJ-USD",
    "CRV-USD","AAVE-USD","MKR-USD","COMP-USD","SNX-USD","LDO-USD","RPL-USD",
    "IMX-USD","BLUR-USD","DYDX-USD","PEPE-USD","SHIB-USD","FLOKI-USD",
    "WIF-USD","BONK-USD","JTO-USD","PYTH-USD","JUP-USD","STRK-USD","MANTA-USD",
    "ENA-USD","W-USD","ORDI-USD","SATS-USD","STX-USD","THETA-USD","EGLD-USD",
]

# Ticarətdən çıxarılmış simvollar
DELISTED = {
    "ANSS","FI","K","PXD","HES","MRO","SWN","CHK","TGI","IDEX","MOOG",
    "MPW","PEAK","SFR","DRE","BECN","UFP","PARA","IPG","ATVI","IACI",
    "ZI","SMAR","COUP","SAVE","HA","FSR","AMETEK","NVENT","REXNORD",
    "BELDEN","WATTS","AIMC","HOLI","AZEK","WBT","LAM","RTLR","SMSC",
    "PSEM","IIVI","HOLX","CIVI","VTLE","ECHO","SJW","CTWS","IAS","CDAY",
    "SGEN","WBA","CFLT","SEMR",
}


# ── İndikator Hesablamaları ───────────────────────────────────

def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(series: pd.Series):
    ema_fast   = calc_ema(series, MACD_FAST)
    ema_slow   = calc_ema(series, MACD_SLOW)
    macd_line  = ema_fast - ema_slow
    signal     = calc_ema(macd_line, MACD_SIGNAL)
    histogram  = macd_line - signal
    return macd_line, signal, histogram


def analyze(df: pd.DataFrame) -> dict | None:
    """
    Bütün indikatorları hesabla və ALIŞ / SATIŞ skorunu qaytar.
    """
    if len(df) < BARS // 2:
        return None

    close  = df["Close"].squeeze()
    volume = df["Volume"].squeeze()

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if isinstance(volume, pd.DataFrame):
        volume = volume.iloc[:, 0]

    close  = close.dropna()
    volume = volume.dropna()

    if len(close) < EMA_SLOW + 10:
        return None

    # EMA
    ema9  = calc_ema(close, EMA_FAST)
    ema21 = calc_ema(close, EMA_MID)
    ema50 = calc_ema(close, EMA_SLOW)

    # RSI
    rsi = calc_rsi(close, RSI_PERIOD)

    # MACD
    macd_line, macd_sig, macd_hist = calc_macd(close)

    # Həcm MA
    vol_ma = volume.rolling(VOL_PERIOD).mean()

    # Son dəyərlər
    price     = float(close.iloc[-1])
    e9        = float(ema9.iloc[-1])
    e21       = float(ema21.iloc[-1])
    e50       = float(ema50.iloc[-1])
    rsi_val   = float(rsi.iloc[-1])
    rsi_prev  = float(rsi.iloc[-2])
    ml        = float(macd_line.iloc[-1])
    ms        = float(macd_sig.iloc[-1])
    mh        = float(macd_hist.iloc[-1])
    mh_prev   = float(macd_hist.iloc[-2])
    vol_now   = float(volume.iloc[-1])
    vol_avg   = float(vol_ma.iloc[-1])

    if any(np.isnan(v) for v in [e9, e21, e50, rsi_val, ml, ms, vol_avg]):
        return None

    # ── ALIŞ Skorlaması ───────────────────────────────────────
    buy_score = 0
    buy_reasons = []

    # 1. EMA düzülüşü
    if e9 > e21 > e50:
        buy_score += 1
        buy_reasons.append("EMA↑ düzülüşü")

    # 2. RSI: 30-60 arası VƏ yüksəlir
    if RSI_OVERSOLD < rsi_val < 60 and rsi_val > rsi_prev:
        buy_score += 1
        buy_reasons.append(f"RSI↑ {rsi_val:.0f}")
    elif RSI_OVERSOLD < rsi_val < RSI_MID:
        buy_score += 0.5
        buy_reasons.append(f"RSI neytral {rsi_val:.0f}")

    # 3. MACD: xətt siqnal üstündə VƏ histogram artır
    if ml > ms and mh > mh_prev:
        buy_score += 1
        buy_reasons.append("MACD↑ crossover")
    elif ml > ms:
        buy_score += 0.5
        buy_reasons.append("MACD üstdə")

    # 4. Həcm təsdiqi
    if vol_avg > 0 and vol_now >= vol_avg * VOL_MULTIPLIER:
        buy_score += 1
        buy_reasons.append(f"Həcm↑ {vol_now/vol_avg:.1f}x")

    # Bonus: Qiymət EMA21 üstündə
    buy_bonus = price > e21

    # ── SATIŞ Skorlaması ──────────────────────────────────────
    sell_score = 0
    sell_reasons = []

    # 1. EMA əks düzülüşü
    if e9 < e21 < e50:
        sell_score += 1
        sell_reasons.append("EMA↓ düzülüşü")

    # 2. RSI: 50-70 arası VƏ düşür
    if RSI_MID < rsi_val < RSI_OVERBOUGHT and rsi_val < rsi_prev:
        sell_score += 1
        sell_reasons.append(f"RSI↓ {rsi_val:.0f}")
    elif RSI_MID < rsi_val < RSI_OVERBOUGHT:
        sell_score += 0.5
        sell_reasons.append(f"RSI yüksək {rsi_val:.0f}")

    # 3. MACD: xətt siqnal altında VƏ histogram azalır
    if ml < ms and mh < mh_prev:
        sell_score += 1
        sell_reasons.append("MACD↓ crossover")
    elif ml < ms:
        sell_score += 0.5
        sell_reasons.append("MACD altında")

    # 4. Həcm təsdiqi (eyni filtr)
    if vol_avg > 0 and vol_now >= vol_avg * VOL_MULTIPLIER:
        sell_score += 1
        sell_reasons.append(f"Həcm↑ {vol_now/vol_avg:.1f}x")

    # Bonus: Qiymət EMA21 altında
    sell_bonus = price < e21

    # ── Siqnal Qərarı ─────────────────────────────────────────
    signal = None
    score  = 0
    reasons = []

    if buy_score >= MIN_SCORE:
        signal  = "ALIŞ"
        score   = buy_score + (0.5 if buy_bonus else 0)
        reasons = buy_reasons + (["Qiymət EMA21↑"] if buy_bonus else [])
    elif sell_score >= MIN_SCORE:
        signal  = "SATIŞ"
        score   = sell_score + (0.5 if sell_bonus else 0)
        reasons = sell_reasons + (["Qiymət EMA21↓"] if sell_bonus else [])

    if signal is None:
        return None

    return {
        "sinyal"  : signal,
        "skor"    : round(score, 1),
        "fiyat"   : round(price, 4),
        "ema9"    : round(e9,   4),
        "ema21"   : round(e21,  4),
        "ema50"   : round(e50,  4),
        "rsi"     : round(rsi_val, 1),
        "macd"    : round(ml,   4),
        "nedenler": " | ".join(reasons),
    }


# ── Məlumat Çəkmə ────────────────────────────────────────────

def fetch_stock(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period="30d", interval="1h",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            return None
        result = analyze(df)
        if result:
            result["sembol"] = ticker
            result["tip"]    = "Səhm"
        return result
    except Exception:
        return None


def fetch_crypto(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period="30d", interval="1h",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            return None
        result = analyze(df)
        if result:
            result["sembol"] = ticker.replace("-USD", "")
            result["tip"]    = "Kripto"
        return result
    except Exception:
        return None


# ── Email HTML Şablonu ────────────────────────────────────────

def build_html(buy_df: pd.DataFrame, sell_df: pd.DataFrame, now: str,
               elapsed: float, total_scanned: int) -> str:
    """Mobil uyğun responsive HTML email qurur."""

    def rows_html(sub: pd.DataFrame, color: str) -> str:
        if sub.empty:
            return f'<tr><td colspan="6" style="text-align:center;color:#888;padding:16px;">Siqnal tapılmadı</td></tr>'
        html = ""
        for _, row in sub.iterrows():
            bg = "#f0fff4" if color == "green" else "#fff5f5"
            html += f"""
            <tr style="background:{bg};border-bottom:1px solid #eee;">
              <td style="padding:10px 8px;font-weight:700;font-size:15px;">{row['sembol']}</td>
              <td style="padding:10px 8px;color:#555;">{row['tip']}</td>
              <td style="padding:10px 8px;font-weight:600;">${row['fiyat']:,.4f}</td>
              <td style="padding:10px 8px;">{row['rsi']:.1f}</td>
              <td style="padding:10px 8px;font-weight:700;color:{'#16a34a' if color=='green' else '#dc2626'};">{row['skor']:.1f}</td>
              <td style="padding:10px 8px;font-size:12px;color:#444;">{row['nedenler']}</td>
            </tr>"""
        return html

    def table_block(title: str, emoji: str, color: str,
                    sub: pd.DataFrame, bg_header: str) -> str:
        return f"""
        <div style="margin-bottom:32px;">
          <div style="background:{bg_header};border-radius:10px 10px 0 0;
                      padding:14px 18px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:22px;">{emoji}</span>
            <span style="font-size:17px;font-weight:700;color:#fff;">{title}</span>
            <span style="margin-left:auto;background:rgba(255,255,255,0.25);
                         border-radius:20px;padding:3px 12px;
                         font-size:13px;color:#fff;font-weight:600;">
              {len(sub)} simvol
            </span>
          </div>
          <div style="overflow-x:auto;border-radius:0 0 10px 10px;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <table style="width:100%;border-collapse:collapse;min-width:420px;">
              <thead>
                <tr style="background:#f8f9fa;border-bottom:2px solid #e9ecef;">
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">SİMVOL</th>
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">NÖV</th>
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">QİYMƏT</th>
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">RSI</th>
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">SKOR</th>
                  <th style="padding:10px 8px;text-align:left;font-size:12px;color:#666;">SƏBƏBLƏR</th>
                </tr>
              </thead>
              <tbody>
                {rows_html(sub, color)}
              </tbody>
            </table>
          </div>
        </div>"""

    buy_block  = table_block("ALIŞ SİQNALLARI",  "🟢", "green", buy_df,  "#16a34a")
    sell_block = table_block("SATIŞ SİQNALLARI", "🔴", "red",   sell_df, "#dc2626")

    return f"""<!DOCTYPE html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Confluence Screener Nəticələri</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:16px;">

    <!-- Başlıq -->
    <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);
                border-radius:14px;padding:28px 24px;margin-bottom:24px;text-align:center;">
      <div style="font-size:32px;margin-bottom:8px;">📊</div>
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">
        Confluence Screener
      </h1>
      <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px;">
        1 Saatlıq Şam · Amerika Səhmləri + Kripto
      </p>
      <p style="margin:10px 0 0;color:rgba(255,255,255,0.65);font-size:13px;">
        🕐 {now}
      </p>
    </div>

    <!-- Statistika kartları -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px;">
      <div style="background:#fff;border-radius:10px;padding:16px;text-align:center;
                  box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <div style="font-size:24px;font-weight:800;color:#2563eb;">{total_scanned}</div>
        <div style="font-size:12px;color:#888;margin-top:4px;">Tarandı</div>
      </div>
      <div style="background:#fff;border-radius:10px;padding:16px;text-align:center;
                  box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <div style="font-size:24px;font-weight:800;color:#16a34a;">{len(buy_df)}</div>
        <div style="font-size:12px;color:#888;margin-top:4px;">Alış</div>
      </div>
      <div style="background:#fff;border-radius:10px;padding:16px;text-align:center;
                  box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <div style="font-size:24px;font-weight:800;color:#dc2626;">{len(sell_df)}</div>
        <div style="font-size:12px;color:#888;margin-top:4px;">Satış</div>
      </div>
    </div>

    <!-- İndikator parametrləri -->
    <div style="background:#fff;border-radius:10px;padding:16px;margin-bottom:24px;
                box-shadow:0 1px 4px rgba(0,0,0,0.08);">
      <p style="margin:0 0 10px;font-size:13px;font-weight:700;color:#374151;">
        ⚙️ Parametrlər
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <span style="background:#eff6ff;color:#2563eb;border-radius:6px;padding:4px 10px;font-size:12px;">EMA 9/21/50</span>
        <span style="background:#eff6ff;color:#2563eb;border-radius:6px;padding:4px 10px;font-size:12px;">RSI 14</span>
        <span style="background:#eff6ff;color:#2563eb;border-radius:6px;padding:4px 10px;font-size:12px;">MACD 12/26/9</span>
        <span style="background:#eff6ff;color:#2563eb;border-radius:6px;padding:4px 10px;font-size:12px;">Həcm ×{VOL_MULTIPLIER}</span>
        <span style="background:#f0fdf4;color:#16a34a;border-radius:6px;padding:4px 10px;font-size:12px;">Min skor: {MIN_SCORE}/4</span>
        <span style="background:#fef9c3;color:#854d0e;border-radius:6px;padding:4px 10px;font-size:12px;">⏱ {elapsed:.0f} saniyə</span>
      </div>
    </div>

    <!-- Cədvəllər -->
    {buy_block}
    {sell_block}

    <!-- Xəbərdarlıq -->
    <div style="background:#fef3c7;border-left:4px solid #f59e0b;border-radius:8px;
                padding:14px 16px;margin-bottom:16px;">
      <p style="margin:0;font-size:13px;color:#78350f;">
        ⚠️ <strong>Bu maliyyə məsləhəti deyil.</strong>
        Öz analizinizi aparın. Yatırım qərarlarını peşəkar məsləhətçi ilə müzakirə edin.
      </p>
    </div>

    <!-- Footer -->
    <p style="text-align:center;font-size:11px;color:#9ca3af;margin:0;">
      Confluence Screener · Avtomatik hesabat · {now}
    </p>
  </div>
</body>
</html>"""


# ── Email Göndərmə ────────────────────────────────────────────

def send_email(html: str, now: str, buy_count: int, sell_count: int):
    """Gmail SMTP vasitəsilə HTML email göndərir."""
    sender   = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")

    if not all([sender, password, receiver]):
        print("⚠️  Email göndərilmir: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER"
              " mühit dəyişənlərini təyin edin.")
        return

    subject = (f"📊 Confluence Screener · {now} · "
               f"🟢{buy_count} Alış  🔴{sell_count} Satış")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✉️  Email göndərildi → {receiver}")
    except Exception as e:
        print(f"❌ Email xətası: {e}")


# ── Ana Screener ──────────────────────────────────────────────

def run():
    print("=" * 70)
    print("  CONFLUENCE SCREENER  —  1 Saatlıq Şam  |  Səhm + Kripto")
    print("=" * 70)
    print(f"  İndikatorlar  : EMA {EMA_FAST}/{EMA_MID}/{EMA_SLOW} | RSI {RSI_PERIOD} | MACD {MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL} | Həcm")
    print(f"  Siqnal həddi  : {MIN_SCORE}/4 indikator eyni istiqamətdə")
    print(f"  Həcm filtri   : Ort. x{VOL_MULTIPLIER}")
    print("=" * 70 + "\n")

    # Siyahıları hazırla
    stocks  = [t for t in dict.fromkeys(STOCK_TICKERS) if t not in DELISTED]
    cryptos = list(dict.fromkeys(CRYPTO_TICKERS))
    total   = len(stocks) + len(cryptos)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"📅 Tarama vaxtı  : {now}")
    print(f"📈 Səhmlər       : {len(stocks)}")
    print(f"🪙 Kriptolar     : {len(cryptos)}")
    print(f"🔍 Cəmi          : {total}")
    print(f"⚙️  Thread        : {WORKERS}\n")

    results    = []
    start_time = time.time()

    # Səhm taraması
    print("── Səhmlər taranır... ─────────────────────────────────────────")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_stock, t): t for t in stocks}
        for f in tqdm(as_completed(futs), total=len(futs),
                      desc="Səhm", ncols=70, unit="ədəd"):
            r = f.result()
            if r:
                results.append(r)

    # Kripto taraması
    print("\n── Kriptolar taranır... ───────────────────────────────────────")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_crypto, t): t for t in cryptos}
        for f in tqdm(as_completed(futs), total=len(futs),
                      desc="Kripto", ncols=70, unit="ədəd"):
            r = f.result()
            if r:
                results.append(r)

    elapsed = time.time() - start_time

    print(f"\n⏱️  Tamamlandı    : {elapsed:.1f} saniyə")
    print(f"✅ Siqnal tapılan : {len(results)}\n")

    if not results:
        print("❌ Siqnal verən simvol tapılmadı.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values(["sinyal", "skor"], ascending=[True, False]).reset_index(drop=True)
    df.index += 1

    buy_df  = df[df["sinyal"] == "ALIŞ"].copy()
    sell_df = df[df["sinyal"] == "SATIŞ"].copy()

    # ── Konsol çıxışı ────────────────────────────────────────
    for label, sub in [("ALIŞ 🟢", buy_df), ("SATIŞ 🔴", sell_df)]:
        if sub.empty:
            continue
        print(f"\n{'━'*70}")
        print(f"  {label}  —  {len(sub)} simvol")
        print(f"{'━'*70}")
        header = (f"{'#':<4} {'Növ':<7} {'Simvol':<10} {'Qiymət':>10} "
                  f"{'RSI':>6} {'Skor':>6}  Səbəblər")
        sep = "─" * 70
        print(sep)
        print(header)
        print(sep)
        for i, row in sub.iterrows():
            print(f"{i:<4} {row['tip']:<7} {row['sembol']:<10} "
                  f"{row['fiyat']:>10.4f} {row['rsi']:>6.1f} "
                  f"{row['skor']:>6.1f}  {row['nedenler']}")
        print(sep)

    # ── CSV saxla ────────────────────────────────────────────
    ts       = datetime.now().strftime("%Y%m%d_%H%M")
    csv_name = f"confluence_siqnallar_{ts}.csv"
    df[["tip","sembol","sinyal","skor","fiyat","rsi","macd","ema9","ema21","ema50","nedenler"]]\
        .to_csv(csv_name, index=False, encoding="utf-8-sig")
    print(f"\n💾 Saxlandı: {csv_name}")

    # ── Email göndər ─────────────────────────────────────────
    html = build_html(buy_df, sell_df, now, elapsed, total)
    send_email(html, now, len(buy_df), len(sell_df))

    print("\n⚠️  Bu maliyyə məsləhəti deyil. Öz analizinizi aparın.")


if __name__ == "__main__":
    run()
