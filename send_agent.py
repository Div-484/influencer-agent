"""
Send Agent — sends APPROVED outreach emails and marks them as sent.

Safety rules (by design):
  - Only picks up rows where status = 'approved'. Drafted/rejected rows
    are never touched.
  - Requires an explicit --send flag to actually send anything.
    Run with --dry-run first to preview without sending or changing
    the database.
  - On a successful send, sets status='sent' AND last_sent_at=now()
    together in the same update, satisfying the database's
    outreach_check constraint.
  - If sending one email fails, it's skipped (left as 'approved') and
    the script continues with the rest — one bad email won't block
    the others.

Usage:
    python send_agent.py --dry-run
    python send_agent.py --send

Requires these in .env:
    SMTP_EMAIL=youraddress@gmail.com
    SMTP_APP_PASSWORD=your_16_char_app_password
    SMTP_HOST=smtp.gmail.com      (optional, this is the default)
    SMTP_PORT=465                 (optional, this is the default)
"""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv
from db import get_connection

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD")


def get_approved_email_outreach(cur):
    """Fetches all approved, not-yet-sent email outreach, joined with
    contact and brand info needed to actually send and write a subject."""
    cur.execute(
        """
        SELECT o.outreach_id, o.message_text, c.email, c.name, b.name
        FROM outreach o
        JOIN contacts c ON c.contact_id = o.contact_id
        JOIN leads l ON l.lead_id = o.lead_id
        JOIN brands b ON b.brand_id = l.brand_id
        WHERE o.status = 'approved' AND o.channel = 'email';
        """
    )
    return cur.fetchall()  # list of (outreach_id, message_text, email, contact_name, brand_name)


def send_email(to_email: str, subject: str, body: str):
    """Sends one email via SMTP. Raises on failure."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise ValueError(
            "SMTP_EMAIL / SMTP_APP_PASSWORD not set in .env. "
            "See the top of this file for what's needed."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)


def mark_sent(cur, outreach_id: str):
    cur.execute(
        """
        UPDATE outreach
        SET status = 'sent', last_sent_at = now()
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )


def run(dry_run: bool):
    conn = get_connection()
    cur = conn.cursor()

    try:
        rows = get_approved_email_outreach(cur)

        if not rows:
            print("No approved email outreach waiting to be sent.")
            return

        print(f"Found {len(rows)} approved message(s).\n")

        sent = 0
        failed = 0

        for outreach_id, message_text, to_email, contact_name, brand_name in rows:
            subject = f"Collaboration opportunity with {brand_name}"

            if dry_run:
                print(f"[DRY RUN] Would send to {contact_name} <{to_email}>")
                print(f"          Subject: {subject}")
                print(f"          outreach_id: {outreach_id}\n")
                continue

            try:
                send_email(to_email, subject, message_text)
                mark_sent(cur, outreach_id)
                conn.commit()
                sent += 1
                print(f"Sent to {contact_name} <{to_email}> | outreach_id={outreach_id}")
            except Exception as e:
                failed += 1
                print(f"FAILED to send to {contact_name} <{to_email}>: {e}")
                # this one row's failure shouldn't affect the others

        if dry_run:
            print(f"\nDRY RUN complete. {len(rows)} message(s) would be sent. "
                  f"Run with --send to actually send them.")
        else:
            print(f"\nSUCCESS")
            print(f"Sent: {sent}")
            print(f"Failed: {failed}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send approved outreach emails.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview only, sends nothing.")
    group.add_argument("--send", action="store_true", help="Actually send the approved emails.")
    args = parser.parse_args()

    run(dry_run=args.dry_run)
