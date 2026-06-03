from flask import Flask, jsonify
from flask_cors import CORS
from fyers_apiv3 import fyersModel

app = Flask(__name__)
# CORS এনাবল করা হলো যাতে আপনার ফ্রন্টএন্ড থেকে API কল ব্লক না হয়
CORS(app) 

# ==========================================
# FYERS API CREDENTIALS
# ==========================================
# আপনার Fyers Client ID
CLIENT_ID = "A735DXMG83-100"  

# আপনার আজকের জেনারেট করা Access Token
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcUg3bTNrSzNyNHg0VnBsOUI3OHY1ckpYRDdfNURrR3RkbFhCeDg0TUgyb3EyV25sMmRXTjNtVktYeVhkTXNacm5QdHR5R0psLWdFWXQyaHVyclN5YVV5VnprR1BfR2JEanhFcVV4SHo2UmNHZ3Uxcz0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIzYzRhZjA1OGFkNTVmNWJkOWMzNTZkN2U0M2I5NTdkYmRmMjI2ODhlOWI4MGE4YzA0ZTIwYTI4NCIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWE0yNTMyNSIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzgwNTMzMDAwLCJpYXQiOjE3ODA0NjQwNTUsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc4MDQ2NDA1NSwic3ViIjoiYWNjZXNzX3Rva2VuIn0.E7PZqEnxGAo096rIM8gkbhWMgZtpFstBxtNRalVVCBM"

# Fyers Model ইনিশিয়ালাইজ করা
fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=ACCESS_TOKEN, log_path="")

# ==========================================
# SYMBOL FORMATTING
# ==========================================
def format_fyers_symbol(frontend_symbol):
    """
    ফ্রন্টএন্ডের সিম্বলকে Fyers-এর ফরম্যাটে (যেমন: NSE:RELIANCE-EQ) কনভার্ট করার ফাংশন
    """
    sym = frontend_symbol.replace('.NS', '').upper()
    
    if sym == 'NIFTY': 
        return 'NSE:NIFTY50-INDEX'
    elif sym == 'BANKNIFTY': 
        return 'NSE:NIFTYBANK-INDEX'
    elif sym == 'FINNIFTY':
        return 'NSE:FINNIFTY-INDEX'
    elif sym == 'SENSEX':
        return 'BSE:SENSEX-INDEX'
    elif 'USDT' in sym or 'BTC' in sym:
        return None  # ক্রিপ্টো স্কিপ করা হলো
    else:
        return f"NSE:{sym}-EQ"

# ==========================================
# API ENDPOINT
# ==========================================
@app.route('/api/price/<symbol>', methods=['GET'])
def get_live_price(symbol):
    try:
        fyers_sym = format_fyers_symbol(symbol)
        if not fyers_sym:
            return jsonify({'status': 'error', 'message': 'Symbol not supported'})

        # Fyers API থেকে লাইভ ডেটা ফেচ করা
        data = {"symbols": fyers_sym}
        response = fyers.quotes(data=data)
        
        # রেসপন্স চেক করে প্রাইস (CMP) রিটার্ন করা
        if response.get('s') == 'ok':
            cmp = response['d'][0]['v']['lp'] 
            return jsonify({
                'status': 'success', 
                'price': cmp, 
                'symbol': symbol
            })
        else:
            return jsonify({'status': 'error', 'message': response.get('message', 'No data found')})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ==========================================
# RUN SERVER
# ==========================================
if __name__ == '__main__':
    # সার্ভার রান করা
    app.run(host='0.0.0.0', port=5000)