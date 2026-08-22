from unittest.mock import patch

from db import get_connection
import send_agent


brand_id = None
contact_id = None
lead_id = None
outreach_id = None
followup_id = None


# =========================================================
# FIXTURE
# =========================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.7.1 SMTP DB Failure Brand',
            'phase571 smtp db failure brand'
        )
        RETURNING brand_id;
        """
    )
    brand_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'SMTP DB Failure Contact',
            'phase571@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )
    contact_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (
            %s,
            'follow_up_due'
        )
        RETURNING lead_id;
        """,
        (brand_id,),
    )
    lead_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            approved_by
        )
        VALUES (
            %s,
            %s,
            'email',
            'Phase 5.7.1 test follow-up message',
            'approved',
            'Phase5.7.1-Test-Reviewer'
        )
        RETURNING outreach_id;
        """,
        (lead_id, contact_id),
    )
    outreach_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO followups (
            lead_id,
            scheduled_for,
            attempt_number,
            status
        )
        VALUES (
            %s,
            NOW(),
            1,
            'scheduled'
        )
        RETURNING followup_id;
        """,
        (lead_id,),
    )
    followup_id = cur.fetchone()[0]

    conn.commit()

    print("===== FIXTURE CREATED =====")
    print("BRAND:", brand_id)
    print("LEAD:", lead_id)
    print("OUTREACH:", outreach_id)
    print("FOLLOWUP:", followup_id)

finally:
    cur.close()
    conn.close()


# =========================================================
# SIMULATE SMTP SUCCESS
# =========================================================

smtp_calls = []


def fake_send_email(
    to_email,
    subject,
    body,
):
    smtp_calls.append(
        {
            "to_email": to_email,
            "subject": subject,
            "body": body,
        }
    )

    print("SIMULATED SMTP SUCCESS")


def failing_mark_sent(
    cur,
    outreach_id,
):
    raise RuntimeError(
        "SIMULATED DATABASE FAILURE AFTER SMTP SUCCESS"
    )


# =========================================================
# EXECUTE
# =========================================================

print()
print("===== EXECUTING FAILURE WINDOW =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
), patch.object(
    send_agent,
    "mark_sent",
    side_effect=failing_mark_sent,
):
    send_agent.run(dry_run=False)


# =========================================================
# VERIFY
# =========================================================

assert len(smtp_calls) == 1
print("CASE 1 - SMTP SUCCESSFUL: PASS")


conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        SELECT status, last_sent_at
        FROM outreach
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    outreach_state = cur.fetchone()

    print("OUTREACH STATE:", outreach_state)

    assert outreach_state[0] == "approved"
    assert outreach_state[1] is None

    print(
        "CASE 2 - OUTREACH ROLLED BACK TO APPROVED: PASS"
    )


    cur.execute(
        """
        SELECT status, outreach_id
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    followup_state = cur.fetchone()

    print("FOLLOW-UP STATE:", followup_state)

    assert followup_state[0] == "scheduled"
    assert followup_state[1] is None

    print(
        "CASE 3 - FOLLOW-UP REMAINS SCHEDULED: PASS"
    )


    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    conversation_count = cur.fetchone()[0]

    print(
        "CONVERSATION COUNT:",
        conversation_count,
    )

    assert conversation_count == 0

    print(
        "CASE 4 - NO CONVERSATION COMMITTED: PASS"
    )


    cur.execute(
        """
        SELECT COUNT(*)
        FROM messages m
        JOIN conversations c
            ON c.conversation_id = m.conversation_id
        WHERE c.outreach_id = %s
          AND m.direction = 'outbound';
        """,
        (outreach_id,),
    )

    outbound_count = cur.fetchone()[0]

    print(
        "OUTBOUND MESSAGE COUNT:",
        outbound_count,
    )

    assert outbound_count == 0

    print(
        "CASE 5 - NO OUTBOUND MESSAGE COMMITTED: PASS"
    )

finally:
    cur.close()
    conn.close()


# =========================================================
# CLEANUP
# =========================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        DELETE FROM brands
        WHERE brand_id = %s;
        """,
        (brand_id,),
    )

    conn.commit()

    print("CLEANUP: PASS")

finally:
    cur.close()
    conn.close()


print()
print(
    "PHASE 5.7.1 SMTP SUCCESS / DB FAILURE TEST PASSED"
)
