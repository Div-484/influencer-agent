from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from db import get_connection
from followup_scheduler import schedule_followup
from followup_outreach_service import create_followup_outreach


NOW = datetime.now(timezone.utc)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
original_outreach_id = None
followup_id = None

try:
    print("===== PHASE 5.5.4 CONTEXT-AWARE DRAFT INTEGRATION =====")

    # =========================================================
    # BRAND
    # =========================================================

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.5.4 Context Draft Brand',
            'phase 5.5.4 context draft brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # =========================================================
    # CONTACT
    # =========================================================

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Context Draft Contact',
            'phase554@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # =========================================================
    # LEAD
    # =========================================================

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

    # =========================================================
    # PREVIOUS OUTREACH
    # =========================================================

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
            'Original message for context testing.',
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

    original_outreach_id = cur.fetchone()[0]

    conn.commit()

    # =========================================================
    # FOLLOW-UP
    # =========================================================

    followup = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=NOW,
        attempt_number=1,
    )

    followup_id = followup[0]

    print("FOLLOW-UP:")
    print(followup)

    # =========================================================
    # MOCK GENERATOR
    #
    # This proves the draft service actually delegates
    # message generation to followup_agent.
    # =========================================================

    generated_message = (
        "CONTEXT-AWARE GENERATED MESSAGE - "
        "Phase 5.5.4"
    )

    with patch(
        "followup_outreach_service.generate_followup_message"
    ) as mock_generator:

        mock_generator.return_value = generated_message

        result = create_followup_outreach(
            followup_id=str(followup_id)
        )

        print()
        print("DRAFT RESULT:")
        print(result)

        # =====================================================
        # CASE 1 - GENERATOR CALLED
        # =====================================================

        assert mock_generator.call_count == 1

        print(
            "CASE 1 - CONTEXT GENERATOR CALLED: PASS"
        )

        # =====================================================
        # CASE 2 - CONTEXT PASSED TO GENERATOR
        # =====================================================

        generator_context = (
            mock_generator.call_args.args[0]
        )

        assert generator_context["found"] is True
        assert generator_context["followup"] is not None
        assert generator_context["lead"] is not None
        assert generator_context["brand"] is not None
        assert generator_context["contact"] is not None
        assert generator_context["previous_outreach"] is not None

        print(
            "CASE 2 - COMPLETE CONTEXT PASSED: PASS"
        )

        # =====================================================
        # CASE 3 - GENERATED MESSAGE USED
        # =====================================================

        assert result["status"] == "drafted"
        assert result["message_text"] == generated_message

        print(
            "CASE 3 - GENERATED MESSAGE USED: PASS"
        )

        # =====================================================
        # CASE 4 - OUTREACH CREATED AS DRAFT
        # =====================================================

        outreach_id = result["outreach_id"]

        cur.execute(
            """
            SELECT
                status,
                message_text,
                channel
            FROM outreach
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

        outreach_row = cur.fetchone()

        print()
        print("OUTREACH:")
        print(outreach_row)

        assert outreach_row is not None
        assert outreach_row[0] == "drafted"
        assert outreach_row[1] == generated_message
        assert outreach_row[2] == "email"

        print(
            "CASE 4 - GENERATED OUTREACH DRAFT CREATED: PASS"
        )

        # =====================================================
        # CASE 5 - FOLLOW-UP LINKED
        # =====================================================

        cur.execute(
            """
            SELECT
                outreach_id
            FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
        )

        linked_outreach_id = cur.fetchone()[0]

        assert str(linked_outreach_id) == str(
            outreach_id
        )

        print(
            "CASE 5 - FOLLOW-UP/OUTREACH LINK CREATED: PASS"
        )

    # =========================================================
    # CASE 6 - IDEMPOTENCY
    # =========================================================

    second_result = create_followup_outreach(
        followup_id=str(followup_id)
    )

    print()
    print("SECOND EXECUTION:")
    print(second_result)

    assert second_result["status"] == "already_processed"

    print(
        "CASE 6 - DRAFT IDEMPOTENCY PRESERVED: PASS"
    )

    print()
    print(
        "PHASE 5.5.4 CONTEXT-AWARE DRAFT INTEGRATION TEST PASSED"
    )

finally:
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
