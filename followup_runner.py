"""
Follow-Up Production Runner.

Phase 5.6:
    - Transition overdue sent leads to follow_up_due.
    - Detect eligible follow-up candidates.
    - Schedule follow-ups.
    - Create drafted follow-up outreach.
    - Never send email.
    - Never bypass human approval.
"""

from followup_due_transition import (
    DEFAULT_FOLLOWUP_WAIT_DAYS,
    transition_due_leads,
)
from followup_orchestrator import schedule_followup_candidates
from followup_outreach_service import create_followup_outreach


DEFAULT_BATCH_LIMIT = 10


def run_followup_cycle(
    limit: int = DEFAULT_BATCH_LIMIT,
    wait_days: int = DEFAULT_FOLLOWUP_WAIT_DAYS,
):
    """
    Execute one complete follow-up processing cycle.

    Flow:

        due transition
            ↓
        candidate detection
            ↓
        eligibility re-check
            ↓
        scheduling
            ↓
        draft outreach

    Email sending and human approval remain outside
    this runner.
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    if wait_days < 1:
        raise ValueError("wait_days must be >= 1.")

    results = {
        "due_transition": [],
        "scheduling": [],
        "drafts": [],
        "errors": [],
    }

    # =========================================================
    # 1. TRANSITION DUE LEADS
    # =========================================================

    try:
        results["due_transition"] = transition_due_leads(
            wait_days=wait_days,
        )
    except Exception as error:
        results["errors"].append(
            {
                "stage": "due_transition",
                "error": str(error),
            }
        )

    # =========================================================
    # 2. SCHEDULE FOLLOW-UPS
    # =========================================================

    try:
        results["scheduling"] = schedule_followup_candidates(
            limit=limit,
        )
    except Exception as error:
        results["errors"].append(
            {
                "stage": "scheduling",
                "error": str(error),
            }
        )

    # =========================================================
    # 3. CREATE OUTREACH DRAFTS
    # =========================================================

    for result in results["scheduling"]:

        if result.get("status") != "scheduled":
            continue

        followup_id = result.get("followup_id")

        if not followup_id:
            results["errors"].append(
                {
                    "stage": "drafting",
                    "error": (
                        "Scheduled follow-up result "
                        "did not contain followup_id."
                    ),
                }
            )
            continue

        try:
            draft_result = create_followup_outreach(
                followup_id=followup_id,
            )

            results["drafts"].append(
                draft_result
            )

        except Exception as error:
            results["errors"].append(
                {
                    "stage": "drafting",
                    "followup_id": followup_id,
                    "error": str(error),
                }
            )

    return results
