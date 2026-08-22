"""
Send Agent.

Sends approved outreach emails and records successful delivery.

Safety rules:
  - Only approved email outreach is eligible.
  - --dry-run never sends or changes the database.
  - SMTP success is followed by database state recording.
  - Follow-up completion is updated only after outreach is marked sent.
  - Failed sends remain approved and are not marked sent.
"""

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from outreach_delivery_attempt import (
    create_delivery_attempt,
    get_next_attempt_number,
    mark_failed,
    mark_finalized,
    mark_smtp_succeeded,
)
from dotenv import load_dotenv

from db import get_connection
from followup_completion import mark_followup_sent_for_outreach


load_dotenv()


SMTP_HOST = os.environ.get(
    "SMTP_HOST",
    "smtp.gmail.com",
)

SMTP_PORT = int(
    os.environ.get(
        "SMTP_PORT",
        "465",
    )
)

SMTP_EMAIL = os.environ.get(
    "SMTP_EMAIL"
)

SMTP_APP_PASSWORD = os.environ.get(
    "SMTP_APP_PASSWORD"
)


def get_approved_email_outreach(cur):
    """
    Fetch approved email outreach that has not yet been sent.
    """

    cur.execute(
        """
        SELECT
            o.outreach_id,
            o.message_text,
            c.email,
            c.name,
            b.name
        FROM outreach o
        JOIN contacts c
            ON c.contact_id = o.contact_id
        JOIN leads l
            ON l.lead_id = o.lead_id
        JOIN brands b
            ON b.brand_id = l.brand_id
        WHERE o.status = 'approved'
          AND o.channel = 'email';
        """
    )

    return cur.fetchall()


def send_email(
    to_email: str,
    subject: str,
    body: str,
):
    """
    Send one email through SMTP.
    Raises on failure.
    """

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise ValueError(
            "SMTP_EMAIL / SMTP_APP_PASSWORD not set in .env."
        )

    msg = EmailMessage()

    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    msg.set_content(body)

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        SMTP_HOST,
        SMTP_PORT,
        context=context,
    ) as server:

        server.login(
            SMTP_EMAIL,
            SMTP_APP_PASSWORD,
        )

        server.send_message(msg)

def get_smtp_succeeded_attempts(
    cur,
    outreach_ids,
):
    """
    Return outreach IDs whose latest delivery attempt
    already has confirmed SMTP success.

    Such outreach must not be sent again automatically.
    """

    if not outreach_ids:
        return set()

    cur.execute(
        """
        SELECT DISTINCT ON (outreach_id)
            outreach_id,
            status
        FROM outreach_delivery_attempts
        WHERE outreach_id = ANY(%s::uuid[])
        ORDER BY
            outreach_id,
            attempt_number DESC;
        """,
        (list(outreach_ids),),
    )

    rows = cur.fetchall()

    return {
        str(outreach_id)
        for outreach_id, status in rows
        if status == "smtp_succeeded"
    }

def get_or_create_conversation(
    cur,
    outreach_id: str,
):
    """
    Return the conversation for an outreach.

    Create one when it does not exist.
    """

    cur.execute(
        """
        SELECT conversation_id
        FROM conversations
        WHERE outreach_id = %s
        ORDER BY created_at
        LIMIT 1;
        """,
        (outreach_id,),
    )

    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id
        )
        VALUES (%s)
        RETURNING conversation_id;
        """,
        (outreach_id,),
    )

    return cur.fetchone()[0]


def record_outbound_message(
    cur,
    conversation_id: str,
    body: str,
):
    """
    Record successful outbound message.
    """

    cur.execute(
        """
        INSERT INTO messages (
            conversation_id,
            direction,
            body,
            sent_at
        )
        VALUES (
            %s,
            'outbound',
            %s,
            NOW()
        )
        RETURNING message_id;
        """,
        (
            conversation_id,
            body,
        ),
    )

    return cur.fetchone()[0]


def mark_sent(
    cur,
    outreach_id: str,
):
    """
    Mark outreach as successfully sent.
    """

    cur.execute(
        """
        UPDATE outreach
        SET
            status = 'sent',
            last_sent_at = NOW()
        WHERE outreach_id = %s
          AND status = 'approved'
        RETURNING outreach_id;
        """,
        (outreach_id,),
    )

    row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            "Outreach was not marked sent; "
            "it may no longer be approved."
        )

    return row[0]


def run(
    dry_run: bool,
):
    conn = get_connection()
    cur = conn.cursor()

    try:

        rows = get_approved_email_outreach(cur)
        smtp_succeeded_ids = get_smtp_succeeded_attempts(
            cur,
            [
                str(row[0])
                for row in rows
            ],
        )

        if smtp_succeeded_ids:
            print(
                "WARNING: "
                f"{len(smtp_succeeded_ids)} approved "
                "outreach item(s) have confirmed SMTP "
                "success and will NOT be resent."
            )

        rows = [
            row
            for row in rows
            if str(row[0]) not in smtp_succeeded_ids
        ]

        if not rows:
            print(
                "No approved email outreach waiting to be sent."
            )
            return

        print(
            f"Found {len(rows)} approved message(s).\n"
        )

        sent = 0
        failed = 0

        for (
            outreach_id,
            message_text,
            to_email,
            contact_name,
            brand_name,
        ) in rows:

            subject = (
                f"Collaboration opportunity with "
                f"{brand_name}"
            )

            if dry_run:

                print(
                    f"[DRY RUN] Would send to "
                    f"{contact_name} <{to_email}>"
                )

                print(
                    f"          Subject: {subject}"
                )

                print(
                    f"          outreach_id: "
                    f"{outreach_id}\n"
                )

                continue

            attempt_id = None

            try:

                # =================================================
                # 1. CREATE INDEPENDENT DELIVERY ATTEMPT
                # =================================================

                attempt_number = get_next_attempt_number(
                    str(outreach_id)
                )

                attempt_id = create_delivery_attempt(
                    outreach_id=str(outreach_id),
                    attempt_number=attempt_number,
                )

                # =================================================
                # 2. SMTP
                # =================================================

                send_email(
                    to_email,
                    subject,
                    message_text,
                )

                mark_smtp_succeeded(
                    str(attempt_id)
                )

                # =================================================
                # 3. DATABASE SUCCESS RECORD
                # =================================================

                conversation_id = (
                    get_or_create_conversation(
                        cur,
                        str(outreach_id),
                    )
                )

                message_id = (
                    record_outbound_message(
                        cur,
                        conversation_id,
                        message_text,
                    )
                )

                mark_sent(
                    cur,
                    str(outreach_id),
                )

                # =================================================
                # 3. FOLLOW-UP COMPLETION
                # =================================================

                followup_result = (
                    mark_followup_sent_for_outreach(
                        outreach_id=str(
                            outreach_id
                        ),
                        cur=cur,
                    )
                )

                # =================================================
                # 4. COMMIT
                # =================================================

                conn.commit()

                # =================================================
                # 5. DELIVERY ATTEMPT FINALIZATION
                # =================================================

                mark_finalized(
                    str(attempt_id)
                )

                sent += 1

                print(
                    f"Sent to {contact_name} "
                    f"<{to_email}> "
                    f"| outreach_id={outreach_id} "
                    f"| conversation_id={conversation_id} "
                    f"| message_id={message_id} "
                    f"| followup_status="
                    f"{followup_result['status']}"
                )

            except Exception as error:

                conn.rollback()

                if attempt_id is not None:
                    try:
                        mark_failed(
                            str(attempt_id),
                            str(error),
                        )
                    except Exception as tracking_error:
                        print(
                            "WARNING: Failed to record "
                            "delivery attempt failure: "
                            f"{tracking_error}"
                        )

                failed += 1

                print(
                    f"FAILED to send to "
                    f"{contact_name} <{to_email}>: "
                    f"{error}"
                )

        if dry_run:

            print(
                f"\nDRY RUN complete. "
                f"{len(rows)} message(s) would be sent. "
                f"Run with --send to actually send them."
            )

        else:

            print("\nSUCCESS")
            print(f"Sent: {sent}")
            print(f"Failed: {failed}")

    finally:

        cur.close()
        conn.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Send approved outreach emails."
    )

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, sends nothing.",
    )

    group.add_argument(
        "--send",
        action="store_true",
        help="Actually send approved emails.",
    )

    args = parser.parse_args()

    run(
        dry_run=args.dry_run
    )
