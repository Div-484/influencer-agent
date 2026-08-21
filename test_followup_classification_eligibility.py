from db import get_connection
from followup_eligibility_repository import get_followup_eligibility


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
            'Phase 5.5.7 Eligibility Guard Brand',
            'phase 5.5.7 eligibility guard brand'
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
            'Eligibility Guard Contact',
            'phase557@example.invalid'
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

    # =========================================================
    # SENT OUTREACH
    # =========================================================

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

    # =========================================================
    # NOT INTERESTED CONVERSATION
    # =========================================================

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
    # CASE 1
    # NOT INTERESTED MUST BLOCK
    # =========================================================

    result = get_followup_eligibility(
        lead_id=str(lead_id),
        attempt_number=1,
    )

    print()
    print("NOT INTERESTED RESULT:")
    print(result)

    assert result["eligible"] is False

    assert result["reason"] == (
        "conversation_not_interested"
    )

    assert result["lead_status"] == (
        "follow_up_due"
    )

    assert result[
        "conversation_classification"
    ] == "not_interested"

    print(
        "CASE 1 - NOT INTERESTED FOLLOW-UP BLOCKED: PASS"
    )

    # =========================================================
    # CASE 2
    # CHANGE CLASSIFICATION TO INTERESTED
    # =========================================================

    cur.execute(
        """
        UPDATE conversations
        SET classification = 'interested'
        WHERE conversation_id = %s;
        """,
        (conversation_id,),
    )

    conn.commit()

    result = get_followup_eligibility(
        lead_id=str(lead_id),
        attempt_number=1,
    )

    print()
    print("INTERESTED RESULT:")
    print(result)

    assert result["eligible"] is True
    assert result["reason"] == "eligible"
    assert result["lead_status"] == "follow_up_due"
    assert result[
        "conversation_classification"
    ] == "interested"

    print(
        "CASE 2 - INTERESTED FOLLOW-UP ALLOWED: PASS"
    )

    # =========================================================
    # CASE 3
    # QUESTION SHOULD ALSO BE ALLOWED
    # =========================================================

    cur.execute(
        """
        UPDATE conversations
        SET classification = 'question'
        WHERE conversation_id = %s;
        """,
        (conversation_id,),
    )

    conn.commit()

    result = get_followup_eligibility(
        lead_id=str(lead_id),
        attempt_number=1,
    )

    print()
    print("QUESTION RESULT:")
    print(result)

    assert result["eligible"] is True
    assert result["reason"] == "eligible"

    print(
        "CASE 3 - QUESTION FOLLOW-UP ALLOWED: PASS"
    )

    # =========================================================
    # CASE 4
    # NEGOTIATING SHOULD ALSO BE ALLOWED
    # =========================================================

    cur.execute(
        """
        UPDATE conversations
        SET classification = 'negotiating'
        WHERE conversation_id = %s;
        """,
        (conversation_id,),
    )

    conn.commit()

    result = get_followup_eligibility(
        lead_id=str(lead_id),
        attempt_number=1,
    )

    print()
    print("NEGOTIATING RESULT:")
    print(result)

    assert result["eligible"] is True
    assert result["reason"] == "eligible"

    print(
        "CASE 4 - NEGOTIATING FOLLOW-UP ALLOWED: PASS"
    )

    # =========================================================
    # CASE 5
    # NO RESPONSE SHOULD ALSO BE ALLOWED
    # =========================================================

    cur.execute(
        """
        UPDATE conversations
        SET classification = 'no_response'
        WHERE conversation_id = %s;
        """,
        (conversation_id,),
    )

    conn.commit()

    result = get_followup_eligibility(
        lead_id=str(lead_id),
        attempt_number=1,
    )

    print()
    print("NO RESPONSE RESULT:")
    print(result)

    assert result["eligible"] is True
    assert result["reason"] == "eligible"

    print(
        "CASE 5 - NO RESPONSE FOLLOW-UP ALLOWED: PASS"
    )

    print()
    print(
        "PHASE 5.5.7 CLASSIFICATION ELIGIBILITY GUARD TEST PASSED"
    )

finally:

    # =========================================================
    # CLEANUP
    # =========================================================

    try:
        conn.rollback()

        if conversation_id:
            cur.execute(
                """
                DELETE FROM conversations
                WHERE conversation_id = %s;
                """,
                (conversation_id,),
            )

        if outreach_id:
            cur.execute(
                """
                DELETE FROM outreach
                WHERE outreach_id = %s;
                """,
                (outreach_id,),
            )

        if lead_id:
            cur.execute(
                """
                DELETE FROM leads
                WHERE lead_id = %s;
                """,
                (lead_id,),
            )

        if contact_id:
            cur.execute(
                """
                DELETE FROM contacts
                WHERE contact_id = %s;
                """,
                (contact_id,),
            )

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
        raise

    finally:
        cur.close()
        conn.close()