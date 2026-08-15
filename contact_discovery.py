"""
Contact Discovery Agent — Hunter.io wrapper
Talks to Hunter's Domain Search endpoint, filters to decision-makers,
and normalizes results to the FRD contact schema.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

HUNTER_BASE_URL = "https://api.hunter.io/v2/domain-search"

DECISION_MAKER_SENIORITY = {"executive", "senior"}
MIN_EMAIL_CONFIDENCE = 75

PAGE_SIZE = 10
DEFAULT_MAX_RESULTS = 30


def _call_hunter(domain: str, api_key: str, limit: int = 10, offset: int = 0) -> dict:
    headers = {"X-API-KEY": api_key}
    params = {"domain": domain, "limit": limit, "offset": offset}
    response = requests.get(HUNTER_BASE_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _fetch_raw_contacts(domain: str, api_key: str, max_results: int = DEFAULT_MAX_RESULTS) -> list:
    """
    Fetches raw Hunter contacts across multiple pages, up to max_results.
    On a Free Hunter plan, results are capped at 10 total and requesting
    further pages (limit + offset > 10) returns a 400 error — this is an
    account limit, not a bug. We treat that specific case as "no more
    pages available" and stop cleanly instead of crashing, so the same
    code keeps working as-is if the plan is ever upgraded.
    """
    collected = []
    offset = 0

    while len(collected) < max_results:
        try:
            raw = _call_hunter(domain, api_key, limit=PAGE_SIZE, offset=offset)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                # Likely a plan-level pagination limit (e.g. Free plan caps
                # at 10 total results). Stop here rather than failing.
                break
            raise  # any other error (401, 403, 5xx) should still surface

        page_contacts = raw.get("data", {}).get("emails", [])
        if not page_contacts:
            break

        collected.extend(page_contacts)
        offset += PAGE_SIZE

        total_available = raw.get("meta", {}).get("results")
        if total_available is not None and offset >= total_available:
            break

    return collected[:max_results]


def _is_decision_maker(contact: dict) -> bool:
    if contact.get("decision_maker") is True:
        return True
    seniority = (contact.get("seniority") or "").lower()
    return seniority in DECISION_MAKER_SENIORITY


def _has_confident_email(contact: dict) -> bool:
    confidence = contact.get("confidence")
    return confidence is not None and confidence >= MIN_EMAIL_CONFIDENCE


def _normalize(contact: dict, company: str, domain: str) -> dict:
    first = contact.get("first_name") or ""
    last = contact.get("last_name") or ""
    full_name = (first + " " + last).strip() or None
    return {
        "company": company,
        "domain": domain,
        "contact_name": full_name,
        "email": contact.get("value"),
        "position": contact.get("position"),
        "department": contact.get("department"),
        "seniority": contact.get("seniority"),
        "decision_maker": bool(contact.get("decision_maker")),
        "linkedin_url": contact.get("linkedin"),
        "email_confidence": contact.get("confidence"),
        "email_status": contact.get("verification", {}).get("status") if contact.get("verification") else None,
    }


def discover_contacts(domain: str, api_key=None, company=None, max_results: int = DEFAULT_MAX_RESULTS) -> list:
    key = api_key or os.environ.get("HUNTER_API_KEY")
    if not key:
        raise ValueError("No Hunter API key provided (pass api_key= or set HUNTER_API_KEY env var)")

    raw_contacts = _fetch_raw_contacts(domain, key, max_results=max_results)
    company_name = company or domain

    filtered = [
        _normalize(c, company_name, domain)
        for c in raw_contacts
        if _is_decision_maker(c) and _has_confident_email(c)
    ]
    return filtered


if __name__ == "__main__":
    test_domains = ["stripe.com"]
    for d in test_domains:
        print(f"\n--- {d} ---")
        try:
            results = discover_contacts(d)
            print(f"Found {len(results)} qualifying contacts")
            if not results:
                print("No decision-maker contacts met the confidence threshold.")
            for r in results:
                print(r)
        except Exception as e:
            print(f"Error: {e}")