import os
import time
import threading
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
TOTP_SECRET = "5E3VUH7R5LU576UBAHQENFZVNA"

# ==========================================
# STOCK TOKEN MAP (NSE Cash Segment Tokens)
# Apnar aro stock thakle ekhane add korte parben
# ==========================================
TOKEN_MAP = {
    "KPITTECH": "9683",
    "IRCTC": "13611",
    "DOMS": "20551",
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
    "BHARTIARTL": "10604"
}
REVERSE_TOKEN_MAP = {str(v): k for k, v in TOKEN_MAP.items()}

# Active subscribed symbols (Default-e dashboard-er stock gulo deya thaklo)
SUBSCRIBED_SYMBOLS = set(TOKEN_MAP.keys())

# Global Session Data
SESSION_DATA = {
    "trade_token": None,
    "sid": None,
    "base_url": "https://gw-napi.kotaksecurities.com"
}

def login_kotak():
    print("⏳ Initiating Kotak Neo Login via Direct API...")
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
            print("✅ Step 1 Success: Received View Token & SID")
            sid = data["data"]["sid"]
            view_token = data["data"]["token"]
            
            val_headers = headers.copy()
            val_headers["sid"] = sid
            val_headers["Auth"] = view_token
            
            val_payload = {
                "ucc": UCC,
                "mpin": MPIN
            }
            
            val_response = requests.post(validate_url, headers=val_headers, json=val_payload, timeout=10)
            val_data = val_response.json()
            
            if val_data.get("status") == "success" or "data" in val_data:
                print("✅ Kotak Neo Direct Login Complete! Server is ready.")
                SESSION_DATA["trade_token"] = val_data["data"]["token"]
                SESSION_DATA["sid"] = val_data["data"].get("sid", sid)
                if "baseUrl" in val_data["data"] and val_data["data"]["baseUrl"]:
                    SESSION_DATA["base_url"] = val_data["data"]["baseUrl"].rstrip("/")
                return True
            else:
                print("❌ MPIN Validation Failed:", val_data)
        else:
            print("❌ Login Failed:", data)
            
    except Exception as e:
        print("❌ API Error:", e)
    return False


def fetch_and_broadcast_prices():
    """Background worker je prottek 2 second-e Kotak Quotes API theke Live CMP, Change o % Change pathabe"""
    print("📡 Starting Live Price Broadcaster Thread...")
    while True:
        try:
            if not SESSION_DATA["trade_token"]:
                time.sleep(5)
                continue

            # Subscribed symbols theke Kotak query banano (e.g., nse_cm|9683,nse_cm|13611)
            queries = []
            for sym in list(SUBSCRIBED_SYMBOLS):
                tk = TOKEN_MAP.get(sym)
                if tk:
                    queries.append(f"nse_cm|{tk}")

            if not queries:
                time.sleep(2)
                continue

            query_str = ",".join(queries)
            quotes_url = f"{SESSION_DATA['base_url']}/apim/quotes/1.0/quotes/neosymbol/{query_str}/all"

            headers = {
                "Authorization": CONSUMER_KEY,
                "Content-Type": "application/json",
                "Auth": SESSION_DATA["trade_token"],
                "sid": SESSION_DATA["sid"],
                "neo-fin-key": "neotradeapi"
            }

            resp = requests.get(quotes_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                quotes_list = resp.json()
                # Kotak Quotes API list of dicts return kore
                if isinstance(quotes_list, dict) and "data" in quotes_list:
                    quotes_list = quotes_list["data"]

                if isinstance(quotes_list, list):
                    for item in quotes_list:
                        tk = str(item.get("exchange_token") or item.get("tk") or "")
                        sym = REVERSE_TOKEN_MAP.get(tk) or item.get("display_symbol") or item.get("symbol")
                        if not sym:
                            continue

                        ltp = float(item.get("ltp") or 0)
                        # Previous close price
                        prev_close = float(
                            item.get("ohlc", {}).get("close")
                            or item.get("prev_close")
                            or item.get("c")
                            or ltp
                        )

                        # Value change & Percentage change calculation
                        val_change = float(item.get("change") or (ltp - prev_close))
                        pct_change = float(
                            item.get("per_change")
                            or ((val_change / prev_close) * 100 if prev_close > 0 else 0.0)
                        )

                        if ltp > 0:
                            socketio.emit('live_price', {
                                'symbol': sym,
                                'price': round(ltp, 2),
                                'change': round(val_change, 2),
                                'pchange': round(pct_change, 2)
                            })
            elif resp.status_code in (401, 403):
                print("🔄 Session token expired, re-logging in...")
                login_kotak()

        except Exception as e:
            print("⚠️ Price Fetch Error:", e)

        time.sleep(2)


@app.route('/api/subscribe', methods=['POST', 'OPTIONS'])
def subscribe():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    data = request.json or {}
    symbols = data.get('symbols', [])
    
    for sym in symbols:
        sym_clean = str(sym).upper().strip()
        SUBSCRIBED_SYMBOLS.add(sym_clean)
        
    print(f"✅ Subscribed Symbols Updated: {list(SUBSCRIBED_SYMBOLS)}")
    return jsonify({
        "status": "subscribed",
        "subscribed_symbols": list(SUBSCRIBED_SYMBOLS)
    }), 200


@app.route('/')
def home():
    return "✅ Quantum Backend is Live and Running!"


# Server চালু হওয়ার সাথে সাথেই Login এবং Price Thread স্টার্ট হবে (Gunicorn বা python app.py দুটোতেই কাজ করবে)
def start_background_services():
    login_kotak()
    t = threading.Thread(target=fetch_and_broadcast_prices, daemon=True)
    t.start()

start_background_services()

if __name__ == '__main__':
    print("🚀 Starting Web Server...")
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
