from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import requests
import pyotp

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= KOTAK NEO CREDENTIALS =================
CONSUMER_KEY = "24786b69-9a65-443e-9fe0-34d50f5dbcf1"
MOBILE_NO = "+918910025743" 
PASSWORD = "Raghu@1992" 
TOTP_SECRET = "RU2IFJABQOUYZ7NAYNHDT76BBE" 

SESSION_TOKEN = None

def login_kotak():
    global SESSION_TOKEN
    try:
        print("⏳ Preparing Backend API...")
        live_otp = pyotp.TOTP(TOTP_SECRET).now()
        print(f"🔑 Generated Live TOTP: {live_otp}")
        print("✅ Backend Server Started Successfully!")
    except Exception as e:
        print("❌ Login Error:", e)

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    tokens = data.get('tokens', [])
    print(f"📡 Received symbols to subscribe: {tokens}")
    return jsonify({"status": "success", "subscribed_tokens": tokens})

@app.route('/api/quote', methods=['POST'])
def get_static_quote():
    try:
        data = request.json
        symbols = data.get('symbols', [])
        quotes = {}
        
        # Authentic NSE live/closing price fetcher (Fallback API)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        for sym in symbols:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS"
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                price = res.json()['chart']['result'][0]['meta']['regularMarketPrice']
                quotes[sym] = price
                
        return jsonify({"status": "success", "quotes": quotes})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    login_kotak()
    print("🚀 Server running on port 5000")
    socketio.run(app, port=5000, allow_unsafe_werkzeug=True)
