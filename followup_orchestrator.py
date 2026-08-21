"""
Follow-up Scheduling Orchestrator.

Phase 5.4.2:
    - Retrieve follow-up candidates.
    - Re-check database-backed eligibility.
    - Schedule eligible follow-ups.
    - Skip candidates that become ineligible.
    - Keep candidate retrieval, eligibility, and scheduling separate.
"""

from datetime import datetime, timedelta, timezone

from followup_candidate_repository import get_followup_candidates
from followup_eligibility_repository import get_followup_eligibility
from followup_scheduler import (
    DEFAULT_FOLLOWUP_DELAY_DAYS,
    MAX_FOLLOWUP_ATTEMPTS,
    schedule_followup,
)


def schedule_followup_candidates(
    limit: int = 10,
    delay_days: int = DEFAULT_FOLLOWUP_DELAY_DAYS,
    attempt_number: int = 1,
    now: datetime | None = None,
):
    """
    Schedule follow-ups for currently eligible candidates.

    The candidate repository provides possible candidates.
    Eligibility is re-checked immediately before scheduling.
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    if delay_days < 0:
        raise ValueError(
            "delay_days must be >= 0."
        )

    if attempt_number < 1:
        raise ValueError(
            "attempt_number must be >= 1."
        )

    if attempt_number > MAX_FOLLOWUP_ATTEMPTS:
        raise ValueError(
            "attempt_number exceeds maximum follow-up attempts."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware."
        )

    candidates = get_followup_candidates(
        limit=limit,
    )

    results = []

    for candidate in candidates:
        (
            lead_id,
            brand_id,
            lead_status,
            outreach_id,
            contact_id,
            message_text,
            last_sent_at,
        ) = candidate

        eligibility = get_followup_eligibility(
            lead_id=str(lead_id),
            attempt_number=attempt_number,
        )

        if not eligibility.get("eligible"):
            results.append(
                {
                    "lead_id": str(lead_id),
                    "status": "skipped",
                    "reason": eligibility.get(
                        "reason",
                        "not_eligible",
                    ),
                }
            )
            continue

        scheduled_for = (
            now
            + timedelta(days=delay_days)
        )

        try:
            followup = schedule_followup(
                lead_id=str(lead_id),
                scheduled_for=scheduled_for,
                attempt_number=attempt_number,
            )

            results.append(
                {
                    "lead_id": str(lead_id),
                    "status": "scheduled",
                    "followup_id": str(
                        followup[0]
                    ),
                    "attempt_number": followup[3],
                    "scheduled_for": followup[2],
                }
            )

        except RuntimeError as error:
            if "already scheduled" in str(error).lower():
                results.append(
                    {
                        "lead_id": str(lead_id),
                        "status": "already_scheduled",
                        "reason": str(error),
                    }
                )
            else:
                results.append(
                    {
                        "lead_id": str(lead_id),
                        "status": "failed",
                        "error": str(error),
                    }
                )

        except Exception as error:
            results.append(
                {
                    "lead_id": str(lead_id),
                    "status": "failed",
                    "error": str(error),
                }
            )

    return results
