"""
Approval Agent — human-in-the-loop review for drafted outreach messages.

Shows all 'drafted' outreach messages as a numbered list. You pick one
by number to read the full message, then approve or reject it.

On a decision, this script updates BOTH:
  - outreach.status / outreach.approved_by
  - inserts a row into the approvals table (decision, reviewer, decided_at)
This closes the audit-trail gap that manual Supabase edits left open.

Usage:
    python approval_agent.py
"""

import os
from dotenv import load_dotenv
from db import get_connection

load_dotenv()

DEFAULT_REVIEWER = os.environ.get("INFLUENCER_NAME", "")


def get_drafted_outreach(cur):
    cur.execute(
        """
        SELECT o.outreach_id, o.message_text, c.name, c.email, b.name
        FROM outreach o
        JOIN contacts c ON c.contact_id = o.contact_id
        JOIN leads l ON l.lead_id = o.lead_id
        JOIN brands b ON b.brand_id = l.brand_id
        WHERE o.status = 'drafted'
        ORDER BY o.created_at;
        """
    )
    return cur.fetchall()  # (outreach_id, message_text, contact_name, email, brand_name)


def record_decision(cur, outreach_id: str, decision: str, reviewer: str):
    """decision must be 'approved' or 'rejected'."""
    cur.execute(
        """
        UPDATE outreach
        SET status = %s::outreach_status, approved_by = %s
        WHERE outreach_id = %s;
        """,
        (decision, reviewer, outreach_id),
    )
    cur.execute(
        """
        INSERT INTO approvals (outreach_id, decision, reviewer)
        VALUES (%s, %s::approval_decision, %s);
        """,
        (outreach_id, decision, reviewer),
    )


def preview(text: str, length: int = 60) -> str:
    flat = text.replace("\n", " ")
    return flat[:length] + ("..." if len(flat) > length else "")


def print_list(rows):
    print(f"\n{len(rows)} drafted message(s) waiting for review:\n")
    for i, (outreach_id, message_text, contact_name, email, brand_name) in enumerate(rows, start=1):
        print(f"[{i}] {contact_name} ({email}) — {brand_name}")
        print(f"    \"{preview(message_text)}\"")
    print()


def run():
    conn = get_connection()
    cur = conn.cursor()

    try:
        while True:
            rows = get_drafted_outreach(cur)
            if not rows:
                print("No drafted messages waiting for review.")
                return

            print_list(rows)
            choice = input(
                "Enter a number to review (or 'q' to quit): "
            ).strip().lower()

            if choice == "q":
                print("Done reviewing for now.")
                return

            if not choice.isdigit() or not (1 <= int(choice) <= len(rows)):
                print("Invalid choice, try again.\n")
                continue

            idx = int(choice) - 1
            outreach_id, message_text, contact_name, email, brand_name = rows[idx]

            print(f"\n--- Full message: {contact_name} ({email}) — {brand_name} ---")
            print(message_text)
            print("---\n")

            decision = input("Approve, reject, or skip? (a/r/s): ").strip().lower()

            if decision == "s":
                continue

            if decision not in ("a", "r"):
                print("Not a valid choice, skipping.\n")
                continue

            reviewer = input(
                f"Your name [{DEFAULT_REVIEWER or 'required'}]: "
            ).strip() or DEFAULT_REVIEWER

            if not reviewer:
                print("A reviewer name is required, skipping this decision.\n")
                continue

            decision_word = "approved" if decision == "a" else "rejected"
            record_decision(cur, outreach_id, decision_word, reviewer)
            conn.commit()
            print(f"Marked {decision_word} by {reviewer}.\n")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
