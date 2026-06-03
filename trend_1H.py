import os
import yfinance as yf
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- GitHub Secrets-dən Məlumatların Oxunması ---
MAIL_GONDEREN = "farid.alizade141@gmail.com"
MAIL_ALAN = "farid.alizade141@gmail.com"
MAIL_SIFRESI = os.getenv("MAIL_PASSWORD")


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def calc_ema(series, period):
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def get_signal(ticker, interval, rsi_period, ema_period, vol_mult, data_period="2y"):
    """
    Checks a single timeframe and returns signal info or None.
    Returns dict with signal details, or None if no signal / error.
    """
    try:
        df = yf.download(ticker, interval=interval, period=data_period, progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < max(ema_period, rsi_period, 20):
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price          = float(df["Close"].iloc[-1])
        prev_price     = float(df["Close"].iloc[-2])
        prev_open_price= float(df["Open"].iloc[-2])
        rsi_val        = float(calc_rsi(df["Close"], rsi_period).iloc[-1])
        ema_val        = float(calc_ema(df["Close"], ema_period).iloc[-1])

        vol_avg   = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg) if vol_avg > 0 else 0

        # Volume threshold must be met
        if vol_ratio < vol_mult:
            return None

        # Determine signal direction (same logic as original)
        signal = None
        if price > ema_val and price > prev_price:
            signal = "LONG"
        elif price < ema_val and price < prev_price:
            signal = "SHORT"
        elif price > ema_val and price < prev_open_price:
            signal = "SHORT"
        elif price < ema_val and price > prev_open_price:
            signal = "LONG"

        if signal is None:
            return None

        dist_pc = ((price - ema_val) / ema_val) * 100
        return {
            "signal":    signal,
            "price":     round(price, 4),
            "rsi":       round(rsi_val, 2),
            "ema":       round(ema_val, 4),
            "vol_ratio": round(vol_ratio, 2),
            "dist_pc":   round(dist_pc, 2),
        }

    except Exception as e:
        print(f"Xəta [{interval}] {ticker}: {e}")
        return None


def check_symbol_multi_tf(ticker,
                           # 1h params (unchanged)
                           h1_interval="1h", h1_ema=20, h1_rsi=14, h1_vol=1.5,
                           # 15m params
                           m15_interval="15m", m15_ema=20, m15_rsi=14, m15_vol=2.0):
    """
    Returns a result dict only when BOTH timeframes show the SAME signal direction
    AND both pass their respective volume thresholds.
    """
    # 15m uses shorter history to keep download fast (60d is max for 15m on yfinance)
    res_1h  = get_signal(ticker, h1_interval,  h1_rsi,  h1_ema,  h1_vol,  data_period="2y")
    res_15m = get_signal(ticker, m15_interval, m15_rsi, m15_ema, m15_vol, data_period="60d")

    if res_1h is None or res_15m is None:
        return None

    # Both timeframes must agree on direction
    if res_1h["signal"] != res_15m["signal"]:
        return None

    return {
        "Tikker":        ticker,
        "Siqnal":        res_1h["signal"],
        "Qiymət":        res_1h["price"],
        # --- 1h columns ---
        "1H RSI":        res_1h["rsi"],
        f"1H EMA({h1_ema})":  res_1h["ema"],
        "1H Həcm X":     res_1h["vol_ratio"],
        "1H Məsafə %":   f"{res_1h['dist_pc']}%",
        # --- 15m columns ---
        "15M RSI":       res_15m["rsi"],
        f"15M EMA({m15_ema})": res_15m["ema"],
        "15M Həcm X":    res_15m["vol_ratio"],
        "15M Məsafə %":  f"{res_15m['dist_pc']}%",
    }


def mail_gonder(results_list, h1_vol_mult, m15_vol_mult):
    password = os.getenv("MAIL_PASSWORD")

    if not results_list:
        print("Siyahı boşdur, mail göndərilmədi.")
        return
    if not password:
        print("XƏTA: MAIL_PASSWORD tapılmadı! GitHub Secrets-i yoxlayın.")
        return

    try:
        msg = MIMEMultipart()
        msg['Subject'] = (
            f"🚀 Multi-TF Trend Hesabat (15M + 1H) — "
            f"{datetime.now().strftime('%H:%M')} | "
            f"Vol: 1H≥{h1_vol_mult}x / 15M≥{m15_vol_mult}x"
        )
        msg['From'] = MAIL_GONDEREN
        msg['To']   = MAIL_ALAN

        html = "<html><body>"
        html += "<h2 style='text-align:center;'>Texniki Radar — 15M + 1H Təsdiq</h2>"
        html += (
            "<p style='text-align:center;color:#888;font-size:13px;'>"
            "Yalnız hər iki zaman çərçivəsi eyni istiqaməti göstərən aktivlər</p>"
        )

        for item in results_list:
            if not isinstance(item, dict):
                continue

            sig_color = "#4CAF50" if item.get("Siqnal") == "LONG" else "#F44336"

            # Dynamically find EMA keys
            ema_1h_key  = next((k for k in item if k.startswith("1H EMA")),  "1H EMA")
            ema_15m_key = next((k for k in item if k.startswith("15M EMA")), "15M EMA")

            html += f"""
            <div style="border:1px solid #ddd; border-left:6px solid {sig_color};
                        padding:15px; margin-bottom:12px; border-radius:5px;
                        font-family:Arial,sans-serif;">
                <b style="font-size:18px;">{item.get('Tikker','N/A')}</b>
                &nbsp;—&nbsp;
                <span style="color:{sig_color}; font-weight:bold;">
                    {item.get('Siqnal','N/A')}
                </span><br>
                <div style="margin-top:6px; color:#333;">
                    Qiymət: <b>{item.get('Qiymət','')}</b>
                </div>
                <table style="margin-top:8px; border-collapse:collapse; width:100%;
                              font-size:13px; color:#555;">
                    <tr style="background:#f5f5f5;">
                        <th style="padding:4px 8px; text-align:left;"></th>
                        <th style="padding:4px 8px; text-align:left;">1H</th>
                        <th style="padding:4px 8px; text-align:left;">15M</th>
                    </tr>
                    <tr>
                        <td style="padding:4px 8px;">RSI</td>
                        <td style="padding:4px 8px;"><b>{item.get('1H RSI','')}</b></td>
                        <td style="padding:4px 8px;"><b>{item.get('15M RSI','')}</b></td>
                    </tr>
                    <tr style="background:#fafafa;">
                        <td style="padding:4px 8px;">EMA</td>
                        <td style="padding:4px 8px;"><b>{item.get(ema_1h_key,'')}</b></td>
                        <td style="padding:4px 8px;"><b>{item.get(ema_15m_key,'')}</b></td>
                    </tr>
                    <tr>
                        <td style="padding:4px 8px;">Həcm X</td>
                        <td style="padding:4px 8px;"><b>{item.get('1H Həcm X','')}x</b></td>
                        <td style="padding:4px 8px;"><b>{item.get('15M Həcm X','')}x</b></td>
                    </tr>
                    <tr style="background:#fafafa;">
                        <td style="padding:4px 8px;">Məsafə %</td>
                        <td style="padding:4px 8px;"><b>{item.get('1H Məsafə %','')}</b></td>
                        <td style="padding:4px 8px;"><b>{item.get('15M Məsafə %','')}</b></td>
                    </tr>
                </table>
            </div>
            """

        html += "</body></html>"
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_GONDEREN, password)
            server.send_message(msg)
        print("Multi-TF mail uğurla göndərildi.")

    except Exception as e:
        print(f"Mail göndərilərkən xəta: {e}")


def run_scan():
    # ── Parameters ────────────────────────────────────────────────
    H1_INTERVAL  = "1h"
    H1_EMA       = 20
    H1_RSI       = 14
    H1_VOL       = 1.5   # unchanged — 1h volume threshold

    M15_INTERVAL = "15m"
    M15_EMA      = 20    # same EMA period, faster candles capture shorter-term trend
    M15_RSI      = 14
    M15_VOL      = 2.0   # slightly higher bar on 15m: more spikes, need stronger confirmation
    # ──────────────────────────────────────────────────────────────

    targets = [
        "AAPL","MSFT","NVDA","GOOGL","GOOG","AMZN","META","TSLA","AVGO","ORCL",
        "CRM","ADBE","AMD","QCOM","TXN","INTC","AMAT","LRCX","KLAC","SNPS",
        "CDNS","MU","MCHP","NXPI","FTNT","PANW","CRWD","NOW","SNOW","PLTR",
        "INTU","ANET","CTSH","AKAM","EPAM","NET","DDOG","ZS","WDAY","APP",
        "ADSK","ARM","ASML","MRVL","ON","SMCI","TEAM","VRSK","TTD","PYPL",
        "HUBS","MDB","OKTA","VEEV","PCTY","NCNO","BRZE","ASAN","BOX","DBX",
        "ZM","DOCU","BILL","GTLB","MNDY","NICE","WIX","NTES","JD","BIDU",
        "MELI","PDD","SE","GRAB","SHOP","COIN","HOOD","SOFI","UPST",
        "AFRM","OPEN","Z","DASH","UBER","LYFT","ABNB","BKNG",
        "EXPE","TRIP","VRNS","TENB","QLYS","RDWR","S","SAIL",
        "MPWR","SLAB","SITM","NOVT","FORM","ONTO","MKSI","ACLS","ICHR",
        "SWKS","QRVO","LITE","WOLF","OLED","COHU","UCTT","CRUS","DIOD",
        "MTSI","AMBA","ALGM","POWI","AEHR","ENPH","SEDG","FSLR","RUN",
        "BE","PLUG","HPQ","HPE","DELL","WDC","STX","NTAP",
        "NTNX","SMTC","IMOS","SIMO","DIOD","HIMX","CEVA","MPWR","LSCC",
        "JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP","V","MA","COF",
        "USB","PNC","TFC","MTB","CFG","HBAN","KEY","RF","FITB","STT",
        "NTRS","CME","ICE","NDAQ","SPGI","MCO","MSCI","FIS","GPN","AMP",
        "PRU","MET","AFL","ALL","TRV","PGR","CB","HIG","L","RJF","VOYA",
        "EG","AIZ","ACGL","WRB","RYAN","AON","AJG","BRO","ERIE",
        "RLI","CINF","THG","HCI","SIGI","KMPR","AFG","FG","MKL",
        "UNH","JNJ","LLY","MRK","PFE","TMO","ABT","DHR","BMY","AMGN",
        "GILD","REGN","VRTX","ISRG","BSX","MDT","EW","SYK","ZTS","IDXX",
        "DXCM","PODD","ALGN","RVTY","IQV","LH","DGX","CRL","TECH","HSIC",
        "VTRS","MRNA","BIIB","INCY","ALNY","BMRN","MOH","CNC","ELV","HUM",
        "CVS","CI","OSCR","TDOC","AMWL","HIMS","DOCS","PHR",
        "NVCR","KPTI","FATE","RCKT","BEAM","EDIT","NTLA","CRSP","PACB","ILMN",
        "WMT","PG","KO","PEP","COST","MCD","PM","MO","CL","MDLZ","KMB","GIS",
        "CPB","CAG","SJM","HRL","TSN","MKC","CLX","CHD","EL","KR","TGT",
        "DLTR","DG","ULTA","ROST","TJX","BBY","HD","LOW","ORLY","AZO","TSCO",
        "NKE","LULU","TPR","RL","SBUX","CMG","YUM","DPZ","QSR",
        "BYND","BROS","CAVA","SHAK","WING","TXRH","DNUT",
        "XOM","CVX","COP","EOG","SLB","OXY","MPC","VLO","PSX","DVN",
        "FANG","APA","HAL","BKR","OKE","WMB","KMI","LNG","EQT","TRGP",
        "AM","CNX","RRC","AR","MGY","SM","MTDR","PR","CHRD",
        "HON","GE","RTX","LMT","NOC","GD","BA","TDG","HWM","TXT","AXON",
        "LDOS","CAT","DE","EMR","ETN","ITW","ROK","DOV","PH","AME","ROP",
        "FAST","GWW","MSI","HUBB","GNRC","XYL","NDSN","UPS","FDX","UNP",
        "NSC","CSX","WAB","TT","CARR","OTIS","JCI","EXPD","JBHT","XPO",
        "ODFL","SAIA","RXO","CHRW","GATX","MATX","ARCB","WERN","HTLD",
        "MRTN","LSTR","HUBG","KFRC","MAN","RHI","KELYA",
        "PLD","AMT","EQIX","CCI","SPG","O","WELL","PSA","EXR","AVB","EQR",
        "MAA","UDR","CPT","ESS","ARE","BXP","KIM","REG","FRT","NNN","VICI",
        "VTR","INVH","WPC","OHI","GLPI","COLD","STAG","EGP","FR","REXR",
        "NEE","DUK","SO","D","AEP","EXC","SRE","ED","PCG","PEG","XEL","ETR",
        "ES","FE","PPL","AEE","CMS","DTE","NI","WEC","EVRG","LNT","PNW",
        "OGE","NRG","VST","CEG","AWK","MSEX","YORW","ARTNA","GWRS",
        "LIN","APD","ECL","SHW","PPG","NEM","FCX","NUE","RS","VMC",
        "MLM","ALB","CE","EMN","RPM","FMC","MOS","CF","DOW","LYB","WLK",
        "OLN","CC","AXTA","AVNT","HUN","TREX","IBP","BLDR","EXP","BCC","ATI",
        "NFLX","DIS","CMCSA","T","VZ","CHTR","TMUS","WBD","FOX","FOXA",
        "NWSA","NWS","NYT","OMC","TTWO","EA","RBLX","MTCH","PINS","SNAP",
        "SPOT","LYV","TTD","MGNI","PUBM","APPS","DV","NCMI","AMC","ROKU",
        "FUBO","SIRI","FWONA","FWONK","WMG","SPHR",
        "MAR","HLT","H","IHG","CCL","RCL","NCLH","DAL","UAL","LUV","AAL",
        "ALK","JBLU","URI","GM","F","RIVN","LCID","NIO","LI","XPEV",
        "DKNG","MGM","WYNN","LVS","CZR","PENN","CHDN","CNK","IMAX","AMC",
        "BRK-B","MMM","ITW","EMR","DOV","ROP","AME","FTV","SWK","SNA",
        "LECO","GTLS","ADP","PAYC","PAYX","PCTY","WEX","FLYW","PAYO",
        "FICO","GDDY","GEN","VRSN","MANH","EPAM","GLOB","PAGS",
        "STNE","TOST","PAX","RELY","FLNC","JOBY","ACHR",

        # --- LONDON (.L) ---
        "AZN.L","GSK.L","BP.L","SHEL.L","HSBA.L","BARC.L","LLOY.L","VOD.L","RR.L",
        "NG.L","BATS.L","IMB.L","ULVR.L","DGE.L","RIO.L","GLEN.L","AAL.L","REL.L",
        "SGE.L","BA.L","IAG.L","SSE.L","AV.L",

        # --- ALMANİYA (.DE) ---
        "SAP.DE","DTE.DE","BAS.DE","BAYN.DE","ALV.DE","MUV2.DE","VOW3.DE","ADS.DE",
        "DBK.DE","CBK.DE","RWE.DE","EOAN.DE","IFX.DE","HEI.DE","HEN3.DE","BMW.DE",
        "PAH3.DE","DTG.DE","BEI.DE","ZAL.DE","CON.DE","SY1.DE","FRE.DE",

        # --- FRANSA və NİDERLAND ---
        "MC.PA","OR.PA","RMS.PA","KER.PA","AIR.PA","TTE.PA","SAN.PA","BNP.PA",
        "ASML.AS","ADYEN.AS","INGA.AS","PRX.AS",

        # --- Tier 1: Mega liquidity ---
        "BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD","DOGE-USD",
        "ADA-USD","AVAX-USD","LINK-USD","DOT-USD",

        # --- Tier 2: High volume alts ---
        "LTC-USD","BCH-USD","ATOM-USD","ETC-USD","FIL-USD","OP-USD","ARB-USD",
        "B-USD","SUI20947-USD","TON11419-USD","ME32197-USD","TRUMP35336-USD",
        "SOL16116-USD","ONDO-USD","PROS39682-USD","LAB33223-USD","KITE-USD",
        "ASTER36341-USD","AIA38430-USD","SPK36569-USD","UB38339-USD","OSMO-USD",
        "ARB11841-USD","SAGA30372-USD","PHB-USD","STORJ-USD","CGPT-USD",
        "SAHARA-USD","VIRTUAL-USD","POL28321-USD","BSB38889-USD",

        # --- Tier 3: Large-cap DeFi / Layer 1 ---
        "SUI-USD","SEI-USD","TIA-USD","INJ-USD","NEAR-USD","ALGO-USD",
        "HBAR-USD","VET-USD","ICP-USD",

        # --- Tier 4: Mid-cap high volume ---
        "RUNE-USD","SAND-USD","MANA-USD","AXS-USD","GALA-USD",
        "CRV-USD","AAVE-USD","MKR-USD","SNX-USD",

        # --- Tier 5: Trending / meme / narrative ---
        "WIF-USD","BONK-USD","FLOKI-USD","SHIB-USD","ORDI-USD","CFX-USD",

        # --- Tier 6: Infrastructure / interop ---
        "LDO-USD","PENDLE-USD","JTO-USD","PYTH-USD","JUP-USD","WEN-USD",
        "W-USD","ENA-USD","ETHFI-USD","REZ-USD","4-USD","SKYAI-USD",
        "FLOCK-USD","VANRY-USD","SXT-USD","CHZ-USD","PEPE24478-USD",
        "MON30495-USD","ARKM-USD","SHIB-USD","XAUT-USD","LAYER35429-USD","AI39883-USD",

        # --- Tier 7: Gaming / NFT / metaverse ---
        "BEAM-USD","MAVIA-USD","YGG-USD","LOOKS-USD","HYPE32196-USD",
        "USDC-USD","BILL39545-USD","OPG-USD","UNI7083-USD","XPL-USD",
        "ROBO39595-USD","COMP5692-USD","STABLE38892-USD","TRIA-USD",

        # --- Tier 8: Layer 2 / rollups ---
        "MANTA-USD","ZETA-USD","STRK-USD","TAIKO-USD","MODE-USD","METIS-USD",

        # --- Tier 9: AI / data / compute ---
        "FET-USD","AGIX-USD","OCEAN-USD","RENDER-USD","WLD-USD",
        "TAO22974-USD","ATH30083-USD","AIOZ-USD","RSS3-USD","NMR-USD",
        "IRYS-USD","SUN-USD","ORCA-USD",

        # --- Tier 10: Classic / legacy alts ---
        "XLM-USD","TRX-USD","XMR-USD","ZEC-USD","DASH-USD",
        "XTZ-USD","ICX-USD","ONT-USD",
    ]

    results = []
    print(f"Multi-TF skan başlayır: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"1H vol≥{H1_VOL}x   |   15M vol≥{M15_VOL}x   |   Hər iki TF eyni istiqamət tələb olunur\n")

    for sym in targets:
        hit = check_symbol_multi_tf(
            sym,
            h1_interval=H1_INTERVAL, h1_ema=H1_EMA, h1_rsi=H1_RSI, h1_vol=H1_VOL,
            m15_interval=M15_INTERVAL, m15_ema=M15_EMA, m15_rsi=M15_RSI, m15_vol=M15_VOL,
        )
        if hit:
            results.append(hit)

    if results:
        # Sort: 1H vol 3-4x first (sweet-spot), then by descending 1H vol
        results_sorted = sorted(
            results,
            key=lambda x: (0 if 3 <= x["1H Həcm X"] <= 4 else 1, -x["1H Həcm X"])
        )

        print(tabulate(pd.DataFrame(results_sorted), headers="keys", tablefmt="grid", showindex=False))
        mail_gonder(results_sorted, H1_VOL, M15_VOL)
    else:
        print("Uyğun aktiv tapılmadı (hər iki TF eyni siqnal + həcm şərti ödənilmədi).")


if __name__ == "__main__":
    run_scan()
