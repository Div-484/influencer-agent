from db import get_connection
import json
import math


def load_scoring_weights(cur):
    cur.execute("""
        SELECT signal_name, weight
        FROM scoring_config
        ORDER BY signal_name;
    """)

    weights = {
        signal_name: float(weight)
        for signal_name, weight in cur.fetchall()
    }

    required = {
        "senior_decision_makers",
        "role_relevance",
        "verified_email",
        "linkedin_coverage",
        "contact_depth",
    }

    missing = required - weights.keys()

    if missing:
        raise ValueError(
            f"Missing scoring configuration: {sorted(missing)}"
        )

    return weights


def score_lead(brand_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        weights = load_scoring_weights(cur)

        cur.execute("""
            SELECT name, role, email, linkedin_url, confidence
            FROM contacts
            WHERE brand_id = %s
        """, (brand_id,))

        contacts = cur.fetchall()

        if not contacts:
            raise ValueError("No contacts found for this brand.")

        total_contacts = len(contacts)

        senior_roles = (
            "chief", "ceo", "cmo", "cto", "coo", "cfo",
            "head", "vice president", "vp", "director"
        )

        relevant_roles = (
            "engineering", "product", "sales", "commerce",
            "marketing", "technology", "account"
        )

        senior_count = 0
        relevant_count = 0
        verified_count = 0
        linkedin_count = 0

        for name, role, email, linkedin, confidence in contacts:
            role_text = (role or "").lower()

            if any(x in role_text for x in senior_roles):
                senior_count += 1

            if any(x in role_text for x in relevant_roles):
                relevant_count += 1

            if confidence == "verified":
                verified_count += 1

            if linkedin:
                linkedin_count += 1

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
            "senior_decision_makers": round(senior_points, 2),
            "role_relevance": round(relevance_points, 2),
            "verified_email": round(verified_points, 2),
            "linkedin_coverage": round(linkedin_points, 2),
            "contact_depth": round(depth_points, 2),
        }

        score = round(sum(contributions.values()))
        score = min(max(score, 0), 100)

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


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python lead_qualification.py <brand_id>")
        sys.exit(1)

    brand_id = sys.argv[1]

    score, rationale = score_lead(brand_id)

    print(f"Lead score: {score}/100")
    print("Scoring rationale:")
    print(json.dumps(rationale, indent=2))
def save_lead_score(brand_id, score, rationale):
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
            RETURNING lead_id, score, status, scored_at;
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
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python lead_qualification.py <brand_id>")
        sys.exit(1)

    brand_id = sys.argv[1]

    score, rationale = score_lead(brand_id)

    print(f"Calculated lead score: {score}/100")

    result = save_lead_score(
        brand_id,
        score,
        rationale
    )

    print("Lead score saved successfully.")
    print(f"lead_id={result[0]}")
    print(f"score={result[1]}")
    print(f"status={result[2]}")
    print(f"scored_at={result[3]}")

    print("\nScoring rationale:")
    print(json.dumps(rationale, indent=2))
