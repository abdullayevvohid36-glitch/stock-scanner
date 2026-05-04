import smtplib
from email.mime.text import MIMEText
import os

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

def test_email():
    msg = MIMEText("Bu GitHub Actions orqali yuborilgan TEST xabaridir.")
    msg['Subject'] = "🚀 Skaner Test"
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    try:
        print(f"Ulanishga urinish: {EMAIL_USER} orqali...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("✅ MUVAFFAQIYATLI: Pochtangizni tekshiring!")
    except Exception as e:
        print(f"❌ XATOLIK: {e}")

if __name__ == "__main__":
    test_email()
