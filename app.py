from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from neo_api_client import NeoAPI
import pyotp

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= KOTAK NEO CREDENTIALS =================
CONSUMER_KEY = "24786b69-9a65-443e-9fe0-34d50f5dbcf1"
MOBILE_NO = "+918910025743" 
PASSWORD = "Raghu@1992" 
TOTP_SECRET = "RU2IFJABQOUYZ7NAYNHDT76BBE" 

client = None

# Ekhane apnar Stock-er nam ebong Kotak-er ID (Instrument Token) map kora ache
TOKEN_MAP = {
    "PAYTM": "11184",
    "TITAN": "3506",
    "INFY": "1594",
    "SIEMENS": "3150",
    "BAJAJFINSV": "16675"
}
REVERSE_TOKEN_MAP = {v: k for k, v in TOKEN_MAP.items()}

# === WebSocket Tick Receiver (Live Data asle eta run hobe) ===
def on_message(message):
    try:
        for tick in message:
            tk = str(tick.get("instrument_token"))
            ltp = float(tick.get("last_traded_price", 0))
            
            # Token miliye Frontend-e sathe sathe push kora hocche
            if tk in REVERSE_TOKEN_MAP and ltp > 0:
                symbol = REVERSE_TOKEN_MAP[tk]
                socketio.emit('live_price', {'symbol': symbol, 'price': ltp})
    except Exception as e:
        print("WS Tick Error:", e)

def on_error(error_message):
    print("WS Error:", error_message)

import requests
import pyotp

def login_kotak():
    print("⏳ Initiating Kotak Neo Login via Direct API...")
    
    # API Endpoints
    login_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
    validate_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
    
    live_otp = pyotp.TOTP(TOTP_SECRET).now()
    
    # Step 1: Login Headers & Body (As per documentation)
    headers = {
        "Authorization": f"Bearer {CONSUMER_KEY}", # Ba apnar dashboard-er plain token
        "neo-fin-key": "neotradeapi",
        "Content-Type": "application/json"
    }
    
    payload = {
        "mobileNumber": f"+91{MOBILE_NO}", # +91 thaka baddhotamulok
        "ucc": "APNAR_UCC_EKHANE_DIN",
        "totp": live_otp
    }
    
    try:
        # Request for Step 1
        response = requests.post(login_url, headers=headers, json=payload)
        data = response.json()
        
        if data.get("status") == "success" or "data" in data:
            print("✅ Step 1 Success: Received View Token & SID")
            sid = data["data"]["sid"]
            view_token = data["data"]["token"]
            
            # Step 2: Validate MPIN Headers & Body
            val_headers = headers.copy()
            val_headers["sid"] = sid
            val_headers["Auth"] = view_token
            
            val_payload = {
                "ucc": "YMPX5",
                "mpin": "073207"
            }
            
            # Request for Step 2
            val_response = requests.post(validate_url, headers=val_headers, json=val_payload)
            val_data = val_response.json()
            
            if val_data.get("status") == "success" or "data" in val_data:
                 print("✅ Kotak Neo Direct Login Complete! Received Trade Token.")
                 # Ekhane apnar WebSocket code start korte paren
            else:
                 print("❌ MPIN Validation Failed:", val_data)
        else:
            print("❌ Login Failed:", data)
            
    except Exception as e:
        print("❌ API Error:", e)
        
@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    symbols = data.get('symbols', [])
    
    instruments = []
    for sym in symbols:
        tk = TOKEN_MAP.get(sym)
        if tk:
            instruments.append({"instrument_token": str(tk), "exchange_segment": "nse_cm"})
    
    # Kotak ke bola hocche ei stock gulor live tick pathate
    if instruments and client:
        try:
            client.subscribe(instrument_tokens=instruments)
            print(f"📡 Subscribed to Live WS: {instruments}")
        except Exception as e:
            print("Subscribe Error:", e)
            
    return jsonify({"status": "success", "subscribed": symbols})

if __name__ == '__main__':
    import os
    login_kotak()
    print("🚀 Real-Time Server running...")
    
    # Render-er deya dynamic port ebong 0.0.0.0 host use kora hocche
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
