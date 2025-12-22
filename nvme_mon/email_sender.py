import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import ssl

# Load environment variables
load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT")) # TLS (Use 465 for SMTP_SSL)
RECIPIENT = os.getenv("RECIPIENT")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SUBJECT = os.getenv("SUBJECT")

def send_email(recipient_email=RECIPIENT, subject=SUBJECT, body=""):

    msg = MIMEText(body, 'plain')
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")