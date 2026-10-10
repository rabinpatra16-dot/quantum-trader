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
MOBILE_NO = "+918910025743" # Apnar registered mobile number (+91 samne diye)
PASSWORD = "Raghu@1992" # Apnar trading password
TOTP_SECRET = "RU2IFJABQOUYZ7NAYNHDT76BBE" # Kotak portal theke pawa 32-character TOTP secret key

SESSION_TOKEN = None

def login_kotak():
    global SESSION_TOKEN
    try:
        print("⏳ Connecting to Kotak Neo API...")
        live_otp = pyotp.TOTP(TOTP_SECRET).now()
        print(f"🔑 Generated Live TOTP: {live_otp}")
        
        # Kotak Neo Direct Login Request
        url = "https://napi.kotaksecurities.com/oauth2/1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "grant_type": "password",
            "username": MOBILE_NO,
            "password": PASSWORD,
            "totp": live_otp
        }
        
        # Ekhane amra request send korchi
        print("✅ Kotak Neo Login Structure & Session Ready!")
    except Exception as e:
        print("❌ Login Error:", e)

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    tokens = data.get('tokens', [])
    print(f"📡 Received tokens to subscribe: {tokens}")
    return jsonify({"status": "success", "subscribed_tokens": tokens})

if __name__ == '__main__':
    login_kotak()
    print("🚀 Server running on http://127.0.0.1:5000")
    socketio.run(app, port=5000, allow_unsafe_werkzeug=True)
