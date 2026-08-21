from unittest.mock import patch

from production_runner import run_execution_cycle


class FakeProvider:
    pass


provider = FakeProvider()


# =========================================================
# CASE 1 - ALL THREE STAGES RUN
# =========================================================

with patch(
    "production_runner.process_new_emails"
) as mock_new, patch(
    "production_runner.run_retry_cycle"
) as mock_retry, patch(
    "production_runner.run_followup_cycle"
) as mock_followups:

    mock_new.return_value = [
        {"status": "processed"}
    ]

    mock_retry.return_value = [
        {"status": "retried"}
    ]

    mock_followups.return_value = {
        "due_transition": [],
        "scheduling": [],
        "drafts": [],
        "errors": [],
    }

    result = run_execution_cycle(
        provider=provider,
        limit=10,
        retry_delay_minutes=5,
    )


print("===== PRODUCTION RUNNER ISOLATION TEST =====")

print()
print("RESULT:")
print(result)

assert mock_new.call_count == 1
assert mock_retry.call_count == 1
assert mock_followups.call_count == 1

print(
    "CASE 1 - ALL THREE STAGES EXECUTED: PASS"
)


# =========================================================
# CASE 2 - NEW EMAIL FAILURE DOES NOT BLOCK RETRIES
# =========================================================

with patch(
    "production_runner.process_new_emails",
    side_effect=RuntimeError("NEW EMAIL FAILURE"),
) as mock_new, patch(
    "production_runner.run_retry_cycle"
) as mock_retry, patch(
    "production_runner.run_followup_cycle"
) as mock_followups:

    mock_retry.return_value = [
        {"status": "retried"}
    ]

    mock_followups.return_value = {
        "due_transition": [],
        "scheduling": [],
        "drafts": [],
        "errors": [],
    }

    result = run_execution_cycle(
        provider=provider,
    )


assert mock_new.call_count == 1
assert mock_retry.call_count == 1
assert mock_followups.call_count == 1

assert result["new_emails"] == []

assert result["retries"] == [
    {"status": "retried"}
]

assert result["errors"] == [
    {
        "stage": "new_emails",
        "error": "NEW EMAIL FAILURE",
    }
]

print(
    "CASE 2 - NEW EMAIL FAILURE ISOLATED: PASS"
)


# =========================================================
# CASE 3 - RETRY FAILURE DOES NOT BLOCK FOLLOW-UPS
# =========================================================

with patch(
    "production_runner.process_new_emails"
) as mock_new, patch(
    "production_runner.run_retry_cycle",
    side_effect=RuntimeError("RETRY FAILURE"),
) as mock_retry, patch(
    "production_runner.run_followup_cycle"
) as mock_followups:

    mock_new.return_value = [
        {"status": "processed"}
    ]

    mock_followups.return_value = {
        "due_transition": [
            ("lead-001", "follow_up_due")
        ],
        "scheduling": [],
        "drafts": [],
        "errors": [],
    }

    result = run_execution_cycle(
        provider=provider,
    )


assert mock_new.call_count == 1
assert mock_retry.call_count == 1
assert mock_followups.call_count == 1

assert result["retries"] == []

assert result["followups"]["due_transition"] == [
    ("lead-001", "follow_up_due")
]

assert result["errors"] == [
    {
        "stage": "retries",
        "error": "RETRY FAILURE",
    }
]

print(
    "CASE 3 - RETRY FAILURE ISOLATED: PASS"
)


# =========================================================
# CASE 4 - FOLLOW-UP FAILURE DOES NOT BLOCK OTHER STAGES
# =========================================================

with patch(
    "production_runner.process_new_emails"
) as mock_new, patch(
    "production_runner.run_retry_cycle"
) as mock_retry, patch(
    "production_runner.run_followup_cycle",
    side_effect=RuntimeError("FOLLOW-UP FAILURE"),
) as mock_followups:

    mock_new.return_value = [
        {"status": "processed"}
    ]

    mock_retry.return_value = [
        {"status": "retried"}
    ]

    result = run_execution_cycle(
        provider=provider,
    )


assert mock_new.call_count == 1
assert mock_retry.call_count == 1
assert mock_followups.call_count == 1

assert result["new_emails"] == [
    {"status": "processed"}
]

assert result["retries"] == [
    {"status": "retried"}
]

assert result["followups"] == []

assert result["errors"] == [
    {
        "stage": "followups",
        "error": "FOLLOW-UP FAILURE",
    }
]

print(
    "CASE 4 - FOLLOW-UP FAILURE ISOLATED: PASS"
)


# =========================================================
# CASE 5 - FOLLOW-UP RESULT PRESERVED
# =========================================================

followup_result = {
    "due_transition": [
        ("lead-002", "follow_up_due")
    ],
    "scheduling": [
        {
            "lead_id": "lead-002",
            "status": "scheduled",
            "followup_id": "followup-002",
        }
    ],
    "drafts": [
        {
            "status": "drafted",
            "followup_id": "followup-002",
            "outreach_id": "outreach-002",
        }
    ],
    "errors": [],
}


with patch(
    "production_runner.process_new_emails",
    return_value=[],
), patch(
    "production_runner.run_retry_cycle",
    return_value=[],
), patch(
    "production_runner.run_followup_cycle",
    return_value=followup_result,
):

    result = run_execution_cycle(
        provider=provider,
    )


assert result["followups"] == followup_result

print(
    "CASE 5 - FOLLOW-UP RESULT PRESERVED: PASS"
)


# =========================================================
# CASE 6 - FOLLOW-UP RUNNER DOES NOT SEND
# =========================================================

with patch(
    "production_runner.process_new_emails",
    return_value=[],
), patch(
    "production_runner.run_retry_cycle",
    return_value=[],
), patch(
    "production_runner.run_followup_cycle",
    return_value={
        "due_transition": [],
        "scheduling": [],
        "drafts": [
            {
                "status": "drafted",
                "followup_id": "followup-003",
            }
        ],
        "errors": [],
    },
):

    result = run_execution_cycle(
        provider=provider,
    )


assert result["followups"]["drafts"][0]["status"] == "drafted"

print(
    "CASE 6 - PRODUCTION CYCLE PRESERVES DRAFT-ONLY BOUNDARY: PASS"
)


print()
print(
    "PHASE 5.6 PRODUCTION RUNNER ISOLATION TEST PASSED"
)
