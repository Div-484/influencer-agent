from unittest.mock import patch

from db import get_connection
import send_agent


BRAND_NAME = "Phase 5.7.3 Send Agent Integration Brand"
CONTACT_NAME = "Send Agent Delivery Attempt Contact"
EMAIL = "phase5736@example.invalid"

brand_id = None
contact_id = None
lead_id = None
outreach_id = None
followup_id = None


def cleanup():
    conn = get_connection()
    cur = conn.cursor()

    try:
        if lead_id:
            cur.execute(
                """
                DELETE FROM leads
                WHERE lead_id = %s;
                """,
                (lead_id,),
            )

        if contact_id:
            cur.execute(
                """
                DELETE FROM contacts
                WHERE contact_id = %s;
                """,
                (contact_id,),
            )

        if brand_id:
            cur.execute(
                """
                DELETE FROM brands
                WHERE brand_id = %s;
                """,
                (brand_id,),
            )

        conn.commit()

    finally:
        cur.close()
        conn.close()


# =============================================================
# FIXTURE
# =============================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        DELETE FROM brands
        WHERE normalized_name = %s;
        """,
        (
            BRAND_NAME.lower().strip(),
        ),
    )

    conn.commit()

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (%s, %s)
        RETURNING brand_id;
        """,
        (
            BRAND_NAME,
            BRAND_NAME.lower().strip(),
        ),
    )
    brand_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (%s, %s, %s)
        RETURNING contact_id;
        """,
        (
            brand_id,
            CONTACT_NAME,
            EMAIL,
        ),
    )
    contact_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (%s, 'follow_up_due')
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
            'Phase 5.7.3 delivery attempt integration test',
            'approved',
            'Phase5.7.3-Test'
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
        ),
    )
    outreach_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO followups (
            lead_id,
            scheduled_for,
            attempt_number,
            status,
            outreach_id
        )
        VALUES (
            %s,
            NOW(),
            1,
            'scheduled',
            %s
        )
        RETURNING followup_id;
        """,
        (
            lead_id,
            outreach_id,
        ),
    )
    followup_id = cur.fetchone()[0]

    conn.commit()

finally:
    cur.close()
    conn.close()


print("===== FIXTURE CREATED =====")
print("BRAND:", brand_id)
print("CONTACT:", contact_id)
print("LEAD:", lead_id)
print("OUTREACH:", outreach_id)
print("FOLLOWUP:", followup_id)


# =============================================================
# ATTEMPT 1
# SMTP SUCCESS + DATABASE FAILURE
# =============================================================

smtp_calls = []


def fake_send_email(
    to_email,
    subject,
    body,
):
    smtp_calls.append(to_email)
    print("SIMULATED SMTP SUCCESS")


original_record_outbound_message = (
    send_agent.record_outbound_message
)


def fail_database_after_smtp(
    cur,
    conversation_id,
    body,
):
    raise RuntimeError(
        "SIMULATED DATABASE FAILURE AFTER SMTP SUCCESS"
    )


print("\n===== ATTEMPT 1 =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
):
    with patch.object(
        send_agent,
        "record_outbound_message",
        side_effect=fail_database_after_smtp,
    ):
        send_agent.run(dry_run=False)


print(
    "SMTP CALL COUNT:",
    len(smtp_calls),
)

assert len(smtp_calls) == 1

print(
    "CASE 1 - SMTP SUCCESS OCCURRED: PASS"
)


# =============================================================
# VERIFY ATTEMPT 1
# =============================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        SELECT
            attempt_number,
            status,
            smtp_started_at,
            smtp_succeeded_at,
            finalized_at,
            last_error
        FROM outreach_delivery_attempts
        WHERE outreach_id = %s
        ORDER BY attempt_number;
        """,
        (outreach_id,),
    )

    attempts_after_failure = cur.fetchall()

    cur.execute(
        """
        SELECT
            status,
            last_sent_at
        FROM outreach
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    outreach_state = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    conversation_count = cur.fetchone()[0]

finally:
    cur.close()
    conn.close()


print("\nATTEMPT HISTORY AFTER DB FAILURE:")

for row in attempts_after_failure:
    print(row)

print(
    "\nOUTREACH STATE:",
    outreach_state,
)

print(
    "CONVERSATION COUNT:",
    conversation_count,
)


assert len(attempts_after_failure) == 1

attempt_1 = attempts_after_failure[0]

assert attempt_1[0] == 1

# Critical 5.7.3 requirement:
# SMTP succeeded, so that evidence must survive
# the later database rollback.
assert attempt_1[1] == "smtp_succeeded"
assert attempt_1[2] is not None
assert attempt_1[3] is not None

assert outreach_state[0] == "approved"
assert outreach_state[1] is None

assert conversation_count == 0

print(
    "CASE 2 - ATTEMPT #1 SMTP SUCCESS PRESERVED: PASS"
)

print(
    "CASE 3 - OUTREACH ROLLED BACK TO APPROVED: PASS"
)

print(
    "CASE 4 - NO CONVERSATION COMMITTED: PASS"
)


# =============================================================
# ATTEMPT 2
# =============================================================

print("\n===== ATTEMPT 2 =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
):
    with patch.object(
        send_agent,
        "record_outbound_message",
        wraps=original_record_outbound_message,
    ):
        send_agent.run(dry_run=False)


print(
    "TOTAL SMTP CALL COUNT:",
    len(smtp_calls),
)

assert len(smtp_calls) == 1

print(
    "CASE 5 - DUPLICATE RETRY SMTP PREVENTED: PASS"
)


# =============================================================
# FINAL VERIFICATION
# =============================================================

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        SELECT
            attempt_number,
            status,
            smtp_started_at,
            smtp_succeeded_at,
            finalized_at,
            last_error
        FROM outreach_delivery_attempts
        WHERE outreach_id = %s
        ORDER BY attempt_number;
        """,
        (outreach_id,),
    )

    final_attempts = cur.fetchall()

    cur.execute(
        """
        SELECT
            status,
            last_sent_at
        FROM outreach
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    final_outreach_state = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    final_conversation_count = cur.fetchone()[0]

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

    outbound_message_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT
            status
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    followup_state = cur.fetchone()

finally:
    cur.close()
    conn.close()


print("\n===== FINAL DELIVERY ATTEMPT HISTORY =====")

for row in final_attempts:
    print(row)

print(
    "\nFINAL OUTREACH STATE:",
    final_outreach_state,
)

print(
    "FINAL CONVERSATION COUNT:",
    final_conversation_count,
)

print(
    "FINAL OUTBOUND MESSAGE COUNT:",
    outbound_message_count,
)

print(
    "FINAL FOLLOW-UP STATE:",
    followup_state,
)


assert len(final_attempts) == 1

assert final_attempts[0][0] == 1
assert final_attempts[0][1] == "smtp_succeeded"
assert final_attempts[0][2] is not None
assert final_attempts[0][3] is not None
assert final_outreach_state[0] == "approved"
assert final_outreach_state[1] is None

assert final_conversation_count == 0
assert outbound_message_count == 0

assert followup_state[0] == "scheduled"

print(
    "CASE 6 - ATTEMPT #1 HISTORY PRESERVED: PASS"
)

print(
    "CASE 7 - NO SECOND DELIVERY ATTEMPT: PASS"
)

print(
    "CASE 8 - OUTREACH REMAINS APPROVED: PASS"
)

print(
    "CASE 9 - NO CONVERSATION COMMITTED: PASS"
)

print(
    "CASE 10 - NO OUTBOUND MESSAGE COMMITTED: PASS"
)

print(
    "CASE 11 - FOLLOW-UP REMAINS SCHEDULED: PASS"
)

print(
    "\nPHASE 5.7.3 SEND AGENT DELIVERY "
    "ATTEMPT INTEGRATION TEST PASSED"
)


cleanup()

print("CLEANUP: PASS")
