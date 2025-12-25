import smtplib
import ssl
import logging
import sys
import os
import sqlite3  # Import sqlite3 library
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime

# --- Configuration for Logging (Logs to both file and console) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_report.log"),  # Logs to the file
        logging.StreamHandler(sys.stdout)  # Logs to the console
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration for NEW Email Service (Load from environment variables) ---
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# Sender and Recipient addresses (must be verified in Mailgun/Sendgrid if sending live)
SENDER_EMAIL = "your_verified_sender@example.com"
RECIPIENT_EMAIL = "recipient_email_address@example.com"

# Define database path relative to the script location
DB_PATH = 'stockpilot.db'
HTML_FILE_PATH = 'stock_report.html'  # Assuming this is used later for the report itself


def generate_stock_report():
    """Generates the report body with database data and calls the email function."""

    records = []  # Initialize records list

    # --- Secure Database Connection Handling using 'with' statement ---
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Execute a query to get data where current stock is below reorder Level
            cursor.execute("SELECT id, item_name, reorder_level, current_stock, alert_date FROM reorder_alerts")
            records = cursor.fetchall()
        # Connection is automatically closed here
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return  # Exit function if DB error occurs

    print("Database connection closed.")  # This print statement is now accurate

    # --- Start building the HTML content as a string (placeholder) ---
    html_content = "<h1>Stock Reorder Alerts</h1><ul>"
    for record in records:
        html_content += f"<li>Item: {record[1]} | Current Stock: {record[3]} | Reorder Level: {record[2]}</li>"
    html_content += "</ul>"

    # After generating the report, send the email
    send_email_report(html_content)


def send_email_report(html_body):
    """Sends the stock report email and logs the outcome."""
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"StockPilot Daily Reorder Alert ({datetime.date.today()})"

    msg.attach(MIMEText(html_body, 'html'))

    context = ssl.create_default_context()

    try:
        server = smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT)
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, text)
        server.quit()

        logger.info(f"Email report successfully sent via new service to {RECIPIENT_EMAIL}")

    except Exception as e:
        logger.error(f"Failed to send email via new service: {e}")


# Entry point of the script
if __name__ == '__main__':
    generate_stock_report()
