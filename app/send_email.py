import os
import smtplib

from app.generate_digest import generate_daily_digest


def send_digest():
    """Generate the daily digest and send it via email."""

    digest = generate_daily_digest()

    # Email settings (from environment)
    smtp_server = "smtp.gmail.com"
    smtp_port = 465
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO")
    app_password = os.environ.get("EMAIL_PASSWORD")

    if not sender_email or not app_password:
        raise RuntimeError("EMAIL_USER and EMAIL_PASSWORD environment variables must be set")

    subject = "Daily AI Digest"
    body = digest

    # Construct raw email message
    message = f"Subject: {subject}\nFrom: {sender_email}\nTo: {receiver_email}\n\n{body}"

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, message.encode('utf-8'))

    print("Email sent successfully.")
