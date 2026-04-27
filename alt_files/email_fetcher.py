import imaplib
import email
from email.header import decode_header
import os
import sys
from dotenv import load_dotenv
from email.message import EmailMessage
from datetime import datetime, timezone
from email.utils import parseaddr

# Prevent Windows terminal from crashing if an email subject contains emojis
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_APP_PASSWORD")

def is_first_run(): 
    return not os.path.exists(STATE_FILE)

STATE_FILE = "last_processed_uid.txt"

HOTEL_KEYWORDS = [
    "hotel", "booking", "reservation", "stay",
    "tour", "trip", "vacation", "travel",
    "accommodation", "room", "package", "check-in"
]


# -------------------------
# State helpers
# -------------------------
def load_last_uid():
    if not os.path.exists(STATE_FILE):
        return 0
    with open(STATE_FILE, "r") as f:
        return int(f.read().strip())

def save_last_uid(uid):
    with open(STATE_FILE, "w") as f:
        f.write(str(uid))


# -------------------------
# Email helpers
# -------------------------
def decode_subject(msg):
    subject = msg.get("Subject", "")
    decoded, enc = decode_header(subject)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore")
    return decoded


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                # Ensure payload exists before decoding
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode(errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="ignore")
    return body.strip()


def is_hotel_email(subject, body):
    text = f"{subject} {body}".lower()
    return any(k in text for k in HOTEL_KEYWORDS)


# -------------------------
# Main function
# -------------------------
def fetch_next_pending_email():
    mail = imaplib.IMAP4_SSL(EMAIL_HOST)
    mail.login(EMAIL_USER, EMAIL_PASS)

    # READONLY prevents inbox changes
    mail.select("inbox", readonly=True)

    if is_first_run():
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        print(f"......First run detected. Processing emails since {today}")

        status, data = mail.uid(
            "search",
            None,
            f'X-GM-RAW "in:inbox category:primary after:{today}"'
        )

        last_uid = 0  # start clean

    else:
        last_uid = load_last_uid()

        status, data = mail.uid(
            "search",
            None, 'X-GM-RAW "in:inbox category:primary"'
        )

    if status != "OK":
        return None

    uids = [int(uid) for uid in data[0].split()]
    pending_uids = [uid for uid in uids if uid > last_uid]

    if not pending_uids:
        print("......No pending emails")
        return None

    # Process in correct order
    for uid in pending_uids:
        # tackling deleted emails - if email is deleted, skip it and move to next one
        status, flag_data = mail.uid("fetch", str(uid), "(FLAGS)")
        if status != "OK":
            continue

        flags = flag_data[0].decode()

        if "\\Deleted" in flags:
            print(f"......Ignoring deleted UID {uid}")
            continue

        status, msg_data = mail.uid("fetch", str(uid), "(BODY.PEEK[])")
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_subject(msg)
        body = extract_body(msg)
        
        # Grab the sender right HERE, directly from the 'msg' object
        raw_from = msg.get("From", "")
        sender_name, sender_email = parseaddr(raw_from)

        if is_hotel_email(subject, body):
            print(f"......Processing UID {uid}: {subject} from {sender_email}")
            save_last_uid(uid)
            # Successfully returns both values to stop the unpack error
            return body, sender_email

        else:
            print(f"......Skipped UID {uid}: {subject}")
            save_last_uid(uid)

    return None