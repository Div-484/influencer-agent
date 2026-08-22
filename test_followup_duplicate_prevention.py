from unittest.mock import patch

from db import get_connection
import send_agent


BRAND_NAME = "Phase 5.7.3 Duplicate Prevention Test Brand"
CONTACT_NAME = "Duplicate Prevention Contact"
EMAIL = "phase5737@example.invalid"

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
        (BRAND_NAME.lower().strip(),),
    )

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
        VALUES (
            %s,
            'sent'
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
            'Phase 5.7.3 duplicate prevention test',
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

    conn.commit()

finally:
    cur.close()
    conn.close()


print("===== FIXTURE CREATED =====")
print("BRAND:", brand_id)
print("CONTACT:", contact_id)
print("LEAD:", lead_id)
print("OUTREACH:", outreach_id)


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


def fail_after_smtp(
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
        side_effect=fail_after_smtp,
    ):
        send_agent.run(dry_run=False)


print(
    "SMTP CALL COUNT AFTER ATTEMPT 1:",
    len(smtp_calls),
)

assert len(smtp_calls) == 1

print(
    "CASE 1 - FIRST SMTP SEND OCCURRED: PASS"
)


# =============================================================
# VERIFY SMTP-SUCCEEDED STATE
# =============================================================

conn = get_connection()
cur = conn.cursor()

try:
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
        SELECT
            attempt_number,
            status,
            smtp_succeeded_at,
            finalized_at,
            last_error
        FROM outreach_delivery_attempts
        WHERE outreach_id = %s
        ORDER BY attempt_number;
        """,
        (outreach_id,),
    )

    attempts = cur.fetchall()

finally:
    cur.close()
    conn.close()


print("\nOUTREACH STATE:", outreach_state)

print("\nDELIVERY ATTEMPT HISTORY:")

for row in attempts:
    print(row)


assert outreach_state[0] == "approved"
assert outreach_state[1] is None

assert len(attempts) == 1
assert attempts[0][0] == 1
assert attempts[0][1] == "smtp_succeeded"
assert attempts[0][2] is not None
assert attempts[0][3] is None

print(
    "CASE 2 - SMTP-SUCCEEDED ATTEMPT PRESERVED: PASS"
)


# =============================================================
# ATTEMPT 2
# DUPLICATE PREVENTION CHECK
# =============================================================

print("\n===== ATTEMPT 2 / DUPLICATE CHECK =====")

with patch.object(
    send_agent,
    "send_email",
    side_effect=fake_send_email,
):
    send_agent.run(dry_run=False)


print(
    "TOTAL SMTP CALL COUNT:",
    len(smtp_calls),
)


# =============================================================
# CURRENT EXPECTED BEHAVIOR
# =============================================================

if len(smtp_calls) == 1:
    print(
        "CASE 3 - DUPLICATE SMTP SEND PREVENTED: PASS"
    )
else:
    print(
        "CASE 3 - DUPLICATE SMTP SEND PREVENTION: FAIL"
    )

    print(
        "CURRENT IMPLEMENTATION STILL SENDS "
        "APPROVED OUTREACH WITH SMTP-SUCCEEDED ATTEMPT."
    )

    raise AssertionError(
        "Duplicate SMTP send was not prevented."
    )


# =============================================================
# FINAL STATE
# =============================================================

conn = get_connection()
cur = conn.cursor()

try:
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
        FROM outreach_delivery_attempts
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    attempt_count = cur.fetchone()[0]

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


print(
    "\nFINAL OUTREACH STATE:",
    final_outreach_state,
)

print(
    "DELIVERY ATTEMPT COUNT:",
    attempt_count,
)

print(
    "CONVERSATION COUNT:",
    conversation_count,
)


assert final_outreach_state[0] == "approved"
assert final_outreach_state[1] is None
assert attempt_count == 1
assert conversation_count == 0

print(
    "CASE 4 - NO SECOND DELIVERY ATTEMPT CREATED: PASS"
)

print(
    "CASE 5 - OUTREACH REMAINS UNFINALIZED: PASS"
)

print(
    "\nPHASE 5.7.3 DUPLICATE PREVENTION TEST PASSED"
)


cleanup()

print("CLEANUP: PASS")