from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_orchestrator import schedule_followup_candidates


BRAND_NAME = "Phase 5.4.2 Orchestrator Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

TEST_NOW = datetime(
    2026,
    8,
    20,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_ids = []
outreach_ids = []
conversation_ids = []
followup_ids = []

try:
    # ---------------------------------------------------------
    # BRAND
    # ---------------------------------------------------------

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
            NORMALIZED_NAME,
        ),
    )

    brand_id = cur.fetchone()[0]

    old_time = TEST_NOW - timedelta(days=5)

    # =========================================================
    # CASE 1
    # follow_up_due + old sent + no reply
    # EXPECTED: scheduled
    # =========================================================

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

    case1_lead = cur.fetchone()[0]
    lead_ids.append(case1_lead)

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            'email',
            'Case 1',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            case1_lead,
            old_time,
        ),
    )

    case1_outreach = cur.fetchone()[0]
    outreach_ids.append(case1_outreach)

    # =========================================================
    # CASE 2
    # sent lead
    # EXPECTED: not scheduled
    # =========================================================

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

    case2_lead = cur.fetchone()[0]
    lead_ids.append(case2_lead)

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            'email',
            'Case 2',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            case2_lead,
            old_time,
        ),
    )

    case2_outreach = cur.fetchone()[0]
    outreach_ids.append(case2_outreach)

    # =========================================================
    # CASE 3
    # follow_up_due + inbound reply
    # EXPECTED: not scheduled
    # =========================================================

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

    case3_lead = cur.fetchone()[0]
    lead_ids.append(case3_lead)

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            'email',
            'Case 3',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            case3_lead,
            old_time,
        ),
    )

    case3_outreach = cur.fetchone()[0]
    outreach_ids.append(case3_outreach)

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id
        )
        VALUES (%s)
        RETURNING conversation_id;
        """,
        (case3_outreach,),
    )

    case3_conversation = cur.fetchone()[0]
    conversation_ids.append(case3_conversation)

    cur.execute(
        """
        INSERT INTO messages (
            conversation_id,
            direction,
            body,
            sent_at,
            external_message_id
        )
        VALUES (
            %s,
            'inbound',
            'Thanks for your email.',
            %s,
            %s
        );
        """,
        (
            case3_conversation,
            TEST_NOW - timedelta(days=2),
            "phase5-4-2-case3",
        ),
    )

    # =========================================================
    # CASE 4
    # follow_up_due + active follow-up
    # EXPECTED: not scheduled
    # =========================================================

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

    case4_lead = cur.fetchone()[0]
    lead_ids.append(case4_lead)

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            'email',
            'Case 4',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            case4_lead,
            old_time,
        ),
    )

    case4_outreach = cur.fetchone()[0]
    outreach_ids.append(case4_outreach)

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
            %s,
            1,
            'scheduled'
        )
        RETURNING followup_id;
        """,
        (
            case4_lead,
            TEST_NOW + timedelta(days=1),
        ),
    )

    case4_followup = cur.fetchone()[0]
    followup_ids.append(case4_followup)

    conn.commit()

    # ---------------------------------------------------------
    # EXECUTE ORCHESTRATOR
    # ---------------------------------------------------------

    results = schedule_followup_candidates(
        limit=10,
        delay_days=3,
        attempt_number=1,
        now=TEST_NOW,
    )

    print("===== ORCHESTRATOR RESULTS =====")

    for result in results:
        print(result)

    # ---------------------------------------------------------
    # CASE 1 MUST BE SCHEDULED
    # ---------------------------------------------------------

    case1_results = [
        r for r in results
        if r["lead_id"] == str(case1_lead)
    ]

    assert len(case1_results) == 1

    case1_result = case1_results[0]

    assert case1_result["status"] == "scheduled"

    assert (
        case1_result["scheduled_for"]
        == TEST_NOW + timedelta(days=3)
    )

    followup_ids.append(
        case1_result["followup_id"]
    )

    # ---------------------------------------------------------
    # CASE 2 MUST NOT APPEAR
    # ---------------------------------------------------------

    assert not any(
        r["lead_id"] == str(case2_lead)
        for r in results
    )

    # ---------------------------------------------------------
    # CASE 3 MUST NOT APPEAR
    # ---------------------------------------------------------

    assert not any(
        r["lead_id"] == str(case3_lead)
        for r in results
    )

    # ---------------------------------------------------------
    # CASE 4 MUST NOT APPEAR
    # ---------------------------------------------------------

    assert not any(
        r["lead_id"] == str(case4_lead)
        for r in results
    )

    # ---------------------------------------------------------
    # DATABASE VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            lead_id,
            attempt_number,
            status,
            scheduled_for
        FROM followups
        WHERE lead_id = %s
        ORDER BY attempt_number;
        """,
        (case1_lead,),
    )

    row = cur.fetchone()

    print()
    print("DATABASE VERIFICATION:")
    print(row)

    assert row is not None
    assert row[1] == 1
    assert row[2] == "scheduled"

    assert row[3] == (
        TEST_NOW + timedelta(days=3)
    )

    print()
    print("CASE 1 - ELIGIBLE: PASS")
    print("CASE 2 - WRONG STATUS: PASS")
    print("CASE 3 - INBOUND REPLY: PASS")
    print("CASE 4 - ACTIVE FOLLOW-UP: PASS")

    print()
    print("PHASE 5.4.2 ORCHESTRATOR INTEGRATION TEST PASSED")

finally:
    # Messages
    if conversation_ids:
        cur.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        )

    # Conversations
    if conversation_ids:
        cur.execute(
            """
            DELETE FROM conversations
            WHERE conversation_id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        )

    # Follow-ups
    if followup_ids:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = ANY(%s::uuid[]);
            """,
            (followup_ids,),
        )

    # Outreach
    if outreach_ids:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE outreach_id = ANY(%s::uuid[]);
            """,
            (outreach_ids,),
        )

    # Leads
    if lead_ids:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = ANY(%s::uuid[]);
            """,
            (lead_ids,),
        )

    # Brand
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
