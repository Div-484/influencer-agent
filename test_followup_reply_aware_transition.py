from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_due_transition import transition_due_leads


BRAND_NAME = "Phase 5.3.4.3 Reply Aware Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

TEST_NOW = datetime(
    2026,
    8,
    13,
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

    # ---------------------------------------------------------
    # CASE 1
    # Old sent + NO reply
    # Expected: follow_up_due
    # ---------------------------------------------------------

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

    outreach_ids.append(cur.fetchone()[0])

    # ---------------------------------------------------------
    # CASE 2
    # Old sent + inbound reply
    # Expected: remain sent
    # ---------------------------------------------------------

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

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id
        )
        VALUES (%s)
        RETURNING conversation_id;
        """,
        (case2_outreach,),
    )

    case2_conversation = cur.fetchone()[0]
    conversation_ids.append(case2_conversation)

    # Inbound reply, classification intentionally NULL.
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
            'Thanks for reaching out.',
            %s,
            %s
        );
        """,
        (
            case2_conversation,
            TEST_NOW - timedelta(days=2),
            "phase5-3-4-3-case2",
        ),
    )

    # ---------------------------------------------------------
    # CASE 3
    # Old sent + inbound reply + interested classification
    # Expected: remain sent
    # ---------------------------------------------------------

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
            outreach_id,
            classification
        )
        VALUES (
            %s,
            'interested'
        )
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
            'I am interested.',
            %s,
            %s
        );
        """,
        (
            case3_conversation,
            TEST_NOW - timedelta(days=2),
            "phase5-3-4-3-case3",
        ),
    )

    # ---------------------------------------------------------
    # CASE 4
    # Old sent + no reply, but recent outreach
    # Expected: remain sent
    # ---------------------------------------------------------

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

    case4_lead = cur.fetchone()[0]
    lead_ids.append(case4_lead)

    recent_time = TEST_NOW - timedelta(hours=12)

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
            recent_time,
        ),
    )

    outreach_ids.append(cur.fetchone()[0])

    # ---------------------------------------------------------
    # CASE 5
    # Old sent + inbound reply + negotiating classification
    # Expected: remain sent
    # ---------------------------------------------------------

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

    case5_lead = cur.fetchone()[0]
    lead_ids.append(case5_lead)

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
            old_time,
        ),
    )

    case5_outreach = cur.fetchone()[0]
    outreach_ids.append(case5_outreach)

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id,
            classification
        )
        VALUES (
            %s,
            'negotiating'
        )
        RETURNING conversation_id;
        """,
        (case5_outreach,),
    )

    case5_conversation = cur.fetchone()[0]
    conversation_ids.append(case5_conversation)

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
            'Can we discuss the rate?',
            %s,
            %s
        );
        """,
        (
            case5_conversation,
            TEST_NOW - timedelta(days=2),
            "phase5-3-4-3-case5",
        ),
    )

    conn.commit()

    # ---------------------------------------------------------
    # EXECUTE TRANSITION
    # ---------------------------------------------------------

    result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print("TRANSITION RESULT:")
    print(result)

    transitioned_ids = {
        str(row[0])
        for row in result
    }

    # ---------------------------------------------------------
    # ASSERTIONS
    # ---------------------------------------------------------

    # Case 1 MUST transition.
    assert str(case1_lead) in transitioned_ids

    # Cases 2-5 MUST NOT transition.
    assert str(case2_lead) not in transitioned_ids
    assert str(case3_lead) not in transitioned_ids
    assert str(case4_lead) not in transitioned_ids
    assert str(case5_lead) not in transitioned_ids

    # ---------------------------------------------------------
    # DATABASE STATUS VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            lead_id,
            status
        FROM leads
        WHERE lead_id = ANY(%s::uuid[])
        ORDER BY lead_id;
        """,
        (lead_ids,),
    )

    rows = cur.fetchall()

    print()
    print("STATUS VERIFICATION:")

    for row in rows:
        print(row)

    # Case 1 transitioned.
    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (case1_lead,),
    )

    assert cur.fetchone()[0] == "follow_up_due"

    # Case 2 remains sent.
    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (case2_lead,),
    )

    assert cur.fetchone()[0] == "sent"

    # Case 3 remains sent.
    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (case3_lead,),
    )

    assert cur.fetchone()[0] == "sent"

    # Case 4 remains sent.
    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (case4_lead,),
    )

    assert cur.fetchone()[0] == "sent"

    # Case 5 remains sent.
    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (case5_lead,),
    )

    assert cur.fetchone()[0] == "sent"

    print()
    print("PHASE 5.3.4.3 REPLY-AWARE TRANSITION TEST PASSED")

finally:
    # Messages first.
    if conversation_ids:
        cur.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        )

    # Conversations.
    if conversation_ids:
        cur.execute(
            """
            DELETE FROM conversations
            WHERE conversation_id = ANY(%s::uuid[]);
            """,
            (conversation_ids,),
        )

    # Outreach.
    if outreach_ids:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE outreach_id = ANY(%s::uuid[]);
            """,
            (outreach_ids,),
        )

    # Leads.
    if lead_ids:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = ANY(%s::uuid[]);
            """,
            (lead_ids,),
        )

    # Brand.
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
