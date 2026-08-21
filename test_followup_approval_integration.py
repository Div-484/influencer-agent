from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup
from followup_outreach_service import create_followup_outreach
from approval_agent import get_drafted_outreach, record_decision


NOW = datetime.now(timezone.utc)

brand_id = None
lead_id = None
contact_id = None
followup_id = None
previous_outreach_id = None
followup_outreach_id = None

conn = get_connection()
cur = conn.cursor()

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
            'Phase 5.4.3.4 Approval Test Brand',
            'phase 5.4.3.4 approval test brand'
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
            'Approval Test Contact',
            'phase5434@example.invalid'
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

    # Previous successful outreach
    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            %s,
            'email',
            'Original collaboration message',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
            NOW - timedelta(days=5),
        ),
    )

    previous_outreach_id = cur.fetchone()[0]

    conn.commit()

    # =========================================================
    # SCHEDULE FOLLOW-UP
    # =========================================================

    followup = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=NOW - timedelta(minutes=1),
        attempt_number=1,
    )

    followup_id = followup[0]

    print("FOLLOW-UP CREATED:")
    print(followup)

    # =========================================================
    # CREATE FOLLOW-UP DRAFT
    # =========================================================

    draft_result = create_followup_outreach(
        followup_id=str(followup_id),
    )

    print()
    print("DRAFT RESULT:")
    print(draft_result)

    assert draft_result["status"] == "drafted"

    followup_outreach_id = draft_result["outreach_id"]

    # =========================================================
    # APPROVAL QUEUE
    # =========================================================

    drafted_rows = get_drafted_outreach(cur)

    matching_rows = [
        row
        for row in drafted_rows
        if str(row[0]) == str(followup_outreach_id)
    ]

    print()
    print("APPROVAL QUEUE MATCH:")
    print(matching_rows)

    assert len(matching_rows) == 1

    row = matching_rows[0]

    assert row[1] == draft_result["message_text"]
    assert row[2] == "Approval Test Contact"
    assert row[3] == "phase5434@example.invalid"
    assert row[4] == "Phase 5.4.3.4 Approval Test Brand"

    print()
    print("CASE 1 - FOLLOW-UP APPEARS IN APPROVAL QUEUE: PASS")

    # =========================================================
    # APPROVE
    # =========================================================

    reviewer = "Phase5-Test-Reviewer"

    record_decision(
        cur,
        str(followup_outreach_id),
        "approved",
        reviewer,
    )

    conn.commit()

    print()
    print("APPROVAL RECORDED")

    # =========================================================
    # OUTREACH VERIFICATION
    # =========================================================

    cur.execute(
        """
        SELECT
            outreach_id,
            status,
            approved_by
        FROM outreach
        WHERE outreach_id = %s;
        """,
        (followup_outreach_id,),
    )

    outreach_row = cur.fetchone()

    print()
    print("OUTREACH VERIFICATION:")
    print(outreach_row)

    assert outreach_row is not None
    assert str(outreach_row[0]) == str(
        followup_outreach_id
    )
    assert outreach_row[1] == "approved"
    assert outreach_row[2] == reviewer

    print()
    print("CASE 2 - OUTREACH APPROVED: PASS")

    # =========================================================
    # APPROVAL AUDIT VERIFICATION
    # =========================================================

    cur.execute(
        """
        SELECT
            outreach_id,
            decision,
            reviewer
        FROM approvals
        WHERE outreach_id = %s
        ORDER BY decided_at DESC
        LIMIT 1;
        """,
        (followup_outreach_id,),
    )

    approval_row = cur.fetchone()

    print()
    print("APPROVAL AUDIT:")
    print(approval_row)

    assert approval_row is not None
    assert str(approval_row[0]) == str(
        followup_outreach_id
    )
    assert approval_row[1] == "approved"
    assert approval_row[2] == reviewer

    print()
    print("CASE 3 - APPROVAL AUDIT CREATED: PASS")

    # =========================================================
    # FOLLOW-UP MUST NOT BE MARKED SENT YET
    # =========================================================

    cur.execute(
        """
        SELECT
            status,
            outreach_id
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    followup_row = cur.fetchone()

    print()
    print("FOLLOW-UP STATUS AFTER APPROVAL:")
    print(followup_row)

    assert followup_row is not None
    assert followup_row[0] == "scheduled"
    assert str(followup_row[1]) == str(
        followup_outreach_id
    )

    print()
    print(
        "CASE 4 - FOLLOW-UP NOT MARKED SENT "
        "BEFORE EMAIL SEND: PASS"
    )

    print()
    print(
        "PHASE 5.4.3.4 APPROVAL INTEGRATION TEST PASSED"
    )

finally:
    # Delete audit records first.
    if followup_outreach_id is not None:
        cur.execute(
            """
            DELETE FROM approvals
            WHERE outreach_id = %s;
            """,
            (followup_outreach_id,),
        )

    if followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
        )

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    if contact_id is not None:
        cur.execute(
            """
            DELETE FROM contacts
            WHERE contact_id = %s;
            """,
            (contact_id,),
        )

    if brand_id is not None:
        cur.execute(
            """
            DELETE FROM brands
            WHERE brand_id = %s;
            """,
            (brand_id,),
        )

    conn.commit()

    cur.close()
    conn.close()
