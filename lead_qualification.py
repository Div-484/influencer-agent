from db import get_connection
import json
import math
import sys


def load_scoring_weights(cur):
    """
    Load scoring weights from the database.
    """

    cur.execute("""
        SELECT signal_name, weight
        FROM scoring_config
        ORDER BY signal_name;
    """)

    weights = {
        signal_name: float(weight)
        for signal_name, weight in cur.fetchall()
    }

    required_signals = {
        "senior_decision_makers",
        "role_relevance",
        "verified_email",
        "linkedin_coverage",
        "contact_depth",
    }

    missing_signals = required_signals - weights.keys()

    if missing_signals:
        raise ValueError(
            f"Missing scoring configuration: "
            f"{sorted(missing_signals)}"
        )

    return weights


def score_lead(brand_id):
    """
    Calculate a 0-100 lead score for a brand.

    Scoring signals:
    - Senior decision makers
    - Role relevance
    - Verified email coverage
    - LinkedIn coverage
    - Contact depth

    Uses diminishing returns for count-based signals.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        weights = load_scoring_weights(cur)

        cur.execute("""
            SELECT
                name,
                role,
                email,
                linkedin_url,
                confidence
            FROM contacts
            WHERE brand_id = %s
        """, (brand_id,))

        contacts = cur.fetchall()

        if not contacts:
            raise ValueError(
                "No contacts found for this brand."
            )

        total_contacts = len(contacts)

        senior_roles = (
            "chief",
            "ceo",
            "cmo",
            "cto",
            "coo",
            "cfo",
            "head",
            "vice president",
            "vp",
            "director",
        )

        relevant_roles = (
            "engineering",
            "product",
            "sales",
            "commerce",
            "marketing",
            "technology",
            "account",
        )

        senior_count = 0
        relevant_count = 0
        verified_count = 0
        linkedin_count = 0

        for name, role, email, linkedin, confidence in contacts:
            role_text = (role or "").lower()

            if any(
                signal in role_text
                for signal in senior_roles
            ):
                senior_count += 1

            if any(
                signal in role_text
                for signal in relevant_roles
            ):
                relevant_count += 1

            if confidence == "verified":
                verified_count += 1

            if linkedin:
                linkedin_count += 1

        # ---------------------------------------------
        # Diminishing-return scoring
        # ---------------------------------------------

        senior_points = (
            weights["senior_decision_makers"]
            * (1 - math.exp(-senior_count / 3))
        )

        relevance_points = (
            weights["role_relevance"]
            * (1 - math.exp(-relevant_count / 4))
        )

        verified_points = (
            weights["verified_email"]
            * (verified_count / total_contacts)
        )

        linkedin_points = (
            weights["linkedin_coverage"]
            * (linkedin_count / total_contacts)
        )

        depth_points = (
            weights["contact_depth"]
            * (1 - math.exp(-total_contacts / 5))
        )

        contributions = {
            "senior_decision_makers": round(
                senior_points,
                2,
            ),
            "role_relevance": round(
                relevance_points,
                2,
            ),
            "verified_email": round(
                verified_points,
                2,
            ),
            "linkedin_coverage": round(
                linkedin_points,
                2,
            ),
            "contact_depth": round(
                depth_points,
                2,
            ),
        }

        score = round(
            sum(contributions.values())
        )

        score = min(
            max(score, 0),
            100,
        )

        rationale = {
            "score": score,
            "weights": weights,
            "contacts": {
                "total": total_contacts,
                "senior_decision_makers": senior_count,
                "role_relevance": relevant_count,
                "verified_emails": verified_count,
                "linkedin_profiles": linkedin_count,
            },
            "contributions": contributions,
        }

        return score, rationale

    finally:
        cur.close()
        conn.close()


def save_lead_score(brand_id, score, rationale):
    """
    Persist the calculated lead score and scoring rationale.

    Does not modify the lead workflow status.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE leads
            SET
                score = %s,
                scoring_rationale = %s::jsonb,
                scored_at = NOW(),
                updated_at = NOW()
            WHERE brand_id = %s
            RETURNING
                lead_id,
                score,
                status,
                scored_at;
        """, (
            score,
            json.dumps(rationale),
            brand_id,
        ))

        row = cur.fetchone()

        if not row:
            raise ValueError(
                f"No lead found for brand_id: {brand_id}"
            )

        conn.commit()

        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def get_qualification_status(score, current_status):
    """
    Determine qualification result from lead score.

    This function does not modify the database.

    Scores:
    - 80-100: qualified
    - 60-79: watch
    - 0-59: rejected

    Workflow statuses are protected from automatic
    score-based status changes once outreach has progressed.
    """

    protected_statuses = {
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
    }

    if current_status in protected_statuses:
        return current_status

    if score >= 80:
        return "qualified"

    if score >= 60:
        return "watch"

    return "rejected"


def apply_qualification_status(brand_id, score, dry_run=False):
    """
    Apply the score-based qualification status to a lead.

    Protected workflow statuses are preserved by
    get_qualification_status().
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                lead_id,
                status
            FROM leads
            WHERE brand_id = %s
            FOR UPDATE;
        """, (brand_id,))

        row = cur.fetchone()

        if not row:
            raise ValueError(
                f"No lead found for brand_id: {brand_id}"
            )

        lead_id, current_status = row

        new_status = get_qualification_status(
            score,
            current_status,
        )

        if new_status == current_status:
            conn.commit()
            return {
                "lead_id": lead_id,
                "old_status": current_status,
                "new_status": current_status,
                "changed": False,
                "dry_run": dry_run,
            }

        cur.execute("""
            UPDATE leads
            SET
                status = %s,
                updated_at = NOW()
            WHERE lead_id = %s
            RETURNING
                lead_id,
                status,
                updated_at;
        """, (
            new_status,
            lead_id,
        ))

        updated_row = cur.fetchone()

        if not updated_row:
            raise ValueError(
                f"Failed to update lead status: {lead_id}"
            )

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

        return {
            "lead_id": updated_row[0],
            "old_status": current_status,
            "new_status": updated_row[1],
            "changed": True,
            "dry_run": dry_run,
            "updated_at": updated_row[2],
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def main():
    """
    Command-line entry point.
    """

    if len(sys.argv) != 2:
        print(
            "Usage: "
            "python lead_qualification.py <brand_id>"
        )
        sys.exit(1)

    brand_id = sys.argv[1]

    try:
        score, rationale = score_lead(
            brand_id
        )

        print(
            f"Calculated lead score: "
            f"{score}/100"
        )

        result = save_lead_score(
            brand_id,
            score,
            rationale,
        )

        print(
            "Lead score saved successfully."
        )

        print(
            f"lead_id={result[0]}"
        )

        print(
            f"score={result[1]}"
        )

        print(
            f"status={result[2]}"
        )

        print(
            f"scored_at={result[3]}"
        )

        print(
            "\nScoring rationale:"
        )

        print(
            json.dumps(
                rationale,
                indent=2,
            )
        )

    except Exception as error:
        print(
            f"Lead qualification failed: "
            f"{error}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
