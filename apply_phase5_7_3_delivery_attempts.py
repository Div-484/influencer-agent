"""
Phase 5.7.3 Migration.

Create outbound delivery-attempt tracking.
"""

from db import get_connection


def apply_migration():
    conn = get_connection()
    cur = conn.cursor()

    try:
        # ---------------------------------------------------------
        # ENUM
        # ---------------------------------------------------------
        cur.execute(
            """
            DO $$
            BEGIN
                CREATE TYPE outreach_delivery_attempt_status AS ENUM (
                    'started',
                    'smtp_succeeded',
                    'finalized',
                    'failed'
                );
            EXCEPTION
                WHEN duplicate_object THEN
                    NULL;
            END
            $$;
            """
        )

        # ---------------------------------------------------------
        # TABLE
        # ---------------------------------------------------------
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS outreach_delivery_attempts (
                attempt_id UUID PRIMARY KEY
                    DEFAULT gen_random_uuid(),

                outreach_id UUID NOT NULL
                    REFERENCES outreach(outreach_id)
                    ON DELETE CASCADE,

                attempt_number INTEGER NOT NULL
                    CHECK (attempt_number > 0),

                status outreach_delivery_attempt_status NOT NULL
                    DEFAULT 'started',

                smtp_started_at TIMESTAMPTZ,

                smtp_succeeded_at TIMESTAMPTZ,

                finalized_at TIMESTAMPTZ,

                last_error TEXT,

                created_at TIMESTAMPTZ NOT NULL
                    DEFAULT NOW()
            );
            """
        )

        # ---------------------------------------------------------
        # UNIQUE ATTEMPT IDENTITY
        # ---------------------------------------------------------
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_outreach_delivery_attempts_identity
            ON outreach_delivery_attempts (
                outreach_id,
                attempt_number
            );
            """
        )

        # ---------------------------------------------------------
        # OUTREACH LOOKUP INDEX
        # ---------------------------------------------------------
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_outreach_delivery_attempts_outreach
            ON outreach_delivery_attempts (
                outreach_id
            );
            """
        )

        # ---------------------------------------------------------
        # STATUS INDEX
        # ---------------------------------------------------------
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_outreach_delivery_attempts_status
            ON outreach_delivery_attempts (
                status
            );
            """
        )

        conn.commit()

        print(
            "PHASE 5.7.3 DELIVERY ATTEMPT "
            "MIGRATION APPLIED"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    apply_migration()
