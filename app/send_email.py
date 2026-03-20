import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def format_as_html(text):
    """Convert plain text digest into clean HTML email format."""

    lines = text.split("\n")
    html = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Section headers (ALL CAPS)
        if stripped.isupper() and len(stripped) > 0:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h2 style='margin-top:20px; margin-bottom:10px;'>{stripped}</h2>")

        # Bullet points
        elif stripped.startswith("•"):
            if not in_list:
                html.append("<ul style='margin-top:0; margin-bottom:10px;'>")
                in_list = True
            html.append(f"<li style='margin-bottom:8px;'>{stripped[1:].strip()}</li>")

        # Blank lines
        elif stripped == "":
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append("<br>")

        # Regular text
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<p style='margin:0 0 10px 0;'>{stripped}</p>")

    if in_list:
        html.append("</ul>")

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; font-size:14px; line-height:1.5;">
            {''.join(html)}
        </body>
    </html>
    """


def send_digest(digest_text):
    """Send the provided digest via email."""

    # Email settings
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

    # Convert content
    html_body = format_as_html(digest_text)

    # Attach both plain + HTML
    msg.attach(MIMEText(digest_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Send email
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

    print("Email sent successfully.")