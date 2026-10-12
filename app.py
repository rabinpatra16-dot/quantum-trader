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

def login_kotak():
    global client
    try:
        print("⏳ Connecting to Kotak Neo Live WebSocket...")
        
        # Ekhane on_message ar on_error baad deya hoyeche
        client = NeoAPI(consumer_key=CONSUMER_KEY, environment='prod')
        client.login(mobilenumber=MOBILE_NO, password=PASSWORD)
        
        live_otp = pyotp.TOTP(TOTP_SECRET).now()
        client.session_2fa(live_otp)
        
        # Notun niyome alada kore on_message set kora hocche
        client.on_message = on_message
        client.on_error = on_error
        
        print("✅ Kotak Neo WebSocket Login Success!")
    except Exception as e:
        print("❌ Login Error:", e)

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
