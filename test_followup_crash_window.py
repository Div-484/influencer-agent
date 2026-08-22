from unittest.mock import patch

from db import get_connection
import send_agent


brand_id = None
contact_id = None
lead_id = None
outreach_id = None
followup_id = None

smtp_calls = []


# =========================================================
# FIXTURE
# =========================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        DELETE FROM brands
        WHERE normalized_name = %s;
        """,
        (
            "phase572 crash window brand",
        ),
    )

    conn.commit()

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.7.2 Crash Window Brand',
            'phase572 crash window brand'
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
            'Crash Window Contact',
            'phase572@example.invalid'
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
            'Phase 5.7.2 crash-window test message',
            'approved',
            'Phase5.7.2-Test-Reviewer'
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
# SIMULATED SMTP
# =========================================================

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


# =========================================================
# SIMULATE CRASH AFTER SMTP
# =========================================================

def crash_after_smtp(
    cur,
    outreach_id,
):
    raise RuntimeError(
        "SIMULATED PROCESS CRASH AFTER SMTP SUCCESS"
    )


print()
print("===== ATTEMPT 1: SMTP SUCCESS + DB CRASH =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
), patch.object(
    send_agent,
    "mark_sent",
    side_effect=crash_after_smtp,
):
    send_agent.run(dry_run=False)


print()
print("SMTP CALLS AFTER ATTEMPT 1:", len(smtp_calls))

assert len(smtp_calls) == 1

print("CASE 1 - FIRST SMTP SEND OCCURRED: PASS")


# =========================================================
# VERIFY DATABASE STATE
# =========================================================

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

    state = cur.fetchone()

    print("STATE AFTER CRASH:", state)

    assert state[0] == "approved"
    assert state[1] is None

    print(
        "CASE 2 - DATABASE STILL SHOWS APPROVED: PASS"
    )

finally:
    cur.close()
    conn.close()


# =========================================================
# ATTEMPT 2
# =========================================================

print()
print("===== ATTEMPT 2: DUPLICATE PREVENTION AFTER CRASH =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
):
    send_agent.run(dry_run=False)


print()
print("TOTAL SMTP CALLS:", len(smtp_calls))

assert len(smtp_calls) == 1

print(
    "CASE 3 - DUPLICATE SMTP SEND PREVENTED: PASS"
)


# =========================================================
# FINAL DATABASE STATE
# =========================================================
# =========================================================

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

    final_state = cur.fetchone()

    print("FINAL OUTREACH STATE:", final_state)

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
    "PHASE 5.7.3 CRASH-WINDOW DUPLICATE PREVENTION TEST PASSED"
)
