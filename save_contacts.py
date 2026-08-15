import sys

from contact_discovery import discover_contacts
from db import get_connection


def normalize_company_name(name: str) -> str:
    return " ".join(name.lower().split())


def get_or_create_brand(cur, company: str, domain: str) -> str:
    normalized_name = normalize_company_name(company)

    cur.execute("""
        SELECT brand_id
        FROM brands
        WHERE normalized_name = %s
        LIMIT 1;
    """, (normalized_name,))

    row = cur.fetchone()

    if row:
        print(f"Using existing brand: {company}")
        return row[0]

    cur.execute("""
        INSERT INTO brands
            (name, normalized_name, website, discovery_source)
        VALUES
            (%s, %s, %s, %s)
        RETURNING brand_id;
    """, (
        company,
        normalized_name,
        f"https://{domain}",
        "hunter_domain_search",
    ))

    brand_id = cur.fetchone()[0]

    print(f"Created new brand: {company}")
    return brand_id


def save_contacts(domain: str, company: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        brand_id = get_or_create_brand(cur, company, domain)

        contacts = discover_contacts(
            domain,
            company=company
        )

        print(f"Hunter returned {len(contacts)} qualifying contacts.")

        inserted = 0
        updated = 0
        skipped = 0

        for contact in contacts:
            email = contact.get("email")

            if not email:
                skipped += 1
                print(
                    f"Skipped: {contact.get('contact_name')} | "
                    "no email returned"
                )
                continue

            confidence = (
                "verified"
                if contact.get("email_status") == "valid"
                else "inferred"
            )

            cur.execute("""
                INSERT INTO contacts
                    (
                        brand_id,
                        name,
                        role,
                        email,
                        linkedin_url,
                        confidence
                    )
                VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::contact_confidence
                    )

                ON CONFLICT (email) WHERE email IS NOT NULL
                DO UPDATE SET
                    brand_id = EXCLUDED.brand_id,
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    linkedin_url = EXCLUDED.linkedin_url,
                    confidence = EXCLUDED.confidence

                RETURNING
                    contact_id,
                    (xmax = 0) AS was_inserted;
            """, (
                brand_id,
                contact.get("contact_name"),
                contact.get("position"),
                email,
                contact.get("linkedin_url"),
                confidence,
            ))

            contact_id, was_inserted = cur.fetchone()

            if was_inserted:
                inserted += 1
                action = "Inserted"
            else:
                updated += 1
                action = "Updated"

            print(
                f"{action}: "
                f"{contact.get('contact_name')} | "
                f"{email} | "
                f"{confidence} | "
                f"id={contact_id}"
            )

        conn.commit()

        print("\nSUCCESS")
        print(f"Inserted: {inserted}")
        print(f"Updated: {updated}")
        print(f"Skipped: {skipped}")
        print(f"Total processed: {inserted + updated}")

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python save_contacts.py "
            "<domain> <company_name>"
        )
        print(
            'Example: python save_contacts.py '
            'stripe.com "Stripe"'
        )
        sys.exit(1)

    domain = sys.argv[1].strip().lower()
    company = sys.argv[2].strip()

    save_contacts(domain, company)
