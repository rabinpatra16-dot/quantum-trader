from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import threading

app = Flask(__name__)
CORS(app)
# SocketIO সেটআপ (যেকোনো ডোমেইন থেকে কানেক্ট করার পারমিশন দেওয়া হলো)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

CLIENT_ID = "A735DXMG83-100"  
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." # আপনার পুরো টোকেনটি এখানে থাকবে
WS_TOKEN = f"{CLIENT_ID}:{ACCESS_TOKEN}"

# ==========================================
# FYERS WEBSOCKET LOGIC
# ==========================================
fyers_ws = None

def onmessage(message):
    """
    যখনই Fyers থেকে নতুন দাম আসবে, এটি সাথে সাথে ফ্রন্টএন্ডে পুশ করে দেবে।
    """
    if 'ltp' in message:
        # ডেটা ফরম্যাট করে ফ্রন্টএন্ডে পাঠানো হচ্ছে
        clean_data = {
            'symbol': message['symbol'].split(':')[1].split('-')[0], # e.g. NSE:RELIANCE-EQ -> RELIANCE
            'price': message['ltp']
        }
        socketio.emit('live_price', clean_data)

def onerror(message):
    print("WebSocket Error:", message)

def onclose(message):
    print("WebSocket Closed:", message)

def onopen():
    print("Connected to Fyers WebSocket")

# Fyers WebSocket ইনিশিয়ালাইজেশন
fyers_ws = data_ws.FyersDataSocket(
    access_token=WS_TOKEN,
    log_path="",
    litemode=True,
    write_to_file=False,
    reconnect=True,
    on_connect=onopen,
    on_close=onclose,
    on_error=onerror,
    on_message=onmessage
)

def start_fyers_ws():
    fyers_ws.connect()

# ব্যাকগ্রাউন্ডে Fyers WebSocket চালু করা হলো
threading.Thread(target=start_fyers_ws, daemon=True).start()

# ==========================================
# SYMBOL FORMATTING & ROUTES
# ==========================================
def format_fyers_symbol(frontend_symbol):
    sym = frontend_symbol.replace('.NS', '').upper().strip()
    if sym == 'NIFTY': return 'NSE:NIFTY50-INDEX'
    elif sym == 'BANKNIFTY': return 'NSE:NIFTYBANK-INDEX'
    else: return f"NSE:{sym}-EQ"

@app.route('/api/subscribe', methods=['POST'])
def subscribe_symbols():
    """
    ফ্রন্টএন্ড থেকে নতুন ট্রেড নিলে সেই সিম্বলটি WebSocket-এ সাবস্ক্রাইব করার জন্য।
    """
    data = request.json
    symbols = data.get('symbols', [])
    formatted_symbols = [format_fyers_symbol(s) for s in symbols if format_fyers_symbol(s)]
    
    if formatted_symbols and fyers_ws:
        fyers_ws.subscribe(data_type="SymbolUpdate", symbol=formatted_symbols)
        return jsonify({'status': 'success', 'message': f'Subscribed to {formatted_symbols}'})
    return jsonify({'status': 'error', 'message': 'Invalid symbols'})

if __name__ == '__main__':
    # Flask এর বদলে socketio.run ব্যবহার করতে হবে
    socketio.run(app, host='0.0.0.0', port=5000)
