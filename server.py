from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
import datetime

app = Flask(__name__)
CORS(app) 

# সিম্বল ঠিক করার ফাংশন (যাতে NIFTY লিখলে Yahoo Finance বুঝতে পারে)
def get_yf_symbol(symbol):
    symbol = symbol.upper()
    if symbol == "NIFTY": return "^NSEI"
    if symbol == "BANKNIFTY": return "^NSEBANK"
    if symbol == "SENSEX": return "^BSESN"
    if symbol == "FINNIFTY": return "^CNXFIN"
    if "USDT" in symbol or "BTC" in symbol: return symbol + "-USD"
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"): return symbol + ".NS"
    return symbol

@app.route('/')
def home():
    return "QuantumTrader Live Server is Running!"

# লাইভ প্রাইস আনার রুট
@app.route('/api/price/<symbol>')
def get_live_price(symbol):
    try:
        ticker_sym = get_yf_symbol(symbol)
        ticker = yf.Ticker(ticker_sym)
        try:
            price = ticker.fast_info['last_price']
        except:
            data = ticker.history(period="1d")
            price = data['Close'].iloc[-1]
            
        return jsonify({"status": "success", "symbol": symbol, "price": round(price, 2)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# চার্ট তৈরি করার জন্য হিস্টোরিক্যাল ডেটা আনার রুট (নতুন)
@app.route('/api/history/<symbol>')
def get_history(symbol):
    try:
        ticker_sym = get_yf_symbol(symbol)
        ticker = yf.Ticker(ticker_sym)
        
        # চার্টের জন্য গত ৫ দিনের ৫-মিনিটের ক্যান্ডেলস্টিক ডেটা
        df = ticker.history(period="5d", interval="5m")
        
        data = []
        for index, row in df.iterrows():
            # Lightweight charts-এর জন্য UNIX Timestamp দরকার
            timestamp = int(index.timestamp())
            
            data.append({
                "time": timestamp,
                "open": round(row['Open'], 2),
                "high": round(row['High'], 2),
                "low": round(row['Low'], 2),
                "close": round(row['Close'], 2)
            })
            
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

if __name__ == '__main__':
    print("=======================================")
    print("QuantumTrader LIVE Server Running!")
    print("=======================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
