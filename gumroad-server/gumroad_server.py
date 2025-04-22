from flask import Flask, request
import json
import os
import random
import string
import smtplib
import ssl
from email.mime.text import MIMEText
import subprocess
import shutil

app = Flask(__name__)

# --- Email Settings ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
FROM_EMAIL = "lovinquesaba@gmail.com"
FROM_PASSWORD = "uxwszckyahsyklpv"

# --- GitHub Settings (Fine-Grained Token Format) ---
GITHUB_REPO_URL = "https://github.com/quesabalovin/pdf_table_extractor.git"
GITHUB_CLONE_DIR = "/tmp/pdf_table_extractor_clone"
GITHUB_BRANCH = "main"
GIT_USERNAME = "quesabalovin"
GIT_EMAIL = "lovin.quesaba@gmail.com"
GITHUB_TOKEN = "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"  # <-- Make sure this token has repo access to pdf_table_extractor

# --- Local Credentials File ---
CREDENTIALS_FILE = "credentials.json"

# === File Utilities ===
def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# === Helper to Generate Random Password ===
def generate_password(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# === Email Sending ===
def send_email(to_email, username, password):
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
        server.login(FROM_EMAIL, FROM_PASSWORD)

        subject = "Your Login Credentials"
        body = f"Hello!\n\nHere are your login credentials:\n\nEmail: {username}\nPassword: {password}\n\nPlease log in and enjoy!"

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email

        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# === GitHub Auto-Update Credentials.json ===
def update_credentials_in_repo(new_email, new_password):
    try:
        if os.path.exists(GITHUB_CLONE_DIR):
            shutil.rmtree(GITHUB_CLONE_DIR)

        repo_url_with_auth = f"https://{GIT_USERNAME}:{GITHUB_TOKEN}@github.com/{GIT_USERNAME}/pdf_table_extractor.git"

        subprocess.check_call([
            "git", "clone", repo_url_with_auth, GITHUB_CLONE_DIR
        ])

        credentials_path = os.path.join(GITHUB_CLONE_DIR, "credentials.json")

        if os.path.exists(credentials_path):
            with open(credentials_path, "r") as f:
                credentials_data = json.load(f)
        else:
            credentials_data = {}

        credentials_data[new_email] = {
            "password": new_password,
            "credits": 10
        }

        with open(credentials_path, "w") as f:
            json.dump(credentials_data, f, indent=2)

        subprocess.check_call(["git", "config", "--global", "user.email", GIT_EMAIL])
        subprocess.check_call(["git", "config", "--global", "user.name", GIT_USERNAME])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "add", "credentials.json"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "commit", "-m", f"Add new user {new_email}"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "push", "origin", GITHUB_BRANCH])

        print("✅ Successfully updated credentials.json and pushed to GitHub!")

    except Exception as e:
        print(f"❌ Failed to update credentials.json in GitHub: {e}")

@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    data = request.form
    email = data.get("email")
    product_id = data.get("product_id")

    if not email or not product_id:
        return "Missing required fields", 400

    password = generate_password()
    credentials = load_json(CREDENTIALS_FILE)
    credentials[email] = {
        "password": password,
        "credits": 10
    }
    save_json(CREDENTIALS_FILE, credentials)
    send_email(email, email, password)
    update_credentials_in_repo(email, password)

    return "✅ Credentials created and email sent!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
