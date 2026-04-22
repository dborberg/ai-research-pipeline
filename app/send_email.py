import os
import re
import smtplib
from html import unescape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.branding import DAILY_TITLE, KNOWN_REPORT_TITLES


def _looks_like_html(text):
    lowered = (text or "").lower()
    return any(tag in lowered for tag in ["<html", "<body", "<h2", "<h3", "<p", "<ul", "<ol", "<li"])


def _is_report_title(text):
    stripped = (text or "").strip()
    return stripped in KNOWN_REPORT_TITLES or stripped.startswith("AI SIGNAL COMMAND")


def _html_to_plain_text(text):
    if not text:
        return ""

    plain = re.sub(r"(?i)<br\s*/?>", "\n", text)
    plain = re.sub(r"(?i)</p>|</div>|</h[1-6]>", "\n\n", plain)
    plain = re.sub(r"(?i)</li>", "\n", plain)
    plain = re.sub(r"(?i)<li[^>]*>", "- ", plain)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = unescape(plain)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def format_as_html(text):
    """Convert plain text digest into clean HTML email format."""

    lines = text.split("\n")
    html = []
    list_mode = None
    current_item_open = False
    title_rendered = False
    date_rendered = False

    def close_item():
        nonlocal current_item_open
        if current_item_open:
            html.append("</li>")
            current_item_open = False

    def close_list():
        nonlocal list_mode
        close_item()
        if list_mode == "ul":
            html.append("</ul>")
        elif list_mode == "ol":
            html.append("</ol>")
        list_mode = None

    for line in lines:
        stripped = line.strip()

        if not title_rendered and stripped and _is_report_title(stripped):
            html.append(f"<h2 style='margin:0 0 4px 0;'>{stripped}</h2>")
            title_rendered = True
            continue

        if title_rendered and not date_rendered and stripped and (
            stripped.startswith("Week of ") or
            stripped.startswith("Week Ending ") or
            stripped.startswith("Month of ") or
            re.match(r"^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$", stripped)
        ):
            html.append(f"<p style='margin:0 0 12px 0;'><strong>{stripped}</strong></p>")
            date_rendered = True
            continue

        # Section headers (ALL CAPS)
        if stripped.isupper() and len(stripped) > 0:
            close_list()
            html.append(f"<h3 style='margin:16px 0 8px 0;'>{stripped}</h3>")

        # Bullet points
        elif stripped.startswith("•"):
            if list_mode != "ul":
                close_list()
                html.append("<ul style='margin:0 0 10px 0; padding-left:18px;'>")
                list_mode = "ul"
            else:
                close_item()
            html.append(f"<li style='margin:0 0 6px 0;'>{stripped[1:].strip()}")
            current_item_open = True

        # Numbered items
        elif re.match(r"^\d+\.\s+", stripped):
            if list_mode != "ol":
                close_list()
                html.append("<ol style='margin:0 0 10px 0; padding-left:20px;'>")
                list_mode = "ol"
            else:
                close_item()
            item_text = re.sub(r"^\d+\.\s+", "", stripped)
            html.append(f"<li style='margin:0 0 6px 0;'>{item_text}")
            current_item_open = True

        # Blank lines
        elif stripped == "":
            if current_item_open:
                html.append("<div style='height:4px;'></div>")
            else:
                close_list()
                html.append("<div style='height:6px;'></div>")

        # Regular text
        else:
            if current_item_open:
                html.append(f"<div style='margin:4px 0 0 0;'>{stripped}</div>")
            else:
                close_list()
                html.append(f"<p style='margin:0 0 8px 0;'>{stripped}</p>")

    close_list()

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; font-size:14px; line-height:1.45; color:#111827;">
            {''.join(html)}
        </body>
    </html>
    """


def send_report(subject, body_text, body_html=None):
    """Send the provided report via email using the shared HTML formatter."""

    smtp_server = "smtp.gmail.com"
    smtp_port = 465
    sender_email = os.environ.get("EMAIL_USER")
    receiver_email = os.environ.get("EMAIL_TO")
    app_password = os.environ.get("EMAIL_PASSWORD")

    if not sender_email or not app_password or not receiver_email:
        raise RuntimeError("EMAIL_USER, EMAIL_PASSWORD, and EMAIL_TO must be set")

    # Create message container
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    if body_html is not None:
        plain_body = (body_text or "").strip()
        html_body = body_html
    elif _looks_like_html(body_text):
        plain_body = _html_to_plain_text(body_text)
        html_body = body_text
    else:
        plain_body = body_text
        html_body = format_as_html(body_text)

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
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

    send_report(DAILY_TITLE, digest_text)
