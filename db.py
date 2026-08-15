"""
db.py — shared database connection for the Influencer Outreach Agent.

Every agent script (contact_discovery.py, outreach.py, etc.) should
import get_connection() from here instead of connecting to Postgres
on its own. Keeps the connection string in ONE place.
"""

import os
import psycopg2
from dotenv import load_dotenv

# Reads the .env file sitting next to this script and loads it into
# the environment, so os.environ can see SUPABASE_DB_URL.
load_dotenv()


def get_connection():
    """
    Returns a live psycopg2 connection to the Supabase Postgres database.
    Raises a clear error early if SUPABASE_DB_URL isn't set, instead of
    failing with a confusing psycopg2 error later.
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError(
            "SUPABASE_DB_URL not found. Make sure you have a .env file "
            "in this folder with a line like:\n"
            "SUPABASE_DB_URL=postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres"
        )
    return psycopg2.connect(db_url)