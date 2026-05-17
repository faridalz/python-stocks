import os
import yfinance as yf
import pandas as pd
from tabulate import tabulate
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- GitHub Secrets-dən Məlumatların Oxunması ---
# GitHub-da yaratdığın secret adları ilə eyni olmalıdır
MAIL_GONDEREN = "farid.alizade141@gmail.com"  # Öz mailini bura yaz
MAIL_ALAN = "farid.alizade141@gmail.com" # Hesabatı hara istəyirsənsə bura yaz
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

def check_symbol(ticker, interval, rsi_period, ema_period, vol_mult):
    try:
        # GitHub serverləri üçün data periodunu tənzimləyirik
        df = yf.download(ticker, interval=interval, period="2y", progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < max(ema_period, rsi_period, 20): return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        price = float(df["Close"].iloc[-1])
        rsi_val = float(calc_rsi(df["Close"], rsi_period).iloc[-1])
        ema_val = float(calc_ema(df["Close"], ema_period).iloc[-1])
        
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg) if vol_avg > 0 else 0

        signal = None
        if  rsi_val < 35 and vol_ratio >= vol_mult: #price > ema_val and
            signal = "BUĞA (Long)"
        elif rsi_val > 75 and vol_ratio >= vol_mult: # price < ema_val
            signal = "AYI (Short)"

        if signal:
            dist_pc = ((price - ema_val) / ema_val) * 100
            return {
                "Tikker": ticker, "Siqnal": signal, "Qiymət": round(price, 2),
                "RSI": round(rsi_val, 2), f"EMA({ema_period})": round(ema_val, 2),
                "Həcm X": round(vol_ratio, 2), "Məsafə %": f"{round(dist_pc, 2)}%"
            }
    except Exception as e:
        print(f"Xəta {ticker}: {e}")
    return None

def mail_gonder(results_list, interval):
    # Şifrəni və siyahını təkrar yoxlayaq
    password = os.getenv("MAIL_PASSWORD")
    
    if not results_list:
        print("Siyahı boşdur, mail göndərilmədi.")
        return
    
    if not password:
        print("XƏTA: MAIL_PASSWORD tapılmadı! GitHub Secrets-i yoxlayın.")
        return

    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"🚀 Hesabat ({interval}) - {datetime.now().strftime('%H:%M')}"
        msg['From'] = MAIL_GONDEREN
        msg['To'] = MAIL_ALAN

        html_content = "<html><body><h2 style='text-align:center;'>Texniki Radar</h2>"

        for item in results_list:
            if not isinstance(item, dict): continue
            
            sig_color = "#4CAF50" if "BUĞA" in item.get('Siqnal', '') else "#F44336"

            # EMA dəyərini dinamik olaraq tapırıq
            ema_key = [k for k in item.keys() if 'EMA' in k]
            ema_val = item[ema_key[0]] if ema_key else "N/A"
            
            html_content += f"""
            <div style="border: 1px solid #ddd; border-left: 6px solid {sig_color}; padding: 15px; margin-bottom: 10px; border-radius: 5px;">
                <b style="font-size: 18px;">{item.get('Tikker', 'N/A')}</b> - 
                <span style="color: {sig_color}; font-weight: bold;">{item.get('Siqnal', 'N/A')}</span><br>
                <div style="margin-top: 5px; color: #555;">
                    Qiymət: <b>{item.get('Qiymət', '0')}</b> | RSI: <b>{item.get('RSI', '0')}</b><br>
                    EMA(50) Dəyəri: <b>{ema_val}</b><br>
                    Həcm: <b>{item.get('Həcm X', '0')}x</b> | Məsafə: <b>{item.get('Məsafə %', '0%')}</b>
                </div>
            </div>
            """

        html_content += "</body></html>"
        
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_GONDEREN, password)
            server.send_message(msg)
        print("Mobil-friendly mail uğurla göndərildi.")
        
    except Exception as e:
        print(f"Mail göndərilərkən xəta baş verdi: {e}")
        
def run_scan():
    # Parametrlər funksiyanın daxilində təyin olunur
    target_interval = "4h"
    target_ema = 50
    target_rsi = 14
    target_vol = 1.5
    
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
    "BE","PLUG","HPQ","HPE","DELL","WDC","STX","NTAP","PURE",
    "NTNX","SMTC","IMOS","SIMO","DIOD","HIMX","CEVA","MPWR","LSCC",
    "JPM","BAC","WFC","GS","MS","C","BLK","SCHW","AXP","V","MA","COF",
    "USB","PNC","TFC","MTB","CFG","HBAN","KEY","RF","FITB","STT","BK",
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
    "ASML.AS","ADYEN.AS","INGA.AS","PRX.AS"

     # --- Tier 1: Mega liquidity ---
    "BTC-USD",    # Bitcoin
    "ETH-USD",    # Ethereum
    "BNB-USD",    # BNB
    "SOL-USD",    # Solana
    "XRP-USD",    # XRP
    "DOGE-USD",   # Dogecoin
    "ADA-USD",    # Cardano
    "AVAX-USD",   # Avalanche
    "LINK-USD",   # Chainlink
    "DOT-USD",    # Polkadot
 
    # --- Tier 2: High volume alts ---
    "LTC-USD",    # Litecoin
    "BCH-USD",    # Bitcoin Cash
    "ATOM-USD",   # Cosmos
    "ETC-USD",    # Ethereum Classic
    "FIL-USD",    # Filecoin
    "OP-USD",     # Optimism
    "ARB-USD",    # Arbitrum
    "B-USD",
    "SUI20947-USD",
    "TON11419-USD",
    "ME32197-USD",
    "TRUMP35336-USD",
    "LTC-USD",
    "SOL16116-USD",
    "ONDO-USD",
    "PROS39682-USD",
    "LAB33223-USD",
    "KITE-USD",
    "ASTER36341-USD",
    "AIA38430-USD",
    "SPK36569-USD",
    "UB38339-USD",
    "OSMO-USD",
    "ARB11841-USD",
    "SAGA30372-USD",
    "PHB-USD",
    "STORJ-USD",
    "CGPT-USD",
    "SAHARA-USD",
    "VIRTUAL-USD",
    "POL28321-USD",
    "BSB38889-USD",
        
        
        
 
    # --- Tier 3: Large-cap DeFi / Layer 1 ---
    "SUI-USD",    # Sui
    "SEI-USD",    # Sei
    "TIA-USD",    # Celestia
    "INJ-USD",    # Injective
    "NEAR-USD",   # NEAR Protocol
    "ALGO-USD",   # Algorand
    "HBAR-USD",   # Hedera
    "VET-USD",    # VeChain
    "ICP-USD",    # Internet Computer
 
    # --- Tier 4: Mid-cap high volume ---
    "RUNE-USD",   # THORChain
    "SAND-USD",   # The Sandbox
    "MANA-USD",   # Decentraland
    "AXS-USD",    # Axie Infinity
    "GALA-USD",   # Gala
    "CRV-USD",    # Curve DAO
    "AAVE-USD",   # Aave
    "MKR-USD",    # Maker
    "SNX-USD",    # Synthetix
 
    # --- Tier 5: Trending / meme / narrative ---
    "WIF-USD",    # Dogwifhat
    "BONK-USD",   # Bonk
    "FLOKI-USD",  # Floki
    "SHIB-USD",   # Shiba Inu
    "ORDI-USD",   # Ordinals
    "CFX-USD",    # Conflux
 
    # --- Tier 6: Infrastructure / interop ---
    "LDO-USD",    # Lido DAO
    "PENDLE-USD", # Pendle
    "JTO-USD",    # Jito
    "PYTH-USD",   # Pyth Network
    "JUP-USD",    # Jupiter
    "WEN-USD",    # Wen
    "W-USD",      # Wormhole
    "ENA-USD",    # Ethena
    "ETHFI-USD",  # Ether.fi
    "REZ-USD",    # Renzo
    "4-USD",
    "SKYAI-USD",
    "FLOCK-USD",
    "VANRY-USD",
    "SXT-USD",
    "CHZ-USD",
    "PEPE24478-USD",        
    "MON30495-USD",
    "ARKM-USD",
    "SHIB-USD",
    "XAUT-USD",
    "LAYER35429-USD",
    "AI39883-USD",
        
        
        
        
 
    # --- Tier 7: Gaming / NFT / metaverse ---
    "BEAM-USD",   # Beam
    "MAVIA-USD",  # Heroes of Mavia
    "YGG-USD",    # Yield Guild Games
    "PYR-USD",    # Vulcan Forged
    "LOOKS-USD",  # LooksRare
    "HYPE32196-USD",    
    "USDC-USD",
    "BILL39545-USD",
    "OPG-USD",   
    "UNI7083-USD",
    "XPL-USD",
    "ROBO39595-USD",
    "COMP5692-USD",
    "STABLE38892-USD",
    "TRIA-USD",
 
    # --- Tier 8: Layer 2 / rollups ---
    "MANTA-USD",  # Manta Network
    "ZETA-USD",   # ZetaChain
    "STRK-USD",   # Starknet
    "TAIKO-USD",  # Taiko
    "MODE-USD",   # Mode Network
    "METIS-USD",  # Metis
 
    # --- Tier 9: AI / data / compute ---
    "FET-USD",    # Fetch.ai
    "AGIX-USD",   # SingularityNET
    "OCEAN-USD",  # Ocean Protocol
    "RENDER-USD",   # Render
    "WLD-USD",    # Worldcoin
    "TAO22974-USD",    # Bittensor
    "ATH30083-USD",    # Aethir
    "AIOZ-USD",   # AIOZ Network
    "RSS3-USD",   # RSS3
    "NMR-USD",    # Numeraire
    "IRYS-USD",
    "SUN-USD",
    "ORCA-USD",
        
        
 
    # --- Tier 10: Classic / legacy alts ---
    "XLM-USD",    # Stellar
    "TRX-USD",    # TRON
    "EOS-USD",    # EOS
    "XMR-USD",    # Monero
    "ZEC-USD",    # Zcash
    "DASH-USD",   # Dash
    "XTZ-USD",    # Tezos
    "ICX-USD",    # ICON
    "ONT-USD",    # Ontology    

    ]
    
    results = []
    print(f"Skan başlayır: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for sym in targets:
        # Dəyişənləri burada funksiyaya düzgün ötürürük
        hit = check_symbol(sym, target_interval, target_rsi, target_ema, target_vol)
        if hit:
            results.append(hit)
    
    if results:
        cedvel = tabulate(pd.DataFrame(results), headers="keys", tablefmt="grid", showindex=False)
        print(cedvel) 
        
        # MAIL ÜÇÜN: Siyahının özünü göndəririk (cedvel-i yox!)
        mail_gonder(results, target_interval)
    else:
        print("Uyğun aktiv tapılmadı.")

if __name__ == "__main__":
    run_scan()
