from db import get_connection
from followup_orchestrator import schedule_followup_candidates


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
conversation_id = None

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
            'Phase 5.5.8 Orchestrator Guard Brand',
            'phase 5.5.8 orchestrator guard brand'
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
            'Orchestrator Guard Contact',
            'phase558@example.invalid'
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
            approved_by,
            last_sent_at
        )
        VALUES (
            %s,
            %s,
            'email',
            'Original collaboration proposal.',
            'sent',
            'Phase5-Test',
            NOW() - INTERVAL '5 days'
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
        INSERT INTO conversations (
            outreach_id,
            classification
        )
        VALUES (
            %s,
            'not_interested'
        )
        RETURNING conversation_id;
        """,
        (outreach_id,),
    )
    conversation_id = cur.fetchone()[0]

    conn.commit()

    print("===== FIXTURE CREATED =====")
    print("BRAND:", brand_id)
    print("LEAD:", lead_id)
    print("OUTREACH:", outreach_id)
    print("CONVERSATION:", conversation_id)

    # =========================================================
    # ORCHESTRATOR
    # =========================================================

    print()
    print("===== ORCHESTRATOR RESULT =====")

    results = schedule_followup_candidates(
        limit=10,
        delay_days=3,
        attempt_number=1,
    )

    print(results)

    matching = [
        row
        for row in results
        if str(row.get("lead_id")) == str(lead_id)
    ]

    assert matching, (
        "Test lead was not evaluated by orchestrator."
    )

    result = matching[0]

    assert result["status"] == "skipped"

    assert result["reason"] == (
        "conversation_not_interested"
    )

    print()
    print(
        "CASE 1 - ORCHESTRATOR BLOCKED NOT_INTERESTED: PASS"
    )

    # =========================================================
    # DATABASE VERIFICATION
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM followups
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    followup_count = cur.fetchone()[0]

    print()
    print("FOLLOW-UP COUNT:", followup_count)

    assert followup_count == 0

    print(
        "CASE 2 - NO FOLLOW-UP SCHEDULED: PASS"
    )

    # =========================================================
    # ACTIVE FOLLOW-UP CHECK
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM followups
        WHERE lead_id = %s
          AND status = 'scheduled';
        """,
        (lead_id,),
    )

    active_count = cur.fetchone()[0]

    print(
        "ACTIVE FOLLOW-UP COUNT:",
        active_count,
    )

    assert active_count == 0

    print(
        "CASE 3 - NO ACTIVE FOLLOW-UP CREATED: PASS"
    )

    print()
    print(
        "PHASE 5.5.8 ORCHESTRATOR CLASSIFICATION GUARD TEST PASSED"
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

    except Exception:
        conn.rollback()

    cur.close()
    conn.close()
