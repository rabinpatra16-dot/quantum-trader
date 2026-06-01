from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
import os  # অনলাইনে চালানোর জন্য এটি যোগ করা হয়েছে

app = Flask(__name__)
CORS(app)

symbol_map = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN"
}

@app.route('/api/price/<symbol>')
def get_price(symbol):
    try:
        original_symbol = symbol.replace('.NS', '').strip().upper()
        
        if original_symbol in symbol_map:
            fetch_symbol = symbol_map[original_symbol]
        else:
            fetch_symbol = original_symbol + '.NS'
            
        print(f"⏳ Fetching price for: {fetch_symbol} ...", end=" ")
        
        ticker = yf.Ticker(fetch_symbol)
        
        try:
            cmp = ticker.fast_info['last_price']
            print(f"✅ Success: ₹{round(cmp, 2)}")
            return jsonify({"symbol": symbol, "price": round(cmp, 2), "status": "success"})
        except:
            pass
            
        data = ticker.history(period="1d")
        if not data.empty:
            cmp = data['Close'].iloc[-1]
            print(f"✅ Success: ₹{round(cmp, 2)}")
            return jsonify({"symbol": symbol, "price": round(cmp, 2), "status": "success"})
        else:
            print("❌ Failed: Data missing on Yahoo Finance!")
            return jsonify({
                "status": "partial", 
                "message": "Yahoo API Issue. Please enter CMP manually.",
                "symbol": symbol
            })
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# অনলাইনে চালানোর জন্য এই নিচের অংশটুকু আপডেট করা হয়েছে
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)