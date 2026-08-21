from db import get_connection

conn = get_connection()
cur = conn.cursor()

try:
    print("===== BEFORE MIGRATION =====")

    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'followups'
        ORDER BY ordinal_position;
    """)

    before = [
        row[0]
        for row in cur.fetchall()
    ]

    print(before)

    if "outreach_id" not in before:
        cur.execute("""
            ALTER TABLE followups
            ADD COLUMN outreach_id UUID;
        """)

        cur.execute("""
            ALTER TABLE followups
            ADD CONSTRAINT followups_outreach_id_fkey
            FOREIGN KEY (outreach_id)
            REFERENCES outreach(outreach_id);
        """)

        cur.execute("""
            CREATE INDEX idx_followups_outreach
            ON followups(outreach_id);
        """)

        conn.commit()

        print()
        print("OUTREACH_ID COLUMN: CREATED")
        print("FOREIGN KEY: CREATED")
        print("INDEX: CREATED")

    else:
        print()
        print("OUTREACH_ID COLUMN: ALREADY EXISTS")

    print()
    print("===== AFTER MIGRATION =====")

    cur.execute("""
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'followups'
        ORDER BY ordinal_position;
    """)

    for row in cur.fetchall():
        print(row)

    cur.execute("""
        SELECT
            conname,
            pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'public.followups'::regclass
        ORDER BY conname;
    """)

    print()
    print("===== FOLLOWUP CONSTRAINTS =====")

    for row in cur.fetchall():
        print(row)

    cur.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'followups'
        ORDER BY indexname;
    """)

    print()
    print("===== FOLLOWUP INDEXES =====")

    for row in cur.fetchall():
        print(row)

    print()
    print("PHASE 5.4.3.2 FOLLOW-UP OUTREACH LINK MIGRATION PASSED")

finally:
    cur.close()
    conn.close()
