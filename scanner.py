import requests
import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_test_msg():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    message = "✅ Salom! Bot muvaffaqiyatli ulandi va xabar yuboryapti!"
    payload = {'chat_id': CHAT_ID, 'text': message}
    
    print(f"Xabar yuborilmoqda... Token: {TELEGRAM_TOKEN[:5]}***, ID: {CHAT_ID}")
    
    try:
        r = requests.post(url, data=payload)
        if r.status_code == 200:
            print("Xabar muvaffaqiyatli ketdi!")
        else:
            print(f"Xatolik yuz berdi: {r.text}")
    except Exception as e:
        print(f"Ulanishda xato: {e}")

if __name__ == "__main__":
    send_test_msg()
