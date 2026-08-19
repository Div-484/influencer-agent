"""
Reply Processor - stores inbound email replies in conversations.

Phase 1A:
    - Match sender by exact contact email.
    - Find latest sent outreach for that contact.
    - Reuse/create one conversation per outreach.
    - Store inbound replies.
    - Prevent duplicate inbound messages using external_message_id.
"""

from db import get_connection
from reply_classifier import classify_reply
from reply_status import get_lead_status


def find_existing_message(cur, external_message_id: str):
    """Return existing message details for an external message ID."""
    cur.execute(
        """
        SELECT
            message_id,
            conversation_id
        FROM messages
        WHERE external_message_id = %s
        LIMIT 1;
        """,
        (external_message_id,),
    )

    return cur.fetchone()


def find_contact_and_outreach(cur, sender_email: str):
    """Find the contact and latest sent outreach for the sender."""
    cur.execute(
        """
        SELECT
            c.contact_id,
            o.outreach_id,
            o.lead_id
        FROM contacts c
        JOIN outreach o
            ON o.contact_id = c.contact_id
        WHERE LOWER(c.email) = LOWER(%s)
          AND o.status = 'sent'
        ORDER BY o.last_sent_at DESC NULLS LAST
        LIMIT 1;
        """,
        (sender_email.strip(),),
    )

    return cur.fetchone()


def get_or_create_conversation(cur, outreach_id: str):
    """
    Return the conversation for an outreach.

    The unique index on conversations.outreach_id prevents
    duplicate conversations under concurrent processing.
    """
    cur.execute(
        """
        SELECT conversation_id
        FROM conversations
        WHERE outreach_id = %s
        LIMIT 1;
        """,
        (outreach_id,),
    )

    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO conversations (outreach_id)
        VALUES (%s)
        ON CONFLICT (outreach_id)
        DO UPDATE SET updated_at = NOW()
        RETURNING conversation_id;
        """,
        (outreach_id,),
    )

    return cur.fetchone()[0]


def record_inbound_message(
    cur,
    conversation_id: str,
    body: str,
    external_message_id: str,
):
    """
    Insert an inbound message.

    The unique partial index on external_message_id provides
    database-level duplicate protection.
    """
    cur.execute(
        """
        SELECT message_id, conversation_id
        FROM messages
        WHERE external_message_id = %s
        LIMIT 1;
        """,
        (external_message_id,),
    )

    existing = cur.fetchone()

    if existing:
        return existing[0], False, existing[1]

    try:
        cur.execute(
            """
            INSERT INTO messages (
                conversation_id,
                direction,
                body,
                sent_at,
                external_message_id
            )
            VALUES (
                %s,
                'inbound',
                %s,
                NOW(),
                %s
            )
            RETURNING message_id;
            """,
            (
                conversation_id,
                body,
                external_message_id,
            ),
        )

        return cur.fetchone()[0], True, conversation_id

    except Exception:
        cur.execute(
            """
            SELECT message_id, conversation_id
            FROM messages
            WHERE external_message_id = %s
            LIMIT 1;
            """,
            (external_message_id,),
        )

        existing = cur.fetchone()

        if existing:
            return existing[0], False, existing[1]

        raise


def process_inbound_reply(
    sender_email: str,
    body: str,
    external_message_id: str,
):
    """Process one already-received inbound reply."""
    if not sender_email or not sender_email.strip():
        raise ValueError("sender_email is required.")

    if not body or not body.strip():
        raise ValueError("body is required.")

    if not external_message_id or not external_message_id.strip():
        raise ValueError("external_message_id is required.")

    sender_email = sender_email.strip()
    body = body.strip()
    external_message_id = external_message_id.strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        existing = find_existing_message(
            cur,
            external_message_id,
        )

        if existing:
            message_id, conversation_id = existing

            conn.commit()

            return {
                "matched": True,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "created": False,
                "duplicate": True,
            }

        match = find_contact_and_outreach(
            cur,
            sender_email,
        )

        if not match:
            conn.rollback()

            return {
                "matched": False,
                "reason": "No sent outreach found for sender email.",
                "sender_email": sender_email,
            }

        contact_id, outreach_id, lead_id = match

        conversation_id = get_or_create_conversation(
            cur,
            outreach_id,
        )

        message_id, created, actual_conversation_id = record_inbound_message(
            cur,
            conversation_id,
            body,
            external_message_id,
        )

        conversation_id = actual_conversation_id

        classification = classify_reply(body)
        new_lead_status = get_lead_status(classification)

        cur.execute(
            """
            UPDATE conversations
            SET classification = %s::conversation_classification,
                updated_at = NOW()
            WHERE conversation_id = %s;
            """,
            (
                classification,
                conversation_id,
            ),
        )

        cur.execute(
            """
            UPDATE leads
            SET status = %s::lead_status,
                updated_at = NOW()
            WHERE lead_id = %s;
            """,
            (
                new_lead_status,
                lead_id,
            ),
        )
        conn.commit()

        return {
            "matched": True,
            "contact_id": contact_id,
            "outreach_id": outreach_id,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "created": created,
            "duplicate": not created,
            "classification": classification,
            "lead_status": new_lead_status,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
