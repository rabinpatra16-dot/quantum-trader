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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

CLIENT_ID = "A735DXMG83-100"

# ==========================================
# FIREBASE SETUP
# ==========================================
try:
    if not firebase_admin._apps:
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
# FYERS API & WEBSOCKET LOGIC
# ==========================================
fyers_ws = None
fyers_api = None # Quotes API-এর জন্য নতুন ভেরিয়েবল

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
    global fyers_ws, fyers_api
    token = get_token_from_firebase()
    if not token:
        print("No token found in Firebase!")
        return
        
    # Quotes API সেটআপ করা হলো
    fyers_api = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=token, log_path="")
    
    WS_TOKEN = f"{CLIENT_ID}:{token}"
    fyers_ws = data_ws.FyersDataSocket(
        access_token=WS_TOKEN, log_path="", litemode=True, write_to_file=False, reconnect=True,
        on_connect=onopen, on_close=onclose, on_error=onerror, on_message=onmessage
    )
    fyers_ws.connect()

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
    
    if formatted_symbols:
        # ১. মার্কেট বন্ধ থাকলেও যেন দাম আসে, তার জন্য Quotes API থেকে দাম টেনে পাঠানো হচ্ছে
        if fyers_api:
            try:
                quotes_data = {"symbols": ",".join(formatted_symbols)}
                res = fyers_api.quotes(data=quotes_data)
                if res and res.get('s') == 'ok':
                    for item in res.get('d', []):
                        symbol_name = item['n'].split(':')[1].split('-')[0]
                        ltp = item['v']['lp']
                        # সাথে সাথে ড্যাশবোর্ডে দাম পাঠিয়ে দেওয়া হচ্ছে
                        socketio.emit('live_price', {'symbol': symbol_name, 'price': ltp})
            except Exception as e:
                print("Quotes API Error:", e)
        
        # ২. লাইভ মার্কেটের জন্য WebSocket-এ সাবস্ক্রাইব করা হচ্ছে
        if fyers_ws:
            fyers_ws.subscribe(data_type="SymbolUpdate", symbols=formatted_symbols)
            
        return jsonify({'status': 'success'})
        
    return jsonify({'status': 'error'})

@app.route('/api/reload_token', methods=['GET'])
def reload_token():
    global fyers_ws
    if fyers_ws:
        fyers_ws.close()
    threading.Thread(target=start_fyers_ws, daemon=True).start()
    return jsonify({'status': 'success', 'message': 'WebSocket Restarted!'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
