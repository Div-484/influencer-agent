"""
Agent Run Logger.

Phase 3.2:
    - Record agent execution results in public.agent_runs.
    - Store input/output references.
    - Store execution duration.
    - Store errors for failed runs.

This module only handles audit logging.
"""

from db import get_connection


def record_agent_run(
    agent_name: str,
    status: str,
    input_ref: str | None = None,
    output_ref: str | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
):
    """
    Record one agent execution in public.agent_runs.

    Supported statuses:
        success
        failed
        retrying
    """

    if not agent_name or not agent_name.strip():
        raise ValueError("agent_name is required.")

    if status not in {
        "success",
        "failed",
        "retrying",
    }:
        raise ValueError(
            f"Unsupported agent run status: {status}"
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO agent_runs (
                agent_name,
                input_ref,
                output_ref,
                status,
                duration_ms,
                error_message
            )
            VALUES (
                %s,
                %s,
                %s,
                %s::agent_run_status,
                %s,
                %s
            )
            RETURNING run_id;
            """,
            (
                agent_name.strip(),
                input_ref,
                output_ref,
                status,
                duration_ms,
                error_message,
            ),
        )

        run_id = cur.fetchone()[0]

        conn.commit()

        return run_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
