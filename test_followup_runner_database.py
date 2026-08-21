from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_runner import run_followup_cycle


conn = get_connection()
cur = conn.cursor()

brand_id = None

try:
    # =========================================================
    # FIXTURE
    # =========================================================

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.6 Runner Integration Brand',
            'phase 5.6 runner integration brand'
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
            'Runner Integration Contact',
            'phase56runner@example.invalid'
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
            'sent'
        )
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    lead_id = cur.fetchone()[0]

    sent_at = (
        datetime.now(timezone.utc)
        - timedelta(days=4)
    )

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            approved_by,
            last_sent_at
        )
        VALUES (
            %s,
            %s,
            'email',
            'Original Phase 5.6 runner integration outreach',
            'sent',
            'Phase5.6-Test-Reviewer',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
            sent_at,
        ),
    )

    original_outreach_id = cur.fetchone()[0]

    conn.commit()

    print("===== FIXTURE CREATED =====")
    print("BRAND:", brand_id)
    print("LEAD:", lead_id)
    print("OUTREACH:", original_outreach_id)

finally:
    cur.close()
    conn.close()


try:
    # =========================================================
    # RUN REAL FOLLOW-UP CYCLE
    # =========================================================

    result = run_followup_cycle(
        limit=10,
        wait_days=3,
    )

    print()
    print("===== RUNNER RESULT =====")
    print(result)

    assert result["errors"] == []

    print(
        "CASE 1 - RUNNER COMPLETED WITHOUT ERRORS: PASS"
    )

    # =========================================================
    # LEAD STATUS
    # =========================================================

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    lead_status = cur.fetchone()[0]

    print()
    print("LEAD STATUS:", lead_status)

    assert lead_status == "follow_up_due"

    print(
        "CASE 2 - LEAD TRANSITIONED TO FOLLOW_UP_DUE: PASS"
    )

    # =========================================================
    # FOLLOW-UP
    # =========================================================

    cur.execute(
        """
        SELECT
            followup_id,
            lead_id,
            attempt_number,
            status,
            outreach_id
        FROM followups
        WHERE lead_id = %s
        ORDER BY attempt_number DESC
        LIMIT 1;
        """,
        (lead_id,),
    )

    followup = cur.fetchone()

    print()
    print("FOLLOW-UP:", followup)

    assert followup is not None
    assert followup[1] == lead_id
    assert followup[2] == 1
    assert followup[3] == "scheduled"

    followup_id = followup[0]

    print(
        "CASE 3 - FOLLOW-UP SCHEDULED: PASS"
    )

    # =========================================================
    # OUTREACH DRAFT
    # =========================================================

    cur.execute(
        """
        SELECT
            outreach_id,
            status,
            channel,
            message_text
        FROM outreach
        WHERE lead_id = %s
        ORDER BY created_at DESC
        LIMIT 1;
        """,
        (lead_id,),
    )

    draft = cur.fetchone()

    print()
    print("DRAFT OUTREACH:", draft)

    assert draft is not None
    assert draft[1] == "drafted"
    assert draft[2] == "email"
    assert draft[3]

    draft_outreach_id = draft[0]

    print(
        "CASE 4 - FOLLOW-UP OUTREACH DRAFTED: PASS"
    )

    # =========================================================
    # FOLLOW-UP / OUTREACH LINK
    # =========================================================

    cur.execute(
        """
        SELECT outreach_id
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    linked_outreach = cur.fetchone()[0]

    print()
    print("FOLLOW-UP OUTREACH LINK:", linked_outreach)

    assert linked_outreach == draft_outreach_id

    print(
        "CASE 5 - FOLLOW-UP/OUTREACH LINK CREATED: PASS"
    )

    # =========================================================
    # NO SEND
    # =========================================================

    assert draft[1] == "drafted"

    print(
        "CASE 6 - RUNNER DID NOT SEND EMAIL: PASS"
    )

    print()
    print(
        "PHASE 5.6 DATABASE RUNNER INTEGRATION TEST PASSED"
    )

finally:
    try:
        conn.rollback()

        if brand_id:
            cur.execute(
                """
                DELETE FROM brands
                WHERE brand_id = %s;
                """,
                (brand_id,),
            )

            conn.commit()

        print()
        print("CLEANUP: PASS")

    except Exception:
        conn.rollback()

    cur.close()
    conn.close()
