import os
import requests
import pyotp
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# threading mode e server chalale free tier e RAM kom khay
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading') 

# ==========================================
# APNAR CREDENTIALS EKHANE BOSABEN
# ==========================================
CONSUMER_KEY = "24786b69-9a65-443e-9fe0-34d50f5dbcf1"
MOBILE_NO = "8910025743" # +91 chhara bosaben
UCC = "YMPX5" 
MPIN = "073207"
TOTP_SECRET = "5E3VUH7R5LU576UBAHQENFZVNA"

def login_kotak():
    print("⏳ Initiating Kotak Neo Login via Direct API...")
    
    # Kotak er ashol login endpoints
    login_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
    validate_url = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
    
    live_otp = pyotp.TOTP(TOTP_SECRET).now()
    
    # Step 1: Login Headers & Body (As per documentation)
    headers = {
        "Authorization": f"Bearer {CONSUMER_KEY}", # Jodi error dey, tahole shudhu f"{CONSUMER_KEY}" try korben
        "neo-fin-key": "neotradeapi",
        "Content-Type": "application/json"
    }
    
    payload = {
        "mobileNumber": f"+91{MOBILE_NO}", # +91 thaka baddhotamulok
        "ucc": UCC,
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
                "ucc": UCC,
                "mpin": MPIN
            }
            
            # Request for Step 2
            val_response = requests.post(validate_url, headers=val_headers, json=val_payload)
            val_data = val_response.json()
            
            if val_data.get("status") == "success" or "data" in val_data:
                 print("✅ Kotak Neo Direct Login Complete! Server is ready.")
                 trade_token = val_data["data"]["token"]
                 # Ebar ekhane WebSocket theke data tanar custom kaj shuru korte paren jodi dorkar hoy
            else:
                 print("❌ MPIN Validation Failed:", val_data)
        else:
            print("❌ Login Failed:", data)
            
    except Exception as e:
        print("❌ API Error:", e)

# ==========================================
# Ekhane apnar aager toiri kora /api/subscribe ebong on_message 
# function gulo rekhe deben. Segulo ami change korlam na.
# ==========================================

@app.route('/')
def home():
    return "✅ Quantum Backend is Live and Running!"

if __name__ == '__main__':
    login_kotak()
    print("🚀 Starting Web Server...")
    
    # Render-er deya dynamic port use korchi jate "No open ports" error na ashe
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
