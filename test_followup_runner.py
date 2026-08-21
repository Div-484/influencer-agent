from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from followup_runner import run_followup_cycle


print("===== FOLLOW-UP RUNNER INTEGRATION TEST =====")


fake_now = datetime.now(timezone.utc)


with patch(
    "followup_runner.transition_due_leads"
) as mock_transition, patch(
    "followup_runner.schedule_followup_candidates"
) as mock_schedule, patch(
    "followup_runner.create_followup_outreach"
) as mock_draft:

    mock_transition.return_value = [
        ("lead-001", "follow_up_due")
    ]

    mock_schedule.return_value = [
        {
            "lead_id": "lead-001",
            "status": "scheduled",
            "followup_id": "followup-001",
            "attempt_number": 1,
            "scheduled_for": fake_now
            + timedelta(days=3),
        }
    ]

    mock_draft.return_value = {
        "status": "drafted",
        "followup_id": "followup-001",
        "outreach_id": "outreach-001",
        "message_text": "Test follow-up draft",
    }

    result = run_followup_cycle(
        limit=10,
        wait_days=3,
    )


print()
print("RESULT:")
print(result)


# =========================================================
# CASE 1 - DUE TRANSITION CALLED
# =========================================================

assert mock_transition.call_count == 1

mock_transition.assert_called_once_with(
    wait_days=3,
)

print(
    "CASE 1 - DUE TRANSITION CALLED: PASS"
)


# =========================================================
# CASE 2 - SCHEDULING CALLED
# =========================================================

assert mock_schedule.call_count == 1

mock_schedule.assert_called_once_with(
    limit=10,
)

print(
    "CASE 2 - SCHEDULING CALLED: PASS"
)


# =========================================================
# CASE 3 - DRAFT CREATED
# =========================================================

assert mock_draft.call_count == 1

mock_draft.assert_called_once_with(
    followup_id="followup-001",
)

print(
    "CASE 3 - FOLLOW-UP DRAFT CREATED: PASS"
)


# =========================================================
# CASE 4 - RESULT STRUCTURE
# =========================================================

assert "due_transition" in result
assert "scheduling" in result
assert "drafts" in result
assert "errors" in result

assert result["due_transition"] == [
    ("lead-001", "follow_up_due")
]

assert result["drafts"][0]["status"] == "drafted"

assert result["errors"] == []

print(
    "CASE 4 - RESULT STRUCTURE VALID: PASS"
)


# =========================================================
# CASE 5 - ONLY SCHEDULED FOLLOW-UPS ARE DRAFTED
# =========================================================

with patch(
    "followup_runner.transition_due_leads",
    return_value=[],
), patch(
    "followup_runner.schedule_followup_candidates",
    return_value=[
        {
            "lead_id": "lead-skip",
            "status": "skipped",
            "reason": "conversation_not_interested",
        },
        {
            "lead_id": "lead-scheduled",
            "status": "scheduled",
            "followup_id": "followup-002",
            "attempt_number": 1,
            "scheduled_for": fake_now,
        },
    ],
), patch(
    "followup_runner.create_followup_outreach",
    return_value={
        "status": "drafted",
        "followup_id": "followup-002",
        "outreach_id": "outreach-002",
        "message_text": "Test draft",
    },
) as draft_mock:

    result = run_followup_cycle()


assert draft_mock.call_count == 1

draft_mock.assert_called_once_with(
    followup_id="followup-002",
)

print(
    "CASE 5 - ONLY SCHEDULED FOLLOW-UPS DRAFTED: PASS"
)


# =========================================================
# CASE 6 - RUNNER DOES NOT SEND EMAIL
# =========================================================

assert not hasattr(
    __import__("followup_runner"),
    "send_email",
)

print(
    "CASE 6 - RUNNER DOES NOT SEND EMAIL: PASS"
)


print()
print(
    "PHASE 5.6 FOLLOW-UP RUNNER INTEGRATION TEST PASSED"
)
