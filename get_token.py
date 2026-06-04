from fyers_apiv3 import fyersModel
import firebase_admin
from firebase_admin import credentials, db
import requests

# 1. Firebase Setup
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://quantum-tracker-6fe30-default-rtdb.firebaseio.com/'
        })
except Exception as e:
    print("Firebase Error: Make sure firebase_key.json is in this folder!")
    exit()

client_id = "A735DXMG83-100" 
secret_key = "8V84BBQP11" 
redirect_uri = "https://127.0.0.1" 

session = fyersModel.SessionModel(
    client_id=client_id, secret_key=secret_key, redirect_uri=redirect_uri,
    response_type="code", grant_type="authorization_code"
)

generateTokenUrl = session.generate_authcode()
print("\n--- Click the link below and login ---")
print(generateTokenUrl)

auth_code = input("\nURL থেকে auth_code কপি করে এখানে পেস্ট করুন: ")
session.set_token(auth_code)
response = session.generate_token()

if "access_token" in response:
    new_token = response["access_token"]
    print("\n✅ Token Generated Successfully!")
    
    # 2. ফায়ারবেসে সেভ করা হচ্ছে
    db.reference('admin_settings/fyers_token').set(new_token)
    print("✅ Saved to Firebase Database!")
    
    # 3. Render সার্ভারকে আপডেট করার নির্দেশ
    try:
        res = requests.get("https://quantum-trader-api.onrender.com/api/reload_token")
        if res.status_code == 200:
            print("✅ Render Server automatically updated with new token! You are LIVE.")
        else:
            print("⚠️ Render Server update failed.")
    except:
        print("⚠️ Could not reach Render Server.")
else:
    print("❌ Error:", response)