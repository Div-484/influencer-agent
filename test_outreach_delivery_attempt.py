from db import get_connection

from outreach_delivery_attempt import (
    create_delivery_attempt,
    get_next_attempt_number,
    mark_failed,
    mark_finalized,
    mark_smtp_succeeded,
)


brand_id = None
contact_id = None
lead_id = None
outreach_id = None


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


conn = get_connection()
cur = conn.cursor()

try:
    # =========================================================
    # FIXTURE
    cur.execute(
        """
        DELETE FROM brands
        WHERE normalized_name = %s;
        """,
        (
            "phase 5.7.3 delivery attempt service test",
        ),
    )

    conn.commit()
    # =========================================================

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
            "Phase 5.7.3 Delivery Attempt Service Test",
            "phase 5.7.3 delivery attempt service test",
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
            "Delivery Attempt Test Contact",
            "phase5735@example.invalid",
        ),
    )

    contact_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (%s, 'sent')
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
            'Delivery attempt service test',
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
# =============================================================

print("\n===== ATTEMPT 1 =====")

attempt_1_number = get_next_attempt_number(
    str(outreach_id)
)

print(
    "NEXT ATTEMPT NUMBER:",
    attempt_1_number,
)

assert attempt_1_number == 1

attempt_1_id = create_delivery_attempt(
    outreach_id=str(outreach_id),
    attempt_number=attempt_1_number,
)

print(
    "ATTEMPT 1 CREATED:",
    attempt_1_id,
)

mark_smtp_succeeded(
    str(attempt_1_id)
)

print(
    "ATTEMPT 1 SMTP SUCCESS RECORDED"
)

mark_failed(
    str(attempt_1_id),
    "Simulated DB finalization failure",
)

print(
    "ATTEMPT 1 FAILURE RECORDED"
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

    attempts = cur.fetchall()

finally:
    cur.close()
    conn.close()


print("\nATTEMPT HISTORY AFTER ATTEMPT 1:")

for row in attempts:
    print(row)


assert len(attempts) == 1
assert attempts[0][0] == 1
assert attempts[0][1] == "smtp_succeeded"
assert attempts[0][2] is not None
assert attempts[0][3] is not None
assert attempts[0][4] is None
assert attempts[0][5] == "Simulated DB finalization failure"

print("CASE 1 - ATTEMPT 1 PRESERVED: PASS")
print("CASE 2 - SMTP SUCCESS TIMESTAMP PRESERVED: PASS")


# =============================================================
# ATTEMPT 2
# =============================================================

print("\n===== ATTEMPT 2 =====")

attempt_2_number = get_next_attempt_number(
    str(outreach_id)
)

print(
    "NEXT ATTEMPT NUMBER:",
    attempt_2_number,
)

assert attempt_2_number == 2

attempt_2_id = create_delivery_attempt(
    outreach_id=str(outreach_id),
    attempt_number=attempt_2_number,
)

print(
    "ATTEMPT 2 CREATED:",
    attempt_2_id,
)

mark_smtp_succeeded(
    str(attempt_2_id)
)

print(
    "ATTEMPT 2 SMTP SUCCESS RECORDED"
)

mark_finalized(
    str(attempt_2_id)
)

print(
    "ATTEMPT 2 FINALIZED"
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

finally:
    cur.close()
    conn.close()


print("\n===== FINAL ATTEMPT HISTORY =====")

for row in final_attempts:
    print(row)


assert len(final_attempts) == 2

assert final_attempts[0][0] == 1
assert final_attempts[0][1] == "smtp_succeeded"

assert final_attempts[1][0] == 2
assert final_attempts[1][1] == "finalized"
assert final_attempts[1][2] is not None
assert final_attempts[1][3] is not None
assert final_attempts[1][4] is not None

print(
    "CASE 3 - ATTEMPT NUMBERS ARE UNIQUE: PASS"
)

print(
    "CASE 4 - ATTEMPT 1 HISTORY PRESERVED: PASS"
)

print(
    "CASE 5 - ATTEMPT 2 FINALIZED: PASS"
)

print(
    "\nPHASE 5.7.3 DELIVERY ATTEMPT SERVICE TEST PASSED"
)


cleanup()

print("CLEANUP: PASS")
