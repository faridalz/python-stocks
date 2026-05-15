"""
=============================================================
  CONFLUENCE SCREENER v2 — 1 Saatlıq Şam  |  Advanced
  Amerika Səhmləri + Kripto
=============================================================
  İndikatorlar (7 qat, ağırlıqlı sistem):

    1. ADX ≥ 20          → Trend gücü filteri (keçid olmadan siqnal yox)
    2. EMA 9/21/50        → Trend istiqaməti
    3. StochRSI %K/%D     → Momentum keyfiyyəti (sadə RSI-dan daha həssas)
    4. MACD 12/26/9       → Crossover + artan/azalan histogram
    5. Həcm               → 20p ort. x1.3 — təsdiq filteri
    6. Bollinger Squeeze  → Konsolidasiyadan çıxış anı
    7. 4 Saatlıq Trend    → Böyük zaman çərçivəsi uyğunluğu
                            (1h siqnal 4h trende zidd ola bilməz)

  Əlavə çıxışlar:
    • ATR əsasında TP1, TP2, Stop Loss hədləri
    • Skor: 0–10 arası ağırlıqlı xal
    • Güc səviyyəsi: ZƏIF / ORTA / GÜCLÜ / ÇOX GÜCLÜ

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
WORKERS        = 20
MIN_SCORE      = 5.0    # Minimum xal (0-10 arası); yüksəldilsə daha az, daha keyfiyyətli siqnal

# EMA
EMA_FAST, EMA_MID, EMA_SLOW = 9, 21, 50

# RSI
RSI_PERIOD    = 14   # Sadə RSI periyodu (skora daxil edilir)

# ADX  (1 saatlıq üçün ≥20 optimal — trendli bazarı süzür)
ADX_PERIOD    = 14
ADX_MIN       = 20      # Altında siqnal verilmir — yan trend çox false positive yaradır
ADX_MAX       = 50      # Üstündə həddən artıq uzanma riski var

# StochRSI
SRSI_RSI_P    = 14
SRSI_STOCH_P  = 14
SRSI_K        = 3       # %K hamarlaşdırma
SRSI_D        = 3       # %D hamarlaşdırma

# MACD
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

# Həcm
VOL_PERIOD    = 20
VOL_MULT      = 1.30    # Ortalamanın 1.3 katı

# Bollinger Squeeze
BB_PERIOD     = 20
BB_STD        = 2.0
KC_PERIOD     = 20
KC_MULT       = 1.5

# ATR (TP/SL üçün)
ATR_PERIOD    = 14
ATR_TP1       = 1.5     # TP1 = giriş + ATR × 1.5
ATR_TP2       = 3.0     # TP2 = giriş + ATR × 3.0
ATR_SL        = 1.0     # SL  = giriş - ATR × 1.0
# ─────────────────────────────────────────────────────────────

# ── Ağırlıqlar (cəmi 10 xal) ─────────────────────────────────
W_ADX      = 1.0   # Trend gücü (keçid şərti)
W_EMA      = 2.0   # Trend istiqaməti
W_RSI      = 1.0   # Sadə RSI (overbought/oversold filtri)
W_SRSI     = 2.0   # StochRSI momentum keyfiyyəti
W_MACD     = 1.5   # Momentum istiqaməti
W_VOL      = 1.0   # Həcm onayı
W_SQUEEZE  = 1.0   # Squeeze çıxışı
W_MTF      = 0.5   # 4h trend uyğunluğu
# Cəm: 10.0
# ─────────────────────────────────────────────────────────────

STOCK_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","ORCL","CRM",
    "ADBE","AMD","QCOM","TXN","INTC","AMAT","LRCX","KLAC","SNPS","CDNS",
    "MU","MCHP","NXPI","FTNT","PANW","CRWD","NOW","SNOW","PLTR","INTU",
    "ANET","CTSH","AKAM","EPAM","NET","DDOG","ZS","WDAY","APP","ADSK",
    "ARM","MRVL","ON","SMCI","TEAM","VRSK","TTD","PYPL","HUBS","MDB",
    "OKTA","VEEV","GTLB","MNDY","MELI","PDD","SE","SHOP","SQ","COIN",
    "HOOD","SOFI","UPST","AFRM","DASH","UBER","LYFT","ABNB","BKNG","ROKU",
    "JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP","V","MA","COF",
    "USB","PNC","TFC","MTB","CFG","HBAN","KEY","RF","FITB","STT","BK",
    "NTRS","CME","ICE","NDAQ","SPGI","MCO","MSCI","FIS","GPN","AMP",
    "PRU","MET","AFL","ALL","TRV","PGR","CB","HIG","RJF","ACGL","WRB",
    "UNH","JNJ","LLY","ABBV","MRK","PFE","TMO","ABT","DHR","BMY","AMGN",
    "GILD","REGN","VRTX","ISRG","BSX","MDT","EW","SYK","ZTS","IDXX",
    "DXCM","PODD","ALGN","RVTY","IQV","LH","DGX","CRL","TECH","HSIC",
    "VTRS","MRNA","BIIB","INCY","ALNY","MOH","CNC","ELV","HUM","CVS","CI",
    "WMT","PG","KO","PEP","COST","MCD","PM","MO","CL","MDLZ","KMB","GIS",
    "CPB","CAG","HRL","TSN","MKC","CLX","CHD","EL","KR","TGT","DLTR","DG",
    "ULTA","ROST","TJX","BBY","HD","LOW","ORLY","AZO","TSCO","NKE","LULU",
    "TPR","RL","SBUX","CMG","YUM","DPZ","QSR",
    "XOM","CVX","COP","EOG","SLB","OXY","MPC","VLO","PSX","DVN","FANG",
    "APA","HAL","BKR","OKE","WMB","KMI","LNG","EQT","TRGP","CNX","RRC","AR",
    "HON","GE","RTX","LMT","NOC","GD","BA","TDG","HWM","AXON","LDOS",
    "CAT","DE","EMR","ETN","ITW","ROK","DOV","PH","AME","ROP","FAST","GWW",
    "MSI","HUBB","GNRC","XYL","UPS","FDX","UNP","NSC","CSX","WAB","TT",
    "CARR","OTIS","JCI","EXPD","JBHT","XPO","ODFL","SAIA",
    "PLD","AMT","EQIX","CCI","SPG","O","WELL","PSA","EXR","AVB","VICI",
    "NEE","DUK","SO","AEP","EXC","SRE","ED","PEG","XEL","NRG","VST","CEG",
    "LIN","APD","ECL","SHW","PPG","NEM","FCX","NUE","STLD","VMC","MLM",
    "NFLX","DIS","CMCSA","T","VZ","CHTR","TMUS","WBD","FOX","NYT","OMC",
    "TTWO","EA","RBLX","MTCH","PINS","SNAP","SPOT","LYV",
    "GM","F","RIVN","LCID","NIO","LI","XPEV","DAL","UAL","LUV","AAL",
    "MAR","HLT","CCL","RCL","NCLH","DKNG","MGM","WYNN","LVS","CZR",
    "BRK-B","MMM","ITW","EMR","ROP","AME","SWK","SNA","ADP","PAYX","FICO",
    "GDDY","MANH","HPQ","HPE","DELL","WDC","STX","NTAP","PSTG","NTNX",
    "ENPH","SEDG","FSLR","BE","PLUG","MPWR","SWKS","QRVO","LITE",
]

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

DELISTED = {
    "ANSS","FI","K","PXD","HES","MRO","SWN","CHK","TGI","IDEX","MOOG",
    "MPW","PEAK","SFR","DRE","BECN","UFP","PARA","IPG","ATVI","IACI",
    "ZI","SMAR","COUP","SAVE","HA","FSR","AMETEK","NVENT","REXNORD",
    "BELDEN","WATTS","AIMC","HOLI","AZEK","WBT","LAM","RTLR","SMSC",
    "PSEM","IIVI","HOLX","CIVI","VTLE","ECHO","SJW","CTWS","IAS","CDAY",
    "SGEN","WBA","CFLT","SEMR",
}


# ── İndikator Hesablamaları ───────────────────────────────────

def calc_ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, p: int) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=p - 1, adjust=False).mean()

def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, p: int):
    """ADX, +DI, -DI qaytarır."""
    up   = high.diff()
    down = -low.diff()
    plus_dm  = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr_s = calc_atr(high, low, close, p)
    plus_di  = 100 * pd.Series(plus_dm,  index=close.index).ewm(com=p-1, adjust=False).mean() / atr_s
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(com=p-1, adjust=False).mean() / atr_s
    dx  = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(com=p - 1, adjust=False).mean()
    return adx, plus_di, minus_di

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Sadə RSI — skora daxil edilir və email-də göstərilir."""
    delta    = close.diff()
    gain     = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss     = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))

def calc_stoch_rsi(close: pd.Series, rsi_p: int, stoch_p: int, k: int, d: int):
    """StochRSI %K və %D qaytarır."""
    delta    = close.diff()
    gain     = delta.clip(lower=0).ewm(com=rsi_p-1, adjust=False).mean()
    loss     = (-delta.clip(upper=0)).ewm(com=rsi_p-1, adjust=False).mean()
    rsi      = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi_low  = rsi.rolling(stoch_p).min()
    rsi_high = rsi.rolling(stoch_p).max()
    stoch_k  = 100 * (rsi - rsi_low) / (rsi_high - rsi_low).replace(0, np.nan)
    pct_k    = stoch_k.rolling(k).mean()
    pct_d    = pct_k.rolling(d).mean()
    return pct_k, pct_d

def calc_macd(close: pd.Series):
    fast = calc_ema(close, MACD_FAST)
    slow = calc_ema(close, MACD_SLOW)
    line = fast - slow
    sig  = calc_ema(line, MACD_SIGNAL)
    hist = line - sig
    return line, sig, hist

def calc_squeeze(high, low, close):
    """
    Bollinger Bands içərisə Keltner Channel-da sıxılırsa → squeeze aktiv.
    Squeeze bitdikdən sonra ilk şam — yüksək ehtimallı breakout.
    """
    mid   = close.rolling(BB_PERIOD).mean()
    std   = close.rolling(BB_PERIOD).std()
    bb_up = mid + BB_STD * std
    bb_lo = mid - BB_STD * std

    atr_kc = calc_atr(high, low, close, KC_PERIOD)
    kc_up  = calc_ema(close, KC_PERIOD) + KC_MULT * atr_kc
    kc_lo  = calc_ema(close, KC_PERIOD) - KC_MULT * atr_kc

    squeeze_on  = (bb_up < kc_up) & (bb_lo > kc_lo)
    squeeze_off = ~squeeze_on
    # Əvvəlki şamda squeeze var idi, indiki şamda yoxdur → breakout anı
    just_released = squeeze_off & squeeze_on.shift(1).fillna(False)
    return squeeze_on, just_released

def get_4h_trend(ticker: str) -> int:
    """
    4 saatlıq EMA 21/50 trendi qaytarır:
      +1 → EMA21 > EMA50 (bullish)
      -1 → EMA21 < EMA50 (bearish)
       0 → müəyyən deyil
    """
    try:
        df = yf.download(ticker, period="60d", interval="4h",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 55:
            return 0
        c = df["Close"].squeeze()
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        e21 = float(calc_ema(c, 21).iloc[-1])
        e50 = float(calc_ema(c, 50).iloc[-1])
        return 1 if e21 > e50 else -1
    except Exception:
        return 0


# ── Əsas Analiz ───────────────────────────────────────────────

def analyze(df: pd.DataFrame, trend_4h: int) -> dict | None:
    if len(df) < 80:
        return None

    close  = df["Close"].squeeze()
    high   = df["High"].squeeze()
    low    = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    for s in [close, high, low, volume]:
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]

    close  = close.dropna();  high = high.dropna()
    low    = low.dropna();    volume = volume.dropna()

    if len(close) < 60:
        return None

    # ── Hesablamalar ─────────────────────────────────────────
    ema9  = calc_ema(close, EMA_FAST)
    ema21 = calc_ema(close, EMA_MID)
    ema50 = calc_ema(close, EMA_SLOW)

    adx, plus_di, minus_di = calc_adx(high, low, close, ADX_PERIOD)
    pct_k, pct_d = calc_stoch_rsi(close, SRSI_RSI_P, SRSI_STOCH_P, SRSI_K, SRSI_D)
    macd_l, macd_s, macd_h = calc_macd(close)
    atr = calc_atr(high, low, close, ATR_PERIOD)
    vol_ma = volume.rolling(VOL_PERIOD).mean()
    _, squeeze_release = calc_squeeze(high, low, close)
    rsi_series = calc_rsi(close, RSI_PERIOD)

    # Son dəyərlər
    price   = float(close.iloc[-1])
    e9      = float(ema9.iloc[-1])
    e21     = float(ema21.iloc[-1])
    e50     = float(ema50.iloc[-1])
    adx_val = float(adx.iloc[-1])
    pdi     = float(plus_di.iloc[-1])
    mdi     = float(minus_di.iloc[-1])
    k_val   = float(pct_k.iloc[-1])
    d_val   = float(pct_d.iloc[-1])
    k_prev  = float(pct_k.iloc[-2])
    d_prev  = float(pct_d.iloc[-2])
    ml      = float(macd_l.iloc[-1])
    ms      = float(macd_s.iloc[-1])
    mh      = float(macd_h.iloc[-1])
    mh_p    = float(macd_h.iloc[-2])
    atr_val = float(atr.iloc[-1])
    vol_now = float(volume.iloc[-1])
    vol_avg = float(vol_ma.iloc[-1])
    sq_rel  = bool(squeeze_release.iloc[-1])
    rsi_val = float(rsi_series.iloc[-1])
    rsi_prev= float(rsi_series.iloc[-2])

    if any(np.isnan(v) for v in [adx_val, e9, e21, e50, k_val, d_val, ml, atr_val, vol_avg, rsi_val]):
        return None

    # ── KEÇID ŞƏRTİ: ADX filtri ──────────────────────────────
    # ADX < 20 → bazarda trend yoxdur, siqnal etibarlı deyil
    # ADX > 50 → həddən artıq uzanma, geri dönüş riski var
    if not (ADX_MIN <= adx_val <= ADX_MAX):
        return None

    # ── ALIŞ Skorlaması ───────────────────────────────────────
    buy_score   = 0.0
    buy_reasons = []

    # 1. ADX (1.5 xal)
    if pdi > mdi:
        buy_score += W_ADX
        buy_reasons.append(f"ADX↑ {adx_val:.0f} (+DI>{mdi:.0f})")

    # 2. EMA düzülüşü (2.0 xal)
    if e9 > e21 > e50:
        buy_score += W_EMA
        buy_reasons.append("EMA9>21>50↑")
    elif e9 > e21 and price > e50:
        buy_score += W_EMA * 0.5
        buy_reasons.append("EMA qismən↑")

    # 3. Sadə RSI (1.0 xal)
    # Alış üçün ideal zona: 40–60 (nə oversold nə overbought — momentum gəlir)
    # RSI < 40: oversold, dönüş mümkün amma təsdiq lazım
    # RSI 40-60 arası VƏ yüksəlir: ən keyfiyyətli alış zonası
    # RSI > 70: overbought — alış siqnalına mənfi təsir
    if 40 <= rsi_val <= 69 and rsi_val > rsi_prev:
        buy_score += W_RSI
        buy_reasons.append(f"RSI↑ {rsi_val:.0f}")
    elif 30 <= rsi_val < 40 and rsi_val > rsi_prev:
        buy_score += W_RSI * 0.75
        buy_reasons.append(f"RSI↑ oversold çıxış {rsi_val:.0f}")
    elif rsi_val >= 70:
        buy_score -= W_RSI * 0
        buy_reasons.append(f"RSI overbought {rsi_val:.0f}⚠️")
    elif rsi_val < 30:
        buy_score -= W_RSI * 1
        buy_reasons.append(f"RSI impossible but WHY NOT {rsi_val:.0f}⚠️")  

    # 4. StochRSI (1.5 xal)
    # Alış üçün: K <50 zonasından yuxarı kəsim etməlidir.
    # K>=50 artıq overbought ərazisinə yaxındır — alış siqnalı sayılmır.
    if k_val < 60 and k_val > d_val and k_prev <= d_prev:
        buy_score += W_SRSI
        buy_reasons.append(f"StochRSI↑ kəsim K={k_val:.0f}")
    elif k_val < 35 and k_val > d_val:
        buy_score += W_SRSI * 0.5
        buy_reasons.append(f"StochRSI↑ K={k_val:.0f}")
    # K>=60 → alış xalı verilmir (overbought zonası)

    # 4. MACD (1.5 xal)
    # Yalnız histogram ARTIRsa tam xal — "xətt üstdə amma düz" siqnal deyil
    if ml > ms and mh > mh_p and mh > 0:
        buy_score += W_MACD
        buy_reasons.append("MACD↑ hist artır")
    elif ml > ms and mh > mh_p:
        buy_score += W_MACD * 0.5
        buy_reasons.append("MACD↑ hist dönür")
    # "Xətt üstdə amma histogram azalır" → xal verilmir

    # 5. Həcm (1.0 xal)
    if vol_avg > 0 and vol_now >= vol_avg * VOL_MULT:
        buy_score += W_VOL
        buy_reasons.append(f"Həcm↑ {vol_now/vol_avg:.1f}x")

    # 6. Squeeze çıxışı (1.0 xal)
    if sq_rel:
        buy_score += W_SQUEEZE
        buy_reasons.append("Squeeze breakout!")

    # 7. 4h trend uyğunluğu (1.0 xal)
    if trend_4h == 1:
        buy_score += W_MTF
        buy_reasons.append("4h trend↑")
    elif trend_4h == -1:
        buy_score -= W_MTF  # 4h bearish olduqda 1h alış siqnalından çıx
        buy_reasons.append("⚠️4h trend↓")

    # ── SATIŞ Skorlaması ──────────────────────────────────────
    sell_score   = 0.0
    sell_reasons = []

    # 1. ADX
    if mdi > pdi:
        sell_score += W_ADX
        sell_reasons.append(f"ADX↓ {adx_val:.0f} (-DI>{pdi:.0f})")

    # 2. EMA
    if e9 < e21 < e50:
        sell_score += W_EMA
        sell_reasons.append("EMA9<21<50↓")
    elif e9 < e21 and price < e50:
        sell_score += W_EMA * 0.5
        sell_reasons.append("EMA qismən↓")

    # 3. Sadə RSI (1.0 xal)
    # Satış üçün ideal zona: 40–60 arası aşağı dönüş
    # RSI > 60: momentum zəifləyir, satış zonası
    # RSI >= 70 VƏ düşür: ən keyfiyyətli satış zonası
    # RSI < 30: oversold — satış siqnalına mənfi təsir
    if 60 >= rsi_val >= 40 and rsi_val < rsi_prev:
        sell_score += W_RSI * 0.75
        sell_reasons.append(f"RSI↓ {rsi_val:.0f}")
    elif rsi_val > 60 and rsi_val < rsi_prev:
        sell_score += W_RSI
        sell_reasons.append(f"RSI↓ overbought {rsi_val:.0f}")
    elif rsi_val < 40:
        sell_score -= W_RSI * 0.5
        sell_reasons.append(f"RSI oversold {rsi_val:.0f}⚠️")

    # 4. StochRSI
    # Satış üçün: K >50 zonasından aşağı kəsim etməlidir.
    # K<=50 artıq oversold ərazisinə yaxındır — satış siqnalı sayılmır.
    if k_val > 50 and k_val < d_val and k_prev >= d_prev:
        sell_score += W_SRSI
        sell_reasons.append(f"StochRSI↓ kəsim K={k_val:.0f}")
    elif k_val > 60 and k_val < d_val:
        sell_score += W_SRSI * 0.75
        sell_reasons.append(f"StochRSI↓ K={k_val:.0f}")
    # K<=50 → satış xalı verilmir (oversold zonası)

    # 4. MACD
    # Yalnız histogram AZALIRsa tam xal
    if ml < ms and mh < mh_p and mh < 0:
        sell_score += W_MACD
        sell_reasons.append("MACD↓ hist azalır")
    elif ml < ms and mh < mh_p:
        sell_score += W_MACD * 0.5
        sell_reasons.append("MACD↓ hist dönür")
    # "Xətt altında amma histogram artır" → xal verilmir

    # 5. Həcm
    if vol_avg > 0 and vol_now >= vol_avg * VOL_MULT:
        sell_score += W_VOL
        sell_reasons.append(f"Həcm↑ {vol_now/vol_avg:.1f}x")

    # 6. Squeeze
    if sq_rel:
        sell_score += W_SQUEEZE
        sell_reasons.append("Squeeze breakout!")

    # 7. 4h trend
    if trend_4h == -1:
        sell_score += W_MTF
        sell_reasons.append("4h trend↓")
    elif trend_4h == 1:
        sell_score -= W_MTF
        sell_reasons.append("⚠️4h trend↑")

    # ── Siqnal Qərarı ─────────────────────────────────────────
    signal  = None
    score   = 0.0
    reasons = []

    if buy_score >= sell_score and buy_score >= MIN_SCORE:
        signal  = "ALIŞ"
        score   = buy_score
        reasons = buy_reasons
    elif sell_score > buy_score and sell_score >= MIN_SCORE:
        signal  = "SATIŞ"
        score   = sell_score
        reasons = sell_reasons

    if signal is None:
        return None

    # Güc səviyyəsi
    if score >= 8.5:
        strength = "ÇOX GÜCLÜ 🔥"
    elif score >= 7.0:
        strength = "GÜCLÜ 💪"
    elif score >= 5.5:
        strength = "ORTA ✅"
    else:
        strength = "ZƏIF ⚠️"

    # ATR əsasında TP/SL
    if signal == "ALIŞ":
        tp1 = round(price + atr_val * ATR_TP1, 4)
        tp2 = round(price + atr_val * ATR_TP2, 4)
        sl  = round(price - atr_val * ATR_SL,  4)
    else:
        tp1 = round(price - atr_val * ATR_TP1, 4)
        tp2 = round(price - atr_val * ATR_TP2, 4)
        sl  = round(price + atr_val * ATR_SL,  4)

    return {
        "sinyal"  : signal,
        "skor"    : round(score, 2),
        "guc"     : strength,
        "fiyat"   : round(price, 4),
        "tp1"     : tp1,
        "tp2"     : tp2,
        "sl"      : sl,
        "adx"     : round(adx_val, 1),
        "rsi"     : round(rsi_val, 1),
        "k"       : round(k_val,   1),
        "d"       : round(d_val,   1),
        "squeeze" : sq_rel,
        "trend4h" : trend_4h,
        "nedenler": " | ".join(reasons),
    }


# ── Məlumat Çəkmə ────────────────────────────────────────────

def fetch_and_analyze(ticker: str, is_crypto: bool) -> dict | None:
    try:
        df = yf.download(ticker, period="30d", interval="1h",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 60:
            return None

        trend_4h = get_4h_trend(ticker)
        result   = analyze(df, trend_4h)

        if result:
            result["sembol"] = ticker.replace("-USD", "") if is_crypto else ticker
            result["tip"]    = "Kripto" if is_crypto else "Səhm"
        return result
    except Exception:
        return None


# ── Email HTML ────────────────────────────────────────────────

def build_html(buy_df, sell_df, now, elapsed, total_scanned):

    def signal_rows(sub, color):
        if sub.empty:
            return '<tr><td colspan="10" style="text-align:center;color:#888;padding:16px;">Siqnal tapılmadı</td></tr>'
        rows = ""
        for _, r in sub.iterrows():
            bg      = "#f0fff4" if color == "green" else "#fff5f5"
            clr     = "#16a34a" if color == "green" else "#dc2626"
            sq_badge = ' <span style="background:#7c3aed;color:#fff;border-radius:4px;padding:1px 5px;font-size:10px;">SQ</span>' if r.get("squeeze") else ""
            mtf_icon = "▲" if r.get("trend4h") == 1 else ("▼" if r.get("trend4h") == -1 else "—")
            rows += f"""
            <tr style="background:{bg};border-bottom:1px solid #eee;">
              <td style="padding:9px 7px;font-weight:700;font-size:14px;">{r['sembol']}{sq_badge}</td>
              <td style="padding:9px 7px;color:#555;font-size:12px;">{r['tip']}</td>
              <td style="padding:9px 7px;font-weight:600;">${r['fiyat']:,.4f}</td>
              <td style="padding:9px 7px;font-size:12px;color:#16a34a;">${r['tp1']:,.4f}<br><span style="color:#059669">${r['tp2']:,.4f}</span></td>
              <td style="padding:9px 7px;font-size:12px;color:#dc2626;">${r['sl']:,.4f}</td>
              <td style="padding:9px 7px;font-size:12px;">{r['adx']:.0f}</td>
              <td style="padding:9px 7px;font-size:12px;font-weight:600;color:{'#dc2626' if r.get('rsi',50)>=70 else ('#16a34a' if r.get('rsi',50)<=30 else '#374151')};">{r.get('rsi',0):.0f}</td>
              <td style="padding:9px 7px;font-size:12px;">{mtf_icon}</td>
              <td style="padding:9px 7px;font-weight:700;color:{clr};">{r['skor']:.1f}</td>
              <td style="padding:9px 7px;font-size:11px;color:#444;">{r['nedenler']}</td>
            </tr>"""
        return rows

    def table_block(title, emoji, color, sub, hdr_color):
        return f"""
        <div style="margin-bottom:28px;">
          <div style="background:{hdr_color};border-radius:10px 10px 0 0;padding:13px 18px;
                      display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;">{emoji}</span>
            <span style="font-size:16px;font-weight:700;color:#fff;">{title}</span>
            <span style="margin-left:auto;background:rgba(255,255,255,0.25);border-radius:20px;
                         padding:3px 12px;font-size:12px;color:#fff;font-weight:600;">{len(sub)} simvol</span>
          </div>
          <div style="overflow-x:auto;border-radius:0 0 10px 10px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
            <table style="width:100%;border-collapse:collapse;min-width:560px;">
              <thead>
                <tr style="background:#f8f9fa;border-bottom:2px solid #e9ecef;">
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">SİMVOL</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">NÖV</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">QİYMƏT</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">TP1/TP2</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">STOP</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">ADX</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">RSI</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">4H</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">SKOR</th>
                  <th style="padding:9px 7px;text-align:left;font-size:11px;color:#666;">SƏBƏBLƏR</th>
                </tr>
              </thead>
              <tbody>{signal_rows(sub, color)}</tbody>
            </table>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="az">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:700px;margin:0 auto;padding:14px;">

  <div style="background:linear-gradient(135deg,#0f172a 0%,#1d4ed8 100%);
              border-radius:14px;padding:26px 22px;margin-bottom:20px;text-align:center;">
    <div style="font-size:30px;margin-bottom:6px;">📊</div>
    <h1 style="margin:0;color:#fff;font-size:19px;font-weight:700;">Confluence Screener v2</h1>
    <p style="margin:5px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">
      1 Saatlıq Şam · ADX + StochRSI + Squeeze + 4H Trend
    </p>
    <p style="margin:8px 0 0;color:rgba(255,255,255,0.6);font-size:12px;">🕐 {now}</p>
  </div>

  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px;">
    {"".join(f'<div style="background:#fff;border-radius:9px;padding:14px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.07);"><div style="font-size:21px;font-weight:800;color:{c};">{v}</div><div style="font-size:11px;color:#888;margin-top:3px;">{l}</div></div>'
    for v,l,c in [(total_scanned,"Tarandı","#2563eb"),(len(buy_df),"Alış","#16a34a"),(len(sell_df),"Satış","#dc2626"),(f"{elapsed:.0f}s","Vaxt","#7c3aed")])}
  </div>

  <div style="background:#fff;border-radius:9px;padding:14px;margin-bottom:20px;
              box-shadow:0 1px 4px rgba(0,0,0,0.07);">
    <p style="margin:0 0 9px;font-size:12px;font-weight:700;color:#374151;">⚙️ Aktiv Filterlər</p>
    <div style="display:flex;flex-wrap:wrap;gap:7px;">
      {"".join(f'<span style="background:#eff6ff;color:#2563eb;border-radius:5px;padding:3px 9px;font-size:11px;">{t}</span>'
      for t in [f"ADX {ADX_MIN}–{ADX_MAX}","EMA 9/21/50","StochRSI 14/14/3/3",f"MACD {MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL}",f"Həcm ×{VOL_MULT}","BB Squeeze","4H Trend","ATR TP/SL"])}
      <span style="background:#f0fdf4;color:#16a34a;border-radius:5px;padding:3px 9px;font-size:11px;">Min skor: {MIN_SCORE}/10</span>
    </div>
  </div>

  {table_block("ALIŞ SİQNALLARI", "🟢", "green", buy_df, "#16a34a")}
  {table_block("SATIŞ SİQNALLARI", "🔴", "red", sell_df, "#dc2626")}

  <div style="background:#fef3c7;border-left:4px solid #f59e0b;border-radius:8px;
              padding:13px 15px;margin-bottom:14px;">
    <p style="margin:0;font-size:12px;color:#78350f;">
      ⚠️ <strong>Bu maliyyə məsləhəti deyil.</strong>
      TP/SL ATR əsasında hesablanır — mütləq öz analizinizi aparın.
      <strong>SQ</strong> = Bollinger Squeeze buraxılışı · <strong>4H</strong> = 4 saatlıq trend istiqaməti
    </p>
  </div>

  <p style="text-align:center;font-size:10px;color:#9ca3af;margin:0;">
    Confluence Screener v2 · {now}
  </p>
</div>
</body>
</html>"""


def send_email(html, now, buy_count, sell_count):
    sender   = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = os.environ.get("EMAIL_RECEIVER")
    if not all([sender, password, receiver]):
        print("⚠️  Email dəyişənləri tapılmadı, keçilir.")
        return
    subject = f"📊 Screener v2 · {now} · 🟢{buy_count} Alış  🔴{sell_count} Satış"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(sender, password)
            s.sendmail(sender, receiver, msg.as_string())
        print(f"✉️  Email göndərildi → {receiver}")
    except Exception as e:
        print(f"❌ Email xətası: {e}")


# ── Ana Screener ──────────────────────────────────────────────

def run():
    print("=" * 72)
    print("  CONFLUENCE SCREENER v2  —  1 Saatlıq Şam  |  Səhm + Kripto")
    print("=" * 72)
    print(f"  İndikatorlar : ADX {ADX_MIN}-{ADX_MAX} | EMA 9/21/50 | StochRSI | MACD | Həcm | Squeeze | 4H")
    print(f"  Min skor     : {MIN_SCORE}/10  |  Həcm filtri: ×{VOL_MULT}")
    print("=" * 72 + "\n")

    stocks  = [t for t in dict.fromkeys(STOCK_TICKERS) if t not in DELISTED]
    cryptos = list(dict.fromkeys(CRYPTO_TICKERS))
    total   = len(stocks) + len(cryptos)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"📅 Tarama vaxtı  : {now}")
    print(f"📈 Səhmlər       : {len(stocks)}  🪙 Kriptolar: {len(cryptos)}  🔍 Cəmi: {total}")
    print(f"⚙️  Thread        : {WORKERS}\n")

    results    = []
    start_time = time.time()

    print("── Səhmlər taranır (1h + 4h məlumat)... ──────────────────────")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_and_analyze, t, False): t for t in stocks}
        for f in tqdm(as_completed(futs), total=len(futs), desc="Səhm", ncols=70, unit="ədəd"):
            r = f.result()
            if r: results.append(r)

    print("\n── Kriptolar taranır (1h + 4h məlumat)... ────────────────────")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_and_analyze, t, True): t for t in cryptos}
        for f in tqdm(as_completed(futs), total=len(futs), desc="Kripto", ncols=70, unit="ədəd"):
            r = f.result()
            if r: results.append(r)

    elapsed = time.time() - start_time
    print(f"\n⏱️  Tamamlandı : {elapsed:.1f} saniyə  |  ✅ Siqnal: {len(results)}\n")

    if not results:
        print("❌ Siqnal verən simvol tapılmadı.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values(["sinyal","skor"], ascending=[True, False]).reset_index(drop=True)
    df.index += 1

    buy_df  = df[df["sinyal"] == "ALIŞ"].copy()
    sell_df = df[df["sinyal"] == "SATIŞ"].copy()

    # Konsol çıxışı
    for label, sub in [("ALIŞ 🟢", buy_df), ("SATIŞ 🔴", sell_df)]:
        if sub.empty: continue
        print(f"\n{'━'*72}")
        print(f"  {label}  —  {len(sub)} simvol")
        print(f"{'━'*72}")
        print(f"{'#':<4} {'Növ':<7} {'Simvol':<10} {'Qiymət':>10} {'TP1':>10} {'SL':>10} {'ADX':>5} {'RSI':>5} {'Skor':>6}  Güc")
        print("─" * 72)
        for i, row in sub.iterrows():
            sq = " SQ" if row.get("squeeze") else ""
            print(f"{i:<4} {row['tip']:<7} {row['sembol']:<10} "
                  f"{row['fiyat']:>10.4f} {row['tp1']:>10.4f} {row['sl']:>10.4f} "
                  f"{row['adx']:>5.0f} {row.get('rsi',0):>5.0f} {row['skor']:>6.2f}  {row['guc']}{sq}")
        print("─" * 72)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    csv = f"confluence_v2_{ts}.csv"
    df[["tip","sembol","sinyal","skor","guc","fiyat","tp1","tp2","sl",
        "adx","rsi","k","d","squeeze","trend4h","nedenler"]]\
        .to_csv(csv, index=False, encoding="utf-8-sig")
    print(f"\n💾 Saxlandı: {csv}")

    html = build_html(buy_df, sell_df, now, elapsed, total)
    send_email(html, now, len(buy_df), len(sell_df))

    print("\n⚠️  Bu maliyyə məsləhəti deyil. Öz analizinizi aparın.")


if __name__ == "__main__":
    run()
