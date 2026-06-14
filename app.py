from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import threading
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

CLIENT_ID = "A735DXMG83-100"

# ==========================================
# FIREBASE SETUP
# ==========================================
try:
    if not firebase_admin._apps:
        # ডাউনলোড করা JSON ফাইলটি দিয়ে ফায়ারবেস কানেক্ট করা হচ্ছে
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://quantum-tracker-6fe30-default-rtdb.firebaseio.com/'
        })
except Exception as e:
    print("Firebase Init Error:", e)

def get_token_from_firebase():
    try:
        return db.reference('admin_settings/fyers_token').get()
    except:
        return None

# ==========================================
# FYERS WEBSOCKET LOGIC
# ==========================================
fyers_ws = None

def onmessage(message):
    if 'ltp' in message:
        clean_data = {
            'symbol': message['symbol'].split(':')[1].split('-')[0],
            'price': message['ltp']
        }
        socketio.emit('live_price', clean_data)

def onerror(message): print("WebSocket Error:", message)
def onclose(message): print("WebSocket Closed:", message)
def onopen(): print("Connected to Fyers WebSocket")

def start_fyers_ws():
    global fyers_ws
    token = get_token_from_firebase() # ফায়ারবেস থেকে টোকেন নিচ্ছে
    if not token:
        print("No token found in Firebase!")
        return
        
    WS_TOKEN = f"{CLIENT_ID}:{token}"
    fyers_ws = data_ws.FyersDataSocket(
        access_token=WS_TOKEN, log_path="", litemode=True, write_to_file=False, reconnect=True,
        on_connect=onopen, on_close=onclose, on_error=onerror, on_message=onmessage
    )
    fyers_ws.connect()

# সার্ভার চালু হওয়ার সাথে সাথে WebSocket কানেক্ট হবে
threading.Thread(target=start_fyers_ws, daemon=True).start()

# ==========================================
# ROUTES
# ==========================================
def format_fyers_symbol(frontend_symbol):
    sym = frontend_symbol.replace('.NS', '').upper().strip()
    if sym == 'NIFTY': return 'NSE:NIFTY50-INDEX'
    elif sym == 'BANKNIFTY': return 'NSE:NIFTYBANK-INDEX'
    else: return f"NSE:{sym}-EQ"

@app.route('/api/subscribe', methods=['POST'])
def subscribe_symbols():
    data = request.json
    symbols = data.get('symbols', [])
    formatted_symbols = [format_fyers_symbol(s) for s in symbols if format_fyers_symbol(s)]
    if formatted_symbols and fyers_ws:
        fyers_ws.subscribe(data_type="SymbolUpdate", symbols=formatted_symbols)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

# ==========================================
# PREVIOUS CLOSE PRICE (FYERS QUOTES API)
# ==========================================
@app.route('/api/prev-close', methods=['POST'])
def prev_close():
    data = request.json
    symbols = data.get('symbols', [])
    if not symbols:
        return jsonify({'status': 'error', 'message': 'No symbols provided'})

    token = get_token_from_firebase()
    if not token:
        return jsonify({'status': 'error', 'message': 'No Fyers token found'})

    try:
        fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=token, is_async=False, log_path="")

        formatted_symbols = [format_fyers_symbol(s) for s in symbols]
        symbols_str = ",".join(formatted_symbols)

        response = fyers.quotes({"symbols": symbols_str})

        result = {}
        if response.get('s') == 'ok':
            for item, original_symbol in zip(response.get('d', []), symbols):
                v = item.get('v', {})
                result[original_symbol] = v.get('prev_close_price')

        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# নতুন টোকেন আসলে সার্ভারকে রিস্টার্ট করার রুট
@app.route('/api/reload_token', methods=['GET'])
def reload_token():
    global fyers_ws
    if fyers_ws:
        fyers_ws.close() # পুরানো কানেকশন বন্ধ
    threading.Thread(target=start_fyers_ws, daemon=True).start() # নতুন টোকেন দিয়ে চালু
    return jsonify({'status': 'success', 'message': 'WebSocket Restarted with New Token!'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
