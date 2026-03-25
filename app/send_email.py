import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def format_as_html(text):
    """Convert plain text digest into clean HTML email format."""

    lines = text.split("\n")
    html = []
    list_mode = None

    def close_list():
        nonlocal list_mode
        if list_mode == "ul":
            html.append("</ul>")
        elif list_mode == "ol":
            html.append("</ol>")
        list_mode = None

    for line in lines:
        stripped = line.strip()

        # Section headers (ALL CAPS)
        if stripped.isupper() and len(stripped) > 0:
            close_list()
            html.append(f"<h2 style='margin-top:20px; margin-bottom:10px;'>{stripped}</h2>")

        # Bullet points
        elif stripped.startswith("•"):
            if list_mode != "ul":
                close_list()
                html.append("<ul style='margin-top:0; margin-bottom:10px;'>")
                list_mode = "ul"
            html.append(f"<li style='margin-bottom:8px;'>{stripped[1:].strip()}</li>")

        # Numbered items
        elif re.match(r"^\d+\.\s+", stripped):
            if list_mode != "ol":
                close_list()
                html.append("<ol style='margin-top:0; margin-bottom:10px; padding-left:20px;'>")
                list_mode = "ol"
            item_text = re.sub(r"^\d+\.\s+", "", stripped)
            html.append(f"<li style='margin-bottom:8px;'>{item_text}</li>")

        # Blank lines
        elif stripped == "":
            close_list()
            html.append("<br>")

        # Regular text
        else:
            close_list()
            html.append(f"<p style='margin:0 0 10px 0;'>{stripped}</p>")

    close_list()

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; font-size:14px; line-height:1.5;">
            {''.join(html)}
        </body>
    </html>
    """


def send_report(subject, body_text):
    """Send the provided report via email using the shared HTML formatter."""

    smtp_server = "smtp.gmail.com"
    smtp_port = 465
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO")
    app_password = os.environ.get("EMAIL_PASSWORD")

    if not sender_email or not app_password or not receiver_email:
        raise RuntimeError("EMAIL_USER, EMAIL_PASSWORD, and EMAIL_TO must be set")

    subject = "Daily Riffs from the Gen AI Songbook"

    # Create message container
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    html_body = format_as_html(body_text)

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        print("Connecting to SMTP server...")
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            print("Logging in...")
            server.login(sender_email, app_password)
            print("Sending message...")
            server.sendmail(sender_email, receiver_email, msg.as_string())

        print("Email sent successfully.")

    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        raise


def send_digest(digest_text):
    """Send the provided daily digest via email."""

    send_report("Daily Riffs from the Gen AI Songbook", digest_text)
