from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_candidate_repository import get_followup_candidates


BRAND_NAME = "Phase 5.4.1.1 Candidate Repository Test Brand"
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

    # =========================================================
    # CASE 1
    # follow_up_due + old sent + NO reply
    # EXPECTED: candidate
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

    old_time = TEST_NOW - timedelta(days=5)

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
    # sent + old outreach
    # EXPECTED: NOT candidate
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
    # follow_up_due + old sent + inbound reply
    # EXPECTED: NOT candidate
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
            'Thanks for the message.',
            %s,
            %s
        );
        """,
        (
            case3_conversation,
            TEST_NOW - timedelta(days=2),
            "phase5-4-1-1-case3",
        ),
    )

    # =========================================================
    # CASE 4
    # follow_up_due + old sent + ACTIVE FOLLOW-UP
    # EXPECTED: NOT candidate
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

    followup_time = TEST_NOW + timedelta(days=1)

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
            followup_time,
        ),
    )

    case4_followup = cur.fetchone()[0]
    followup_ids.append(case4_followup)

    # =========================================================
    # CASE 5
    # follow_up_due + recent outreach + no reply
    #
    # EXPECTED: candidate
    #
    # Repository is intentionally status-based.
    # Timing eligibility belongs to transition service.
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

    case5_lead = cur.fetchone()[0]
    lead_ids.append(case5_lead)

    recent_time = TEST_NOW - timedelta(hours=6)

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
            'Case 5',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            case5_lead,
            recent_time,
        ),
    )

    case5_outreach = cur.fetchone()[0]
    outreach_ids.append(case5_outreach)

    conn.commit()

    # =========================================================
    # EXECUTE REPOSITORY
    # =========================================================

    candidates = get_followup_candidates(limit=10)

    print("===== CANDIDATES =====")

    for candidate in candidates:
        print(candidate)

    candidate_ids = {
        str(row[0])
        for row in candidates
    }

    # ---------------------------------------------------------
    # ASSERTIONS
    # ---------------------------------------------------------

    # Case 1 must be returned.
    assert str(case1_lead) in candidate_ids

    # Case 2 must NOT be returned.
    assert str(case2_lead) not in candidate_ids

    # Case 3 must NOT be returned.
    assert str(case3_lead) not in candidate_ids

    # Case 4 must NOT be returned.
    assert str(case4_lead) not in candidate_ids

    # Case 5 is intentionally returned because repository
    # works from lead status, not timing transition.
    assert str(case5_lead) in candidate_ids

    print()
    print("CASE 1 - ELIGIBLE: PASS")
    print("CASE 2 - WRONG LEAD STATUS: PASS")
    print("CASE 3 - INBOUND REPLY: PASS")
    print("CASE 4 - ACTIVE FOLLOW-UP: PASS")
    print("CASE 5 - STATUS-BASED REPOSITORY BEHAVIOR: PASS")

    print()
    print("PHASE 5.4.1.1 CANDIDATE REPOSITORY INTEGRATION TEST PASSED")

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
