import os
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
TOTP_SECRET = "W627DHISMLVJNAGLR2BSOE3UQM"

# ==========================================
# STOCK TOKEN MAP (NSE Cash Segment Tokens)
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

SUBSCRIBED_SYMBOLS = set(TOKEN_MAP.keys())

SESSION_DATA = {
    "trade_token": None,
    "sid": None,
    "base_url": "https://gw-napi.kotaksecurities.com"
}

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
                print(f"🔗 Using Base URL: {SESSION_DATA['base_url']}", flush=True)
                return True
            else:
                print("❌ MPIN Validation Failed:", val_data, flush=True)
        else:
            print("❌ Login Failed:", data, flush=True)
            
    except Exception as e:
        print("❌ API Error:", e, flush=True)
    return False


def fetch_quotes_once(debug=False):
    """Kotak theke ekbar quotes fetch kore return korbe"""
    queries = []
    for sym in list(SUBSCRIBED_SYMBOLS):
        tk = TOKEN_MAP.get(sym)
        if tk:
            queries.append(f"nse_cm|{tk}")

    if not queries:
        return None

    # URL encode pipe character (|) as %7C and raw both
    raw_query = ",".join(queries)
    encoded_query = urllib.parse.quote(raw_query, safe=",")
    base = SESSION_DATA["base_url"]

    urls_to_try = [
        f"{base}/script-details/1.0/quotes/neosymbol/{raw_query}/all",
        f"{base}/script-details/1.0/quotes/neosymbol/{encoded_query}/all",
        f"{base}/apim/quotes/1.0/quotes/neosymbol/{raw_query}/all",
        f"https://mis.kotaksecurities.com/script-details/1.0/quotes/neosymbol/{raw_query}/all"
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
                print(f"🔍 Quotes API [{resp.status_code}] -> {url[:65]}... : {resp.text[:250]}", flush=True)
            if resp.status_code == 200:
                return resp.json()
        except Exception as err:
            if debug:
                print(f"⚠️ URL Try Error ({url[:40]}): {err}", flush=True)
    return None


def fetch_and_broadcast_prices():
    """SocketIO Background Task je prottek 3 second-e price broadcast korbe"""
    print("📡 Starting Live Price Broadcaster Thread...", flush=True)
    first_run = True
    
    while True:
        try:
            if not SESSION_DATA["trade_token"]:
                socketio.sleep(3)
                continue

            quotes_list = fetch_quotes_once(debug=first_run)
            first_run = False

            if quotes_list:
                if isinstance(quotes_list, dict) and "data" in quotes_list:
                    quotes_list = quotes_list["data"]

                if isinstance(quotes_list, list):
                    for item in quotes_list:
                        tk = str(item.get("exchange_token") or item.get("tk") or "")
                        sym = REVERSE_TOKEN_MAP.get(tk) or item.get("display_symbol") or item.get("symbol")
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
        sym_clean = str(sym).upper().strip()
        SUBSCRIBED_SYMBOLS.add(sym_clean)
        
    print(f"✅ Subscribed Symbols Updated: {list(SUBSCRIBED_SYMBOLS)}", flush=True)
    return jsonify({
        "status": "subscribed",
        "subscribed_symbols": list(SUBSCRIBED_SYMBOLS)
    }), 200


@app.route('/api/test-quotes')
def test_quotes():
    """Browser theke direct check korar jonno Kotak ki data pathachhe"""
    res = fetch_quotes_once(debug=True)
    return jsonify({
        "base_url": SESSION_DATA["base_url"],
        "logged_in": bool(SESSION_DATA["trade_token"]),
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
