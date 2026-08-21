from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_eligibility import MAX_FOLLOWUP_ATTEMPTS
from followup_eligibility_repository import get_followup_eligibility
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.3.3 Eligibility Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()


conn = get_connection()
cur = conn.cursor()

brand_id = None
eligible_lead_id = None
sent_lead_id = None
active_followup_id = None

try:
    # ---------------------------------------------------------
    # FIXTURE
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

    # Lead 1: follow_up_due
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

    eligible_lead_id = cur.fetchone()[0]

    # Lead 2: sent
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

    sent_lead_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # TEST 1
    # follow_up_due + no active follow-up
    # ---------------------------------------------------------

    result = get_followup_eligibility(
        lead_id=str(eligible_lead_id),
        attempt_number=1,
    )

    print("TEST 1 - ELIGIBLE:")
    print(result)

    assert result["eligible"] is True
    assert result["reason"] == "eligible"
    assert result["lead_status"] == "follow_up_due"

    # ---------------------------------------------------------
    # TEST 2
    # sent + no active follow-up
    # ---------------------------------------------------------

    result = get_followup_eligibility(
        lead_id=str(sent_lead_id),
        attempt_number=1,
    )

    print()
    print("TEST 2 - SENT LEAD:")
    print(result)

    assert result["eligible"] is False
    assert result["reason"] == "invalid_lead_status"
    assert result["lead_status"] == "sent"

    # ---------------------------------------------------------
    # TEST 3
    # follow_up_due + active scheduled follow-up
    # ---------------------------------------------------------

    scheduled_for = (
        datetime.now(timezone.utc)
        + timedelta(days=3)
    )

    followup = schedule_followup(
        lead_id=str(eligible_lead_id),
        scheduled_for=scheduled_for,
        attempt_number=1,
    )

    active_followup_id = followup[0]

    result = get_followup_eligibility(
        lead_id=str(eligible_lead_id),
        attempt_number=2,
    )

    print()
    print("TEST 3 - ACTIVE FOLLOW-UP:")
    print(result)

    assert result["eligible"] is False
    assert result["reason"] == "active_followup_exists"

    # ---------------------------------------------------------
    # TEST 4
    # follow_up_due + attempt exceeds maximum
    # ---------------------------------------------------------

    # Remove active follow-up first so max-attempt rule
    # is tested independently.
    cur.execute(
        """
        DELETE FROM followups
        WHERE followup_id = %s;
        """,
        (active_followup_id,),
    )

    active_followup_id = None
    conn.commit()

    result = get_followup_eligibility(
        lead_id=str(eligible_lead_id),
        attempt_number=MAX_FOLLOWUP_ATTEMPTS + 1,
    )

    print()
    print("TEST 4 - MAX ATTEMPTS:")
    print(result)

    assert result["eligible"] is False
    assert result["reason"] == "max_attempts_reached"

    # ---------------------------------------------------------
    # TEST 5
    # invalid lead ID
    # ---------------------------------------------------------

    fake_lead_id = (
        "00000000-0000-0000-0000-000000000000"
    )

    result = get_followup_eligibility(
        lead_id=fake_lead_id,
        attempt_number=1,
    )

    print()
    print("TEST 5 - LEAD NOT FOUND:")
    print(result)

    assert result["eligible"] is False
    assert result["reason"] == "lead_not_found"

    print()
    print("PHASE 5.3.3 DATABASE ELIGIBILITY TEST PASSED")

finally:
    if active_followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (active_followup_id,),
        )

    if eligible_lead_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE lead_id = %s;
            """,
            (eligible_lead_id,),
        )

    if eligible_lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (eligible_lead_id,),
        )

    if sent_lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (sent_lead_id,),
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
