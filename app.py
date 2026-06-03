from flask import Flask, jsonify, request
from flask_cors import CORS
from fyers_apiv3 import fyersModel

app = Flask(__name__)
# CORS এনাবল করা হলো যাতে ফ্রন্টএন্ড থেকে ব্লক না হয়
CORS(app) 

# ==========================================
# FYERS API CREDENTIALS
# ==========================================
CLIENT_ID = "A735DXMG83-100"  
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcUg3bTNrSzNyNHg0VnBsOUI3OHY1ckpYRDdfNURrR3RkbFhCeDg0TUgyb3EyV25sMmRXTjNtVktYeVhkTXNacm5QdHR5R0psLWdFWXQyaHVyclN5YVV5VnprR1BfR2JEanhFcVV4SHo2UmNHZ3Uxcz0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIzYzRhZjA1OGFkNTVmNWJkOWMzNTZkN2U0M2I5NTdkYmRmMjI2ODhlOWI4MGE4YzA0ZTIwYTI4NCIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWE0yNTMyNSIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzgwNTMzMDAwLCJpYXQiOjE3ODA0NjQwNTUsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc4MDQ2NDA1NSwic3ViIjoiYWNjZXNzX3Rva2VuIn0.E7PZqEnxGAo096rIM8gkbhWMgZtpFstBxtNRalVVCBM"

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")

# ==========================================
# SYMBOL FORMATTING
# ==========================================
def format_fyers_symbol(frontend_symbol):
    """
    ফ্রন্টএন্ডের সিম্বলকে Fyers ফরম্যাটে কনভার্ট করার ফাংশন
    """
    sym = frontend_symbol.replace('.NS', '').upper().strip()
    
    if sym == 'NIFTY': 
        return 'NSE:NIFTY50-INDEX'
    elif sym == 'BANKNIFTY': 
        return 'NSE:NIFTYBANK-INDEX'
    elif sym == 'FINNIFTY':
        return 'NSE:FINNIFTY-INDEX'
    elif sym == 'SENSEX':
        return 'BSE:SENSEX-INDEX'
    elif 'USDT' in sym or 'BTC' in sym:
        return None  
    else:
        return f"NSE:{sym}-EQ"

# ==========================================
# NEW BULK API ENDPOINT (একসাথে সব দাম আনার জন্য)
# ==========================================
@app.route('/api/prices', methods=['GET'])
def get_multiple_prices():
    try:
        # ফ্রন্টএন্ড থেকে কমা দিয়ে পাঠানো সিম্বল রিড করবে (যেমন: symbols=ITBEES,VBL,RELIANCE)
        symbols_str = request.args.get('symbols', '')
        if not symbols_str:
            return jsonify({'status': 'error', 'message': 'No symbols provided'})
        
        frontend_symbols = symbols_str.split(',')
        fyers_symbols_list = []
        symbol_mapping = {} # Fyers সিম্বল থেকে ফ্রন্টএন্ড সিম্বল ট্র্যাক রাখার জন্য

        # সব সিম্বল একসাথে ফরম্যাট করা
        for sym in frontend_symbols:
            formatted = format_fyers_symbol(sym)
            if formatted:
                fyers_symbols_list.append(formatted)
                symbol_mapping[formatted] = sym

        if not fyers_symbols_list:
            return jsonify({'status': 'error', 'message': 'No valid symbols found'})

        # Fyers API-তে ১টি মাত্র রিকোয়েস্টে সব সিম্বলের ডেটা পাঠানো হচ্ছে
        fyers_string_format = ",".join(fyers_symbols_list)
        response = fyers.quotes(data={"symbols": fyers_string_format})
        
        if response.get('s') == 'ok':
            prices_dict = {}
            for item in response.get('d', []):
                fyers_sym = item.get('n') # Fyers সিম্বল নাম (যেমন: NSE:VBL-EQ)
                lp = item.get('v', {}).get('lp') # লাইভ লাস্ট প্রাইস (CMP)
                
                if fyers_sym in symbol_mapping:
                    orig_sym = symbol_mapping[fyers_sym]
                    prices_dict[orig_sym] = lp

            return jsonify({
                'status': 'success',
                'prices': prices_dict # এটি একটা অবজেক্ট রিটার্ন করবে: {"ITBEES": 35.40, "VBL": 620.10}
            })
        else:
            return jsonify({'status': 'error', 'message': response.get('message', 'Failed to fetch quotes')})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# পুরোনো সিঙ্গেল এন্ডপয়েন্টও ব্যাকআপ হিসেবে রাখা হলো
@app.route('/api/price/<symbol>', methods=['GET'])
def get_live_price(symbol):
    try:
        fyers_sym = format_fyers_symbol(symbol)
        if not fyers_sym:
            return jsonify({'status': 'error', 'message': 'Symbol not supported'})

        response = fyers.quotes(data={"symbols": fyers_sym})
        if response.get('s') == 'ok':
            cmp = response['d'][0]['v']['lp'] 
            return jsonify({'status': 'success', 'price': cmp, 'symbol': symbol})
        else:
            return jsonify({'status': 'error', 'message': response.get('message', 'No data found')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
