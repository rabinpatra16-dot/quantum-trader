import os
import csv
import io
import urllib.parse
import requests
import pyotp
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ==========================================
# APNAR CREDENTIALS
# ==========================================
CONSUMER_KEY = "24786b69-9a65-443e-9fe0-34d50f5dbcf1"
MOBILE_NO = "8910025743"
UCC = "YMPX5"
MPIN = "073207"
TOTP_SECRET = "W627DHISMLVJNAGLR2BSOE3UQM" # Apnar latest working TOTP Secret

# ==========================================
# DEFAULT FALLBACK STOCK TOKEN MAP (NSE Equity)
# ==========================================
TOKEN_MAP = {
    "KPITTECH": "9683",
    "IRCTC": "13611",
    "DOMS": "20555",
    "MAZDOCK": "509",
    "CUPID": "9790",
    "TITAN": "3506",
    "BAJAJFINSV": "16675",
    "SIEMENS": "3150",
    "RELIANCE": "2885",
    "TCS": "11536",
    "HDFCBANK": "1333",
    "INFY": "1594",
    "SBIN": "3045",
    "ICICIBANK": "4963",
    "TATAMOTORS": "3456",
    "ITC": "1660",
    "LT": "11483",
    "AXISBANK": "5900",
    "KOTAKBANK": "1922",
    "BHARTIARTL": "10604",
    "ZOMATO": "5097",
    "HAL": "2303",
    "BEL": "383",
    "TRENT": "1964",
    "CDSL": "21174",
    "BSE": "19585",
    "IREDA": "20261",
    "JIOFIN": "18143",
    "TATAPOWER": "3426",
    "TATASTEEL": "3499"
}
REVERSE_TOKEN_MAP = {str(v): k for k, v in TOKEN_MAP.items()}

# Active subscribed symbols
SUBSCRIBED_SYMBOLS = set([
    "KPITTECH", "IRCTC", "DOMS", "MAZDOCK", 
    "CUPID", "TITAN", "BAJAJFINSV", "SIEMENS"
])

SESSION_DATA = {
    "trade_token": None,
    "sid": None,
    "base_url": "https://gw-napi.kotaksecurities.com"
}


def load_nse_master_tokens():
    """Kotak-er Scrip Master theke shob NSE EQ stock-er sothik token auto load korbe (No Pandas needed!)"""
    try:
        print("📥 Fetching Kotak NSE Scrip Master file paths...", flush=True)
        paths_url = f"{SESSION_DATA['base_url']}/script-details/1.0/masterscrip/file-paths"
        headers = {
            "Authorization": CONSUMER_KEY,
            "Content-Type": "application/json"
        }
        resp = requests.get(paths_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            files = data.get("data", {}).get("filesPaths", [])
            nse_cm_url = next((f for f in files if "nse_cm" in f.lower()), None)
            
            if nse_cm_url:
                print(f"📥 Downloading NSE Master CSV from: {nse_cm_url}", flush=True)
                csv_resp = requests.get(nse_cm_url, timeout=15)
                if csv_resp.status_code == 200:
                    reader = csv.DictReader(io.StringIO(csv_resp.text))
                    count = 0
                    for row in reader:
                        # Clean keys & values
                        row_clean = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
                        # Shudhu Equity (EQ / BE) series-er token nebe
                        trd_sym = row_clean.get("pTrdSymbol", "")
                        sym_name = row_clean.get("pSymbolName", "").upper()
                        token = row_clean.get("pSymbol", "")
                        group = row_clean.get("pGroup", "").upper()
                        
                        if token and (trd_sym.endswith("-EQ") or group == "EQ"):
                            clean_name = trd_sym.replace("-EQ", "").upper() if trd_sym else sym_name
                            if clean_name:
                                TOKEN_MAP[clean_name] = str(token)
                                REVERSE_TOKEN_MAP[str(token)] = clean_name
                                count += 1
                    print(f"✅ Auto-loaded {count} NSE Equity stock tokens successfully!", flush=True)
    except Exception as e:
        print("⚠️ Scrip Master Auto-Load Warning:", e, flush=True)


def login_kotak():
    print("⏳ Initiating Kotak Neo Login via Direct API...", flush=True)
    login_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
    validate_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
    
    live_otp = pyotp.TOTP(TOTP_SECRET).now()
    
    headers = {
        "Authorization": CONSUMER_KEY,
        "neo-fin-key": "neotradeapi",
        "Content-Type": "application/json"
    }
    
    payload = {
        "mobileNumber": f"+91{MOBILE_NO}",
        "ucc": UCC,
        "totp": live_otp
    }
    
    try:
        response = requests.post(login_url, headers=headers, json=payload, timeout=10)
        data = response.json()
        
        if data.get("status") == "success" or "data" in data:
            print("✅ Step 1 Success: Received View Token & SID", flush=True)
            sid = data["data"]["sid"]
            view_token = data["data"]["token"]
            
            val_headers = headers.copy()
            val_headers["sid"] = sid
            val_headers["Auth"] = view_token
            
            val_payload = {
                "mpin": MPIN
            }
            
            val_response = requests.post(validate_url, headers=val_headers, json=val_payload, timeout=10)
            val_data = val_response.json()
            
            if val_data.get("status") == "success" or "data" in val_data:
                print("✅ Kotak Neo Direct Login Complete! Server is ready.", flush=True)
                SESSION_DATA["trade_token"] = val_data["data"]["token"]
                SESSION_DATA["sid"] = val_data["data"].get("sid", sid)
                if "baseUrl" in val_data["data"] and val_data["data"]["baseUrl"]:
                    SESSION_DATA["base_url"] = val_data["data"]["baseUrl"].rstrip("/")
                
                # Login hoye gelei shob stock-er sothik token auto load kore nebe
                load_nse_master_tokens()
                return True
            else:
                print("❌ MPIN Validation Failed:", val_data, flush=True)
        else:
            print("❌ Login Failed:", data, flush=True)
            
    except Exception as e:
        print("❌ API Error:", e, flush=True)
    return False


def fetch_quotes_once(debug=False):
    queries = []
    missing_syms = []
    for sym in list(SUBSCRIBED_SYMBOLS):
        tk = TOKEN_MAP.get(sym)
        if tk:
            queries.append(f"nse_cm|{tk}")
        else:
            missing_syms.append(sym)

    if debug and missing_syms:
        print(f"⚠️ Tokens missing for symbols: {missing_syms}", flush=True)

    if not queries:
        return None

    raw_query = ",".join(queries)
    encoded_query = urllib.parse.quote(raw_query, safe=",")
    base = SESSION_DATA["base_url"]

    urls_to_try = [
        f"{base}/script-details/1.0/quotes/neosymbol/{raw_query}/all",
        f"{base}/script-details/1.0/quotes/neosymbol/{encoded_query}/all",
        f"{base}/apim/quotes/1.0/quotes/neosymbol/{raw_query}/all"
    ]

    headers = {
        "Authorization": CONSUMER_KEY,
        "Content-Type": "application/json",
        "neo-fin-key": "neotradeapi",
        "Auth": SESSION_DATA["trade_token"],
        "sid": SESSION_DATA["sid"]
    }

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if debug:
                print(f"🔍 Quotes API [{resp.status_code}] -> {url[:65]}...", flush=True)
            if resp.status_code == 200:
                return resp.json()
        except Exception as err:
            if debug:
                print(f"⚠️ URL Try Error: {err}", flush=True)
    return None


def fetch_and_broadcast_prices():
    print("📡 Starting Live Price Broadcaster Thread...", flush=True)
    first_run = True
    
    while True:
        try:
            if not SESSION_DATA["trade_token"]:
                print("🔄 Waiting 32s for fresh TOTP window to retry login...", flush=True)
                socketio.sleep(32)
                login_kotak()
                continue

            quotes_list = fetch_quotes_once(debug=first_run)
            first_run = False

            if quotes_list:
                if isinstance(quotes_list, dict) and "data" in quotes_list:
                    quotes_list = quotes_list["data"]

                if isinstance(quotes_list, list):
                    for item in quotes_list:
                        tk = str(item.get("exchange_token") or item.get("tk") or "")
                        # Display symbol ba REVERSE_TOKEN_MAP theke sothik nam ber kora
                        raw_sym = str(item.get("display_symbol") or item.get("symbol") or "").replace("-EQ", "").strip().upper()
                        sym = REVERSE_TOKEN_MAP.get(tk) or raw_sym
                        if not sym:
                            continue

                        ltp = float(item.get("ltp") or item.get("last_traded_price") or 0)
                        ohlc = item.get("ohlc") or {}
                        prev_close = float(
                            ohlc.get("close")
                            or item.get("prev_close")
                            or item.get("c")
                            or ltp
                        )

                        val_change = float(item.get("change") or (ltp - prev_close))
                        pct_change = float(
                            item.get("per_change")
                            or ((val_change / prev_close) * 100 if prev_close > 0 else 0.0)
                        )

                        if ltp > 0:
                            payload_data = {
                                'symbol': sym,
                                'tk': tk,
                                'price': round(ltp, 2),
                                'ltp': round(ltp, 2),
                                'change': round(val_change, 2),
                                'pchange': round(pct_change, 2)
                            }
                            socketio.emit('live_price', payload_data)
                            socketio.emit('price_update', payload_data)
                            socketio.emit('tick', payload_data)
        except Exception as e:
            print("⚠️ Price Fetch Loop Error:", e, flush=True)

        socketio.sleep(3)


@app.route('/api/subscribe', methods=['POST', 'OPTIONS'])
def subscribe():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    data = request.json or {}
    symbols = data.get('symbols', [])
    
    for sym in symbols:
        # 'NSE:KPITTECH-EQ' ba 'KPITTECH' -> shudhu 'KPITTECH' rakha
        sym_clean = str(sym).upper().strip().split(":")[-1].replace("-EQ", "")
        SUBSCRIBED_SYMBOLS.add(sym_clean)
        
    print(f"✅ Subscribed Symbols Updated: {list(SUBSCRIBED_SYMBOLS)}", flush=True)
    return jsonify({
        "status": "subscribed",
        "subscribed_symbols": list(SUBSCRIBED_SYMBOLS)
    }), 200


@app.route('/api/test-quotes')
def test_quotes():
    if not SESSION_DATA["trade_token"]:
        login_kotak()
    res = fetch_quotes_once(debug=True)
    return jsonify({
        "subscribed_symbols": list(SUBSCRIBED_SYMBOLS),
        "mapped_tokens": {s: TOKEN_MAP.get(s) for s in SUBSCRIBED_SYMBOLS},
        "quotes_response": res
    })


@app.route('/')
def home():
    return "✅ Quantum Backend is Live and Running!"


if __name__ == '__main__':
    login_kotak()
    socketio.start_background_task(fetch_and_broadcast_prices)
    print("🚀 Starting Web Server...", flush=True)
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
