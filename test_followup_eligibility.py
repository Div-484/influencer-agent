from followup_eligibility import is_followup_eligible


ALL_STATUSES = [
    "new_lead",
    "qualified",
    "watch",
    "rejected",
    "contact_found",
    "manual_sourcing",
    "message_drafted",
    "waiting_for_approval",
    "approved_ready_to_send",
    "message_rejected",
    "sent",
    "replied",
    "follow_up_due",
    "interested",
    "not_interested",
    "negotiating",
    "deal_confirmed",
    "wrong_contact",
    "no_response",
    "do_not_contact",
    "completed",
]


print("===== LEAD STATUS ELIGIBILITY =====")

for status in ALL_STATUSES:
    result = is_followup_eligible(
        lead_status=status,
        attempt_number=1,
        has_active_followup=False,
    )

    expected = status == "follow_up_due"

    print(
        f"{status}: "
        f"{result} "
        f"(expected={expected})"
    )

    assert result == expected


print()
print("===== ACTIVE FOLLOW-UP =====")

result = is_followup_eligible(
    lead_status="follow_up_due",
    attempt_number=1,
    has_active_followup=True,
)

print("ACTIVE FOLLOW-UP RESULT:", result)

assert result is False


print()
print("===== MAX ATTEMPT =====")

result = is_followup_eligible(
    lead_status="follow_up_due",
    attempt_number=3,
    has_active_followup=False,
)

print("ATTEMPT 3 RESULT:", result)

assert result is False


print()
print("===== VALID ATTEMPT 2 =====")

result = is_followup_eligible(
    lead_status="follow_up_due",
    attempt_number=2,
    has_active_followup=False,
)

print("ATTEMPT 2 RESULT:", result)

assert result is True


print()
print("===== INVALID ATTEMPT =====")

try:
    is_followup_eligible(
        lead_status="follow_up_due",
        attempt_number=0,
        has_active_followup=False,
    )

    raise AssertionError(
        "attempt_number=0 should be rejected."
    )

except ValueError as error:
    print("ATTEMPT 0 REJECTED:", error)


print()
print("===== EMPTY STATUS =====")

try:
    is_followup_eligible(
        lead_status="",
        attempt_number=1,
        has_active_followup=False,
    )

    raise AssertionError(
        "Empty lead status should be rejected."
    )

except ValueError as error:
    print("EMPTY STATUS REJECTED:", error)


print()
print("PHASE 5.3.2 ELIGIBILITY TEST PASSED")
