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
from dotenv import load_dotenv

# === Load environment variables (.env or Render) ===
load_dotenv()

app = Flask(__name__)

# --- Email Settings (Hardcoded password here) ---
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 465
FROM_EMAIL    = "lovinquesaba@gmail.com"
FROM_PASSWORD = "uxwszckyahsyklpv"  # ⚠️ Hardcoded Gmail App Password

# --- GitHub Settings (Token via Render ENV) ---
GITHUB_CLONE_DIR = "/tmp/pdf_table_extractor_clone"
GIT_USERNAME     = "quesabalovin"
GIT_EMAIL        = "lovin.quesaba@gmail.com"
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")  # Secure via Render
GITHUB_BRANCH    = "main"
REPO_NAME        = "pdf_table_extractor"

# --- Local Credentials File ---
CREDENTIALS_FILE = "credentials.json"

# === Utils ===
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def generate_password(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

# === Email ===
def send_email(to_email, username, password):
    try:
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ctx)
        server.login(FROM_EMAIL, FROM_PASSWORD)

        subject = "Your Login Credentials"
        body = (
            f"Hello!\n\n"
            f"Here are your login credentials:\n\n"
            f"Email: {username}\n"
            f"Password: {password}\n\n"
            f"Please log in and enjoy!"
        )
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = to_email

        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!")
    except Exception as e:
        print("❌ Failed to send email:", e)

# === GitHub Sync ===
def update_credentials_in_repo(new_email, new_password):
    if not GITHUB_TOKEN:
        print("❌ ERROR: GITHUB_TOKEN is not set or failed to load from environment.")
        return

    print("🔐 DEBUG: GITHUB_TOKEN loaded:", GITHUB_TOKEN[:5], "...")

    auth_url = f"https://{GIT_USERNAME}:{GITHUB_TOKEN}@github.com/{GIT_USERNAME}/{REPO_NAME}.git"

    try:
        if os.path.exists(GITHUB_CLONE_DIR):
            shutil.rmtree(GITHUB_CLONE_DIR)

        subprocess.check_call(["git", "clone", auth_url, GITHUB_CLONE_DIR])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "remote", "set-url", "origin", auth_url])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "remote", "set-url", "--push", "origin", auth_url])

        creds_path = os.path.join(GITHUB_CLONE_DIR, "credentials.json")
        creds = load_json(creds_path)
        creds[new_email] = {"password": new_password, "credits": 10}
        save_json(creds_path, creds)

        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.email", GIT_EMAIL])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.name", GIT_USERNAME])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "add", "credentials.json"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "commit", "-m", f"Add new user {new_email}"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "push", "origin", GITHUB_BRANCH])

        print("✅ Successfully updated and pushed credentials.json to GitHub!")

    except Exception as e:
        print("❌ GitHub sync error:", e)

# === Gumroad Ping ===
@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    form = request.form
    email = form.get("email")
    pid   = form.get("product_id")
    if not email or not pid:
        return "Missing email or product_id", 400

    pwd = generate_password()
    creds = load_json(CREDENTIALS_FILE)
    creds[email] = {"password": pwd, "credits": 10}
    save_json(CREDENTIALS_FILE, creds)

    send_email(email, email, pwd)
    update_credentials_in_repo(email, pwd)

    return "✅ Credentials created and email sent!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
