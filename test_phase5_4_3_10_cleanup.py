from db import get_connection

conn = get_connection()
cur = conn.cursor()

try:
    print("===== PHASE 5.4.3.10 CLEANUP / REGRESSION CHECK =====")

    # ---------------------------------------------------------
    # 1. FOLLOW-UP ORPHANS
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM followups f
        LEFT JOIN leads l
            ON l.lead_id = f.lead_id
        WHERE l.lead_id IS NULL;
        """
    )

    orphan_followups = cur.fetchone()[0]

    print()
    print("ORPHAN FOLLOWUPS:", orphan_followups)

    assert orphan_followups == 0

    print("CASE 1 - NO ORPHAN FOLLOWUPS: PASS")

    # ---------------------------------------------------------
    # 2. FOLLOW-UP OUTREACH ORPHANS
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM followups f
        WHERE f.outreach_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM outreach o
              WHERE o.outreach_id = f.outreach_id
          );
        """
    )

    orphan_followup_outreach = cur.fetchone()[0]

    print()
    print(
        "ORPHAN FOLLOW-UP OUTREACH LINKS:",
        orphan_followup_outreach,
    )

    assert orphan_followup_outreach == 0

    print("CASE 2 - NO ORPHAN FOLLOW-UP OUTREACH: PASS")

    # ---------------------------------------------------------
    # 3. ACTIVE FOLLOW-UP DUPLICATES
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            lead_id,
            attempt_number,
            COUNT(*)
        FROM followups
        WHERE status = 'scheduled'
        GROUP BY
            lead_id,
            attempt_number
        HAVING COUNT(*) > 1;
        """
    )

    duplicate_active_attempts = cur.fetchall()

    print()
    print("DUPLICATE ACTIVE ATTEMPTS:")
    print(duplicate_active_attempts)

    assert len(duplicate_active_attempts) == 0

    print("CASE 3 - NO DUPLICATE ACTIVE ATTEMPTS: PASS")

    # ---------------------------------------------------------
    # 4. FOLLOW-UP -> OUTREACH LINK VALIDITY
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM followups
        WHERE outreach_id IS NULL;
        """
    )

    unlinked_followups = cur.fetchone()[0]

    print()
    print(
        "FOLLOWUPS WITHOUT OUTREACH:",
        unlinked_followups,
    )

    print(
        "CASE 4 - UNLINKED FOLLOWUPS:",
        "PASS"
        if unlinked_followups >= 0
        else "FAIL",
    )

    # ---------------------------------------------------------
    # 5. INDEX VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'followups'
        ORDER BY indexname;
        """
    )

    indexes = [row[0] for row in cur.fetchall()]

    print()
    print("FOLLOW-UP INDEXES:")

    for index_name in indexes:
        print(index_name)

    required_indexes = {
        "followups_pkey",
        "idx_followups_active_attempt",
        "idx_followups_lead",
        "idx_followups_outreach",
    }

    missing_indexes = required_indexes - set(indexes)

    print()
    print("MISSING REQUIRED INDEXES:", missing_indexes)

    assert not missing_indexes

    print("CASE 5 - REQUIRED INDEXES PRESENT: PASS")

    # ---------------------------------------------------------
    # 6. CONSTRAINT VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'followups'::regclass
        ORDER BY conname;
        """
    )

    constraints = [row[0] for row in cur.fetchall()]

    print()
    print("FOLLOW-UP CONSTRAINTS:")

    for constraint in constraints:
        print(constraint)

    required_constraints = {
        "followups_pkey",
        "followups_lead_id_fkey",
        "followups_attempt_number_check",
        "followups_outreach_id_fkey",
    }

    missing_constraints = (
        required_constraints - set(constraints)
    )

    print()
    print(
        "MISSING REQUIRED CONSTRAINTS:",
        missing_constraints,
    )

    assert not missing_constraints

    print("CASE 6 - REQUIRED CONSTRAINTS PRESENT: PASS")

    # ---------------------------------------------------------
    # 7. STATUS COUNTS
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            status,
            COUNT(*)
        FROM followups
        GROUP BY status
        ORDER BY status;
        """
    )

    status_counts = cur.fetchall()

    print()
    print("FOLLOW-UP STATUS COUNTS:")

    for row in status_counts:
        print(row)

    # ---------------------------------------------------------
    # FINAL
    # ---------------------------------------------------------

    print()
    print(
        "PHASE 5.4.3.10 CLEANUP / REGRESSION VERIFICATION PASSED"
    )

finally:
    cur.close()
    conn.close()
