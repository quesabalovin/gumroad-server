# gumroad_server.py

from flask import Flask, request
import smtplib
from email.mime.text import MIMEText
import json
import os
import random
import string

# --- Load Users ---
USERS_FILE = "credentials.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

USERS = load_users()

# --- Email Settings ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
FROM_EMAIL = "lovinquesaba@gmail.com"  # <-- CHANGE THIS
FROM_PASSWORD = "uxwszckyahsyklpv"  # <-- CHANGE THIS

# --- Flask App ---
app = Flask(__name__)

def send_login_email(to_email, username, password):
    subject = "Your Login Credentials for PDF Extractor"
    body = f"""Hello,

Thank you for purchasing!

Here are your login details:

🔑 Username: {username}
🔒 Password: {password}

You can now log in and use the service. Enjoy!

Regards,
Parq Team
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(FROM_EMAIL, FROM_PASSWORD)
        server.send_message(msg)

def generate_random_password(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    data = request.form

    buyer_email = data.get('email')
    product_id = data.get('product_id')

    if not buyer_email:
        return "No buyer email found", 400

    USERS = load_users()  # Reload latest users

    if buyer_email not in USERS:
        USERS[buyer_email] = {
            "password": generate_random_password(),
            "credits": 10
        }
        save_users(USERS)

    username = buyer_email
    password = USERS[buyer_email]["password"]

    try:
        send_login_email(buyer_email, username, password)
        return "Email sent successfully!", 200
    except Exception as e:
        return f"Failed to send email: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
