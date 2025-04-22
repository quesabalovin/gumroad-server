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
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 465
FROM_EMAIL    = "lovinquesaba@gmail.com"         # <-- your Gmail
FROM_PASSWORD = "uxwszckyahsyklpv"                # <-- your Gmail App Password

# --- GitHub Settings (Fine-Grained Token) ---
GITHUB_REPO_URL  = "https://github.com/quesabalovin/pdf_table_extractor.git"
GITHUB_CLONE_DIR = "/tmp/pdf_table_extractor_clone"
GITHUB_BRANCH    = "main"
GIT_USERNAME     = "quesabalovin"
GIT_EMAIL        = "lovin.quesaba@gmail.com"
GITHUB_TOKEN     = "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"  # <-- your fine-grained token

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
        print(f"❌ Failed to send email: {e}")

# === GitHub Auto-Update Credentials.json ===
def update_credentials_in_repo(new_email, new_password):
    try:
        # 1. Clean out any old clone
        if os.path.exists(GITHUB_CLONE_DIR):
            shutil.rmtree(GITHUB_CLONE_DIR)

        # 2. Clone using token auth
        auth_url = (
            f"https://{GIT_USERNAME}:{GITHUB_TOKEN}"
            f"@github.com/{GIT_USERNAME}/pdf_table_extractor.git"
        )
        subprocess.check_call(["git", "clone", auth_url, GITHUB_CLONE_DIR])

        # 3. Ensure origin push also uses token auth
        subprocess.check_call([
            "git", "-C", GITHUB_CLONE_DIR,
            "remote", "set-url", "origin", auth_url
        ])

        # 4. Load & merge credentials
        cred_path = os.path.join(GITHUB_CLONE_DIR, "credentials.json")
        creds = load_json(cred_path)
        creds[new_email] = {"password": new_password, "credits": 10}
        save_json(cred_path, creds)

        # 5. Commit & push
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.email", GIT_EMAIL])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "config", "user.name",  GIT_USERNAME])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "add",    "credentials.json"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "commit", "-m",     f"Add new user {new_email}"])
        subprocess.check_call(["git", "-C", GITHUB_CLONE_DIR, "push",   "origin", GITHUB_BRANCH])

        print("✅ Successfully updated credentials.json and pushed to GitHub!")
    except Exception as e:
        print(f"❌ Failed to update credentials.json in GitHub: {e}")

# === Gumroad Ping Handler ===
@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    data       = request.form
    email      = data.get("email")
    product_id = data.get("product_id")

    if not email or not product_id:
        return "Missing required fields", 400

    # generate and save locally
    password    = generate_password()
    credentials = load_json(CREDENTIALS_FILE)
    credentials[email] = {"password": password, "credits": 10}
    save_json(CREDENTIALS_FILE, credentials)

    # email the buyer
    send_email(email, email, password)

    # sync into your Streamlit repo on GitHub
    update_credentials_in_repo(email, password)

    return "✅ Credentials created and email sent!", 200

# === Run the Flask app ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
