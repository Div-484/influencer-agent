from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup
from followup_context import get_followup_context
from followup_agent import generate_followup_message


NOW = datetime.now(timezone.utc)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
followup_id = None

try:
    print("===== PHASE 5.5.3 GENERATOR INTEGRATION =====")

    # ---------------------------------------------------------
    # BRAND
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.5.3 Generator Integration Brand',
            'phase 5.5.3 generator integration brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # CONTACT
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Generator Integration Contact',
            'phase553@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # LEAD
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # PREVIOUS SENT OUTREACH
    # ---------------------------------------------------------

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
            'Original collaboration proposal.',
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

    outreach_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # SCHEDULE FOLLOW-UP
    # ---------------------------------------------------------

    followup = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=NOW,
        attempt_number=1,
    )

    followup_id = followup[0]

    print("FOLLOW-UP:")
    print(followup)

    # ---------------------------------------------------------
    # RETRIEVE CONTEXT
    # ---------------------------------------------------------

    context = get_followup_context(
        followup_id=str(followup_id)
    )

    print()
    print("===== CONTEXT =====")
    print(context)

    assert context["found"] is True

    print("CASE 1 - CONTEXT FOUND: PASS")

    # ---------------------------------------------------------
    # GENERATE MESSAGE
    # ---------------------------------------------------------

    message = generate_followup_message(context)

    print()
    print("===== GENERATED MESSAGE =====")
    print(message)

    assert isinstance(message, str)
    assert len(message.strip()) > 0

    print("CASE 2 - MESSAGE GENERATED: PASS")

    # Must contain contact context
    assert "Generator" in message

    print("CASE 3 - CONTACT CONTEXT USED: PASS")

    # Must contain brand context
    assert "Phase 5.5.3 Generator Integration Brand" in message

    print("CASE 4 - BRAND CONTEXT USED: PASS")

    # Must not be identical to original outreach
    assert message != "Original collaboration proposal."

    print("CASE 5 - ORIGINAL MESSAGE NOT REPEATED VERBATIM: PASS")

    # Generator must not persist anything.
    cur.execute(
        """
        SELECT COUNT(*)
        FROM outreach
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    outreach_count = cur.fetchone()[0]

    print()
    print("OUTREACH COUNT AFTER GENERATION:")
    print(outreach_count)

    assert outreach_count == 1

    print("CASE 6 - GENERATOR DID NOT PERSIST OUTREACH: PASS")

    print()
    print("PHASE 5.5.3 GENERATOR INTEGRATION TEST PASSED")

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
