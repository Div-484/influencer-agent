from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from db import get_connection
from followup_due_transition import transition_due_leads
from followup_candidate_repository import get_followup_candidates
from followup_orchestrator import schedule_followup_candidates
from followup_outreach_service import create_followup_outreach
from followup_completion import mark_followup_sent_for_outreach
import send_agent


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
original_outreach_id = None
followup_id = None
followup_outreach_id = None


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
            'Phase 5.4.3.9 E2E Brand',
            'phase 5.4.3.9 e2e brand'
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
            'E2E Test Contact',
            'phase5439@example.invalid'
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

    # Original outreach is deliberately older than 3 days.
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
            'Original Phase 5.4.3.9 outreach',
            'sent',
            'Phase5-E2E-Reviewer',
            NOW() - INTERVAL '4 days'
        )
        RETURNING outreach_id;
        """,
        (lead_id, contact_id),
    )
    original_outreach_id = cur.fetchone()[0]

    conn.commit()

    print("===== E2E FIXTURE CREATED =====")
    print("BRAND:", brand_id)
    print("LEAD:", lead_id)
    print("ORIGINAL OUTREACH:", original_outreach_id)

    # =========================================================
    # STEP 1 — SENT -> FOLLOW_UP_DUE
    # =========================================================

    print()
    print("===== STEP 1: FOLLOW-UP DUE TRANSITION =====")

    transition_now = datetime.now(timezone.utc)

    transitioned = transition_due_leads(
        wait_days=3,
        now=transition_now,
    )

    print("TRANSITION RESULT:")
    print(transitioned)

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    lead_status = cur.fetchone()[0]

    print("LEAD STATUS:", lead_status)

    assert lead_status == "follow_up_due"

    print("CASE 1 - LEAD BECAME FOLLOW_UP_DUE: PASS")

    # =========================================================
    # STEP 2 — CANDIDATE DETECTION
    # =========================================================

    print()
    print("===== STEP 2: CANDIDATE DETECTION =====")

    candidates = get_followup_candidates(
        limit=10,
    )

    print("CANDIDATES:")

    for candidate in candidates:
        print(candidate)

    matching_candidates = [
        row
        for row in candidates
        if str(row[0]) == str(lead_id)
    ]

    assert len(matching_candidates) == 1

    print("CASE 2 - LEAD DETECTED AS CANDIDATE: PASS")

    # =========================================================
    # STEP 3 — SCHEDULE
    # =========================================================

    print()
    print("===== STEP 3: FOLLOW-UP SCHEDULING =====")

    schedule_now = datetime.now(timezone.utc)

    schedule_results = schedule_followup_candidates(
        limit=10,
        delay_days=3,
        attempt_number=1,
        now=schedule_now,
    )

    print("SCHEDULER RESULTS:")

    for result in schedule_results:
        print(result)

    matching_schedule = [
        result
        for result in schedule_results
        if result.get("lead_id") == str(lead_id)
    ]

    assert len(matching_schedule) == 1

    schedule_result = matching_schedule[0]

    assert schedule_result["status"] == "scheduled"

    followup_id = schedule_result["followup_id"]

    print("FOLLOWUP:", followup_id)
    print("CASE 3 - FOLLOW-UP SCHEDULED: PASS")

    # =========================================================
    # STEP 4 — CREATE FOLLOW-UP OUTREACH
    # =========================================================

    print()
    print("===== STEP 4: FOLLOW-UP OUTREACH DRAFT =====")

    draft_result = create_followup_outreach(
        followup_id=str(followup_id),
    )

    print("DRAFT RESULT:")
    print(draft_result)

    assert draft_result["status"] == "drafted"

    followup_outreach_id = draft_result["outreach_id"]

    assert followup_outreach_id is not None

    print(
        "FOLLOW-UP OUTREACH:",
        followup_outreach_id,
    )

    print("CASE 4 - FOLLOW-UP OUTREACH DRAFTED: PASS")

    # =========================================================
    # STEP 5 — APPROVAL
    # =========================================================

    print()
    print("===== STEP 5: APPROVAL =====")

    cur.execute(
        """
        UPDATE outreach
        SET
            status = 'approved',
            approved_by = 'Phase5-E2E-Reviewer'
        WHERE outreach_id = %s
        RETURNING outreach_id, status, approved_by;
        """,
        (followup_outreach_id,),
    )

    approval_result = cur.fetchone()

    conn.commit()

    print("APPROVAL RESULT:")
    print(approval_result)

    assert approval_result is not None
    assert approval_result[1] == "approved"

    print("CASE 5 - FOLLOW-UP OUTREACH APPROVED: PASS")

    # =========================================================
    # STEP 6 — SEND
    # =========================================================

    print()
    print("===== STEP 6: FOLLOW-UP SEND =====")

    with patch("send_agent.send_email") as mock_send:

        mock_send.return_value = None

        send_agent.run(
            dry_run=False,
        )

        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count == 1

        assert any(
            len(call.args) >= 1
            and str(call.args[0])
            == "phase5439@example.invalid"
            for call in mock_send.call_args_list
        )

    print("CASE 6 - FOLLOW-UP EMAIL SENT: PASS")

    # =========================================================
    # STEP 7 — COMPLETION
    # =========================================================

    print()
    print("===== STEP 7: FOLLOW-UP COMPLETION =====")

    completion_result = mark_followup_sent_for_outreach(
        str(followup_outreach_id),
    )

    print("COMPLETION RESULT:")
    print(completion_result)

    assert completion_result["status"] in (
        "sent",
        "not_updated",
    )

    # =========================================================
    # FINAL STATE
    # =========================================================

    cur.execute(
        """
        SELECT
            l.status,
            o.status,
            o.last_sent_at,
            f.status,
            f.outreach_id
        FROM leads l
        JOIN followups f
            ON f.lead_id = l.lead_id
        JOIN outreach o
            ON o.outreach_id = f.outreach_id
        WHERE l.lead_id = %s
          AND f.followup_id = %s;
        """,
        (lead_id, followup_id),
    )

    final_state = cur.fetchone()

    print()
    print("===== FINAL E2E STATE =====")
    print(final_state)

    assert final_state is not None

    final_lead_status = final_state[0]
    final_outreach_status = final_state[1]
    final_last_sent_at = final_state[2]
    final_followup_status = final_state[3]
    final_linked_outreach = final_state[4]

    assert final_lead_status == "follow_up_due"
    assert final_outreach_status == "sent"
    assert final_last_sent_at is not None
    assert final_followup_status == "sent"
    assert str(final_linked_outreach) == str(
        followup_outreach_id
    )

    print("CASE 7 - FINAL LEAD STATUS VALID: PASS")
    print("CASE 8 - OUTREACH MARKED SENT: PASS")
    print("CASE 9 - LAST_SENT_AT SET: PASS")
    print("CASE 10 - FOLLOW-UP MARKED SENT: PASS")
    print("CASE 11 - FOLLOW-UP/OUTREACH LINK VALID: PASS")

    # =========================================================
    # STEP 8 — DUPLICATE SEND PROTECTION
    # =========================================================

    print()
    print("===== STEP 8: DUPLICATE SEND PROTECTION =====")

    with patch("send_agent.send_email") as mock_send_again:

        mock_send_again.return_value = None

        send_agent.run(
            dry_run=False,
        )

        print(
            "SECOND SMTP CALL COUNT:",
            mock_send_again.call_count,
        )

        assert mock_send_again.call_count == 0

    print("CASE 12 - NO DUPLICATE SEND: PASS")

    # =========================================================
    # DUPLICATE DATABASE COUNTS
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (followup_outreach_id,),
    )

    conversation_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM messages m
        JOIN conversations c
            ON c.conversation_id = m.conversation_id
        WHERE c.outreach_id = %s
          AND m.direction = 'outbound';
        """,
        (followup_outreach_id,),
    )

    outbound_count = cur.fetchone()[0]

    print()
    print("CONVERSATION COUNT:", conversation_count)
    print("OUTBOUND MESSAGE COUNT:", outbound_count)

    assert conversation_count == 1
    assert outbound_count == 1

    print("CASE 13 - NO DUPLICATE CONVERSATION: PASS")
    print("CASE 14 - NO DUPLICATE OUTBOUND MESSAGE: PASS")

    print()
    print(
        "PHASE 5.4.3.9 END-TO-END LIFECYCLE TEST PASSED"
    )

finally:
    # =========================================================
    # CLEANUP
    # =========================================================

    try:
        if followup_outreach_id is not None:
            cur.execute(
                """
                DELETE FROM messages
                WHERE conversation_id IN (
                    SELECT conversation_id
                    FROM conversations
                    WHERE outreach_id = %s
                );
                """,
                (followup_outreach_id,),
            )

            cur.execute(
                """
                DELETE FROM conversations
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

        if followup_outreach_id is not None:
            cur.execute(
                """
                DELETE FROM outreach
                WHERE outreach_id = %s;
                """,
                (followup_outreach_id,),
            )

        if original_outreach_id is not None:
            cur.execute(
                """
                DELETE FROM outreach
                WHERE outreach_id = %s;
                """,
                (original_outreach_id,),
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

    finally:
        cur.close()
        conn.close()
