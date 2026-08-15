"""
Outreach Agent — drafts outreach messages for saved contacts.

IMPORTANT: this agent only DRAFTS messages and saves them into the
outreach table with status 'drafted'. It never sends anything. Per
the FRD (FR-005.03/.04), every draft must go through human approval
before it can be marked approved/sent.

Usage:
    python outreach_agent.py <domain> "<company_name>"

Example:
    python outreach_agent.py stripe.com "Stripe"
"""

import os
import sys
from dotenv import load_dotenv
from db import get_connection

load_dotenv()

# --- Sender config, editable via .env ---
INFLUENCER_NAME = os.environ.get("INFLUENCER_NAME", "[Your Name]")
NICHE = os.environ.get("NICHE", "")
PORTFOLIO_URL = os.environ.get("PORTFOLIO_URL", "")


def normalize_company_name(name: str) -> str:
    return " ".join(name.lower().split())


def build_message(contact_name: str, brand_name: str) -> str:
    """Builds a templated outreach message. contact_name may be None."""
    greeting_name = contact_name.split(" ")[0] if contact_name else "there"

    niche_line = f" I focus on {NICHE} content." if NICHE else ""
    portfolio_line = f"\n\nHere's a link to my work: {PORTFOLIO_URL}" if PORTFOLIO_URL else ""

    message = (
        f"Hi {greeting_name},\n\n"
        f"My name is {INFLUENCER_NAME}, and I'm reaching out because I'd love to explore "
        f"a possible collaboration with {brand_name}.{niche_line} "
        f"I think there could be a great fit between what {brand_name} does and my audience."
        f"{portfolio_line}\n\n"
        f"Would you be open to a quick chat about this?\n\n"
        f"Best,\n{INFLUENCER_NAME}"
    )
    return message


def get_brand(cur, company: str):
    normalized_name = normalize_company_name(company)
    cur.execute(
        "SELECT brand_id, name FROM brands WHERE normalized_name = %s LIMIT 1;",
        (normalized_name,),
    )
    return cur.fetchone()  # (brand_id, name) or None


def get_or_create_lead(cur, brand_id: str) -> str:
    """Returns an existing lead_id for this brand, or creates one with
    status 'contact_found' since we're drafting outreach for a known contact."""
    cur.execute(
        "SELECT lead_id FROM leads WHERE brand_id = %s ORDER BY created_at LIMIT 1;",
        (brand_id,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO leads (brand_id, status)
        VALUES (%s, 'contact_found')
        RETURNING lead_id;
        """,
        (brand_id,),
    )
    return cur.fetchone()[0]


def get_contacts_for_brand(cur, brand_id: str):
    cur.execute(
        "SELECT contact_id, name, email FROM contacts WHERE brand_id = %s;",
        (brand_id,),
    )
    return cur.fetchall()  # list of (contact_id, name, email)


def has_existing_draft(cur, contact_id: str) -> bool:
    """Avoid drafting duplicate outreach for a contact that already has
    an active (non-rejected) draft."""
    cur.execute(
        """
        SELECT 1 FROM outreach
        WHERE contact_id = %s AND status != 'rejected'
        LIMIT 1;
        """,
        (contact_id,),
    )
    return cur.fetchone() is not None


def draft_outreach_for_brand(domain: str, company: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        brand = get_brand(cur, company)
        if not brand:
            print(f"No brand found for '{company}'. Run save_contacts.py first.")
            return

        brand_id, brand_name = brand
        lead_id = get_or_create_lead(cur, brand_id)

        contacts = get_contacts_for_brand(cur, brand_id)
        if not contacts:
            print(f"No contacts saved yet for {brand_name}. Run save_contacts.py first.")
            return

        drafted = 0
        skipped = 0

        for contact_id, contact_name, email in contacts:
            if has_existing_draft(cur, contact_id):
                skipped += 1
                print(f"Skipped (already drafted): {contact_name} | {email}")
                continue

            message = build_message(contact_name, brand_name)

            cur.execute(
                """
                INSERT INTO outreach (lead_id, contact_id, channel, message_text, status)
                VALUES (%s, %s, 'email', %s, 'drafted')
                RETURNING outreach_id;
                """,
                (lead_id, contact_id, message),
            )
            outreach_id = cur.fetchone()[0]
            drafted += 1
            print(f"Drafted: {contact_name} | {email} | outreach_id={outreach_id}")

        # Update lead status now that outreach drafts exist
        if drafted > 0:
            cur.execute(
                "UPDATE leads SET status = 'message_drafted', updated_at = now() WHERE lead_id = %s;",
                (lead_id,),
            )

        conn.commit()

        print("\nSUCCESS")
        print(f"Drafted: {drafted}")
        print(f"Skipped: {skipped}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: python outreach_agent.py <domain> "<company_name>"')
        print('Example: python outreach_agent.py stripe.com "Stripe"')
        sys.exit(1)

    domain_arg = sys.argv[1].strip().lower()
    company_arg = sys.argv[2].strip()

    draft_outreach_for_brand(domain_arg, company_arg)