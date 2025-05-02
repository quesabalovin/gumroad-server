# gumroad_server.py
import os
import random
import string
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime, timezone
import logging

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from passlib.context import CryptContext
from dotenv import load_dotenv

# === Load environment variables ===
# Loads variables from .env file for local development
# On Render, variables are set in the environment tab
load_dotenv()

# === Setup Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'
)

# === Flask App Initialization ===
app = Flask(__name__)

# === Configuration ===
# Secret key for session security (even if sessions aren't heavily used here)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
if not app.config['SECRET_KEY']:
    logging.warning("FLASK_SECRET_KEY environment variable not set. Using default (unsafe for production).")
    app.config['SECRET_KEY'] = 'default-dev-secret-key-change-me'

# Database connection string from Render environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if not app.config['SQLALCHEMY_DATABASE_URI']:
    logging.critical("FATAL ERROR: DATABASE_URL environment variable not set. Application cannot connect to the database.")
    # Optional: Exit or raise an error if DB connection is absolutely required at startup
    # raise RuntimeError("DATABASE_URL environment variable not set.")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# === Email Settings (Read from environment variables) ===
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465)) # Use int() for port
FROM_EMAIL = os.environ.get("FROM_EMAIL")
FROM_PASSWORD = os.environ.get("FROM_PASSWORD") # Gmail App Password or equivalent

# === Database and Migrations Setup ===
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialize Flask-Migrate

# === Password Hashing Context ===
# Ensure this uses the same scheme (bcrypt) as your Streamlit app verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# === Database Model ===
# This User model definition MUST EXACTLY match the one in your Streamlit app (app.py)
# Any discrepancy will cause errors during data reading/writing or migration.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Ensure length is sufficient, index for faster lookups by email
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    # Store the hashed password, length depends on hashing algorithm (bcrypt needs ~60 chars, 128 is safe)
    password_hash = db.Column(db.String(128), nullable=False)
    # Credits assigned on purchase
    credits = db.Column(db.Integer, nullable=False, default=100)
    # Use timezone aware datetime for creation timestamp
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # Optional: Track last login time (updated by Streamlit app ideally)
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hashes the provided password and stores it in password_hash."""
        self.password_hash = pwd_context.hash(password)

    # check_password method can be defined here for consistency but isn't used by this server
    def check_password(self, password):
        """Verifies a password against the stored hash."""
        try:
            return pwd_context.verify(password, self.password_hash)
        except (ValueError, TypeError): # Catch potential errors with invalid hashes
             logging.error(f"Error verifying password for {self.email} - possible hash issue.")
             return False

    def __repr__(self):
        """String representation for debugging."""
        return f'<User {self.email}>'

# === Utility Functions ===
def generate_password(length=12):
    """Generates a secure random password."""
    # Combine letters, digits, and common symbols
    characters = string.ascii_letters + string.digits + '!@#$%^&*'
    # Ensure the generated password meets complexity requirements if any
    password = "".join(random.choices(characters, k=length))
    # Optional: Add checks to ensure password contains different character types
    return password

# === Email Sending Function ===
def send_credentials_email(to_email, generated_password):
    """Sends the generated credentials via email."""
    if not FROM_EMAIL or not FROM_PASSWORD:
        logging.error("Email credentials (FROM_EMAIL/PASSWORD) missing in environment. Cannot send email.")
        return False

    # Ensure required email parameters are strings
    if not isinstance(to_email, str) or not isinstance(FROM_EMAIL, str):
         logging.error("Invalid email address type provided.")
         return False

    try:
        ctx = ssl.create_default_context()
        # Use a timeout for robustness
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ctx, timeout=20) as server:
            server.ehlo() # Greet the server
            server.login(FROM_EMAIL, FROM_PASSWORD)

            subject = "Your PDF Table Extractor Pro Access"
            # --- !!! UPDATE THE URL BELOW !!! ---
            streamlit_app_url = "https://YOUR-STREAMLIT-APP-URL.onrender.com" # Replace with actual URL
            # --- -------------------------- ---
            body = (
                f"Hello,\n\n"
                f"Thank you for purchasing PDF Table Extractor Pro!\n\n"
                f"Please use the following credentials to log in:\n\n"
                f"Email: {to_email}\n"
                f"Generated Password: {generated_password}\n\n"
                f"Access the tool here: {streamlit_app_url}\n\n"
                f"We recommend storing this password securely.\n\n"
                f"If you encounter any issues, please contact support.\n\n" # Add support contact if available
                f"Best regards,\n"
                f"The PDF Extractor Team" # Or your brand/name
            )
            msg = MIMEText(body, 'plain', 'utf-8') # Ensure UTF-8 encoding
            msg["Subject"] = subject
            msg["From"]    = f"PDF Extractor Pro <{FROM_EMAIL}>" # More professional From display
            msg["To"]      = to_email

            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        logging.info(f"Credentials email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
         logging.error(f"SMTP Authentication failed for {FROM_EMAIL}. Verify email/App Password.")
         return False
    except smtplib.SMTPException as smtp_err:
         logging.error(f"SMTP error sending email to {to_email}: {smtp_err}", exc_info=True)
         return False
    except Exception as e:
        # Catch any other unexpected errors during email sending
        logging.error(f"General failure sending email to {to_email}: {e}", exc_info=True)
        return False

# === Database User Creation/Update Function ===
def create_user_in_db(email, password, initial_credits=100):
    """Creates a new user or updates password/credits if user exists."""
    if not email or not password:
        logging.error("Attempted to create user with missing email or password.")
        return False

    # Use Flask application context to ensure SQLAlchemy session works correctly
    with app.app_context():
        try:
            # Check if user exists using a case-insensitive query if appropriate, otherwise case-sensitive
            # For case-insensitive: existing_user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            existing_user = User.query.filter_by(email=email).first()

            if existing_user:
                logging.warning(f"User {email} already exists. Updating password and setting credits to {initial_credits}.")
                # Policy decision: On re-purchase, update password and reset/set credits.
                existing_user.set_password(password) # Update password hash
                existing_user.credits = initial_credits   # Set credits
                user_to_commit = existing_user
            else:
                logging.info(f"Creating new user record for: {email}")
                new_user = User(email=email, credits=initial_credits)
                new_user.set_password(password) # Hash the new password
                user_to_commit = new_user
                db.session.add(user_to_commit) # Add new user to session

            # Attempt to commit the changes (add or update)
            db.session.commit()
            logging.info(f"Successfully committed user data for {email}")
            return True
        except Exception as e:
            db.session.rollback() # IMPORTANT: Rollback database changes on any error during commit
            logging.error(f"Database commit error for user {email}: {e}", exc_info=True)
            return False # Indicate failure

# === Gumroad Webhook Handler ===
@app.route("/gumroad_ping", methods=["POST"])
def gumroad_ping():
    """Handles incoming webhook pings from Gumroad upon successful sale."""
    # Optional: Implement webhook signature verification if Gumroad provides it for security
    logging.info("Received POST request on /gumroad_ping")
    form_data = request.form

    email = form_data.get("email")
    product_id = form_data.get("product_id") # Useful for logging or validation

    # Validate incoming data
    if not email:
        logging.warning("Webhook received without 'email' parameter.")
        return jsonify({"status": "error", "message": "Missing email parameter"}), 400

    # Optional: Validate Product ID against environment variable
    expected_product_id = os.environ.get("GUMROAD_PRODUCT_ID")
    if expected_product_id and product_id != expected_product_id:
         logging.warning(f"Webhook ignored for {email}. Product ID mismatch: got '{product_id}', expected '{expected_product_id}'.")
         return jsonify({"status": "ignored", "message": "Product ID mismatch"}), 400 # Or 200 if you want Gumroad to stop retrying

    logging.info(f"Processing Gumroad sale for email: {email}, product: {product_id}")

    # 1. Generate a secure password
    generated_password = generate_password()
    logging.info(f"Generated password for {email}") # Don't log the actual password

    # 2. Store/Update User in Database
    # Assuming 100 credits are granted per successful purchase webhook
    initial_credits = 100
    db_success = create_user_in_db(email, generated_password, initial_credits)

    if not db_success:
        logging.error(f"CRITICAL: Failed to store user {email} in database after successful payment notification.")
        # Notify admin maybe? Return error to Gumroad.
        return jsonify({"status": "error", "message": "Internal server error processing user data"}), 500

    # 3. Send Credentials Email
    email_success = send_credentials_email(email, generated_password)

    if not email_success:
        logging.error(f"Database entry created/updated for {email}, but failed to send credentials email.")
        # The user exists, so maybe return success to Gumroad to prevent retries, but log the issue.
        return jsonify({"status": "partial_success", "message": "User processed, but notification email failed."}), 200

    # If everything succeeded
    logging.info(f"Successfully processed sale and sent credentials for {email}")
    return jsonify({"status": "success", "message": "User created/updated and email sent successfully!"}), 200

# === Health Check Endpoint ===
@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check. Optionally add DB check."""
    db_ok = False
    try:
        # Try a simple query to check DB connection
        with app.app_context():
            db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception as e:
        logging.error(f"Health check DB connection error: {e}")

    if db_ok:
        return jsonify({"status": "OK", "database_connection": "OK"}), 200
    else:
        # Return 503 Service Unavailable if DB check fails
        return jsonify({"status": "Error", "database_connection": "Failed"}), 503

# === Simple Home Route ===
@app.route("/", methods=["GET"])
def home():
    """Indicates the server is running."""
    return jsonify({"message": "Gumroad User Provisioning Server is active."}), 200

# === Flask Application Entry Point ===
if __name__ == "__main__":
    # Port configuration for Render (uses PORT env var) or local default
    port = int(os.environ.get("PORT", 5001))
    # Debug mode controlled by FLASK_DEBUG env var (defaults to False)
    is_debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    # Run the Flask development server (for production, Render uses a proper WSGI server like Gunicorn)
    app.run(host="0.0.0.0", port=port, debug=is_debug)
