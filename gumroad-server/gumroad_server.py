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
from datetime import datetime

# === Load environment variables (for GitHub token etc.) ===
load_dotenv()

app = Flask(__name__)

# --- Email Settings (Hardcoded for now) ---
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 465
FROM_EMAIL    = "lovinquesaba17@gmail.com"
FROM_PASSWORD = "vwljbmhtwdvqlrrj"  # ⚠️ Hardcoded Gmail App Password

# --- GitHub Settings ---
GITHUB_CLONE_DIR = "/tmp/pdf_table_extractor_clone"
GIT_USERNAME     = "quesabalovin"
GIT_EMAIL        = "lovin.quesaba@gmail.com"
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN")  # Must be set via environment
GITHUB_BRANCH    = "main"
REPO_NAME        = "pdf_table_extractor"

# --- Local Backup ---
CREDENTIALS_FILE = "credentials.json"

# === Utility Functions ===
def load_json(path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def generate_password(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

# === Email Sending ===
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
            f"Please log in at https://pdf-table-extractor-o8u6.onrender.com\n\n"
            f"Enjoy!"
        )
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = to_email

        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!", flush=True)
    except Exception as e:
        print("❌ Failed to send email:", e, flush=True)

# === GitHub Sync ===
def update_credentials_in_repo(new_email, new_password):
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not found in environment.", flush=True)
        return

    auth_url = f"https://{GIT_USERNAME}:{GITHUB_TOKEN}@github.com/{GIT_USERNAME}/{REPO_NAME}.git"

    try:
        if os.path.exists(GITHUB_CLONE_DIR):
            shutil.rmtree(GITHUB_CLONE_DIR)

        subprocess.check_call(["git", "clone", auth_url, GITHUB_CLONE_DIR])

        creds_dir = os.path.join(GITHUB_CLONE_DIR, "pdf_table_extractor")
        os.makedirs(creds_dir, exist_ok=True)
        creds_path = os.path.join(creds_dir, "credentials.json")

        creds = load_json(creds_path)
        creds[new_email] = {"password": new_password, "credits": 100}
        save_json(creds_path, creds)

        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.email", GIT_EMAIL])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.name", GIT_USERNAME])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "add", "pdf_table_extractor/credentials.json"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "commit", "-m", f"Add new user {new_email}"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "push", "origin", GITHUB_BRANCH])

        print("✅ GitHub credentials updated.", flush=True)
    except Exception as e:
        print("❌ GitHub sync failed:", e, flush=True)

# === Gumroad Webhook Handler ===
@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    form = request.form
    email = form.get("email")
    pid   = form.get("product_id")
    if not email or not pid:
        return "Missing email or product_id", 400

    pwd = generate_password()
    creds = load_json(CREDENTIALS_FILE)
    creds[email] = {"password": pwd, "credits": 100}
    save_json(CREDENTIALS_FILE, creds)

    send_email(email, email, pwd)
    update_credentials_in_repo(email, pwd)

    return "✅ Credentials created and email sent!", 200

# === Health Check for cron-job.org ===
@app.route("/health", methods=["GET"])
def health_check():
    now = datetime.utcnow().isoformat()
    print(f"🟢 Cron-job.org ping at {now} UTC", flush=True)
    return "✅ Server is awake!", 200

# === Home Route ===
@app.route("/", methods=["GET"])
def home():
    return "✅ Gumroad server is live. Use POST /gumroad_ping to register users.", 200

# === Start Server ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
