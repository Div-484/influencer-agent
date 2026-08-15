"""
test_connection.py — run this once to confirm your .env and Supabase
database are wired up correctly.

What it does:
  1. Connects to your Supabase Postgres database
  2. Inserts one dummy row into the 'brands' table
  3. Reads it back
  4. Deletes it again, so your table stays clean

Run it with:
    python test_connection.py
"""

from db import get_connection


def run_test():
    conn = get_connection()
    cur = conn.cursor()

    print("Connected to Supabase successfully.")

    # 1. Insert a dummy brand
    cur.execute(
        """
        INSERT INTO brands (name, normalized_name, website, discovery_source)
        VALUES (%s, %s, %s, %s)
        RETURNING brand_id;
        """,
        ("Test Brand Co", "test brand co", "https://testbrand.com", "connection_test"),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    print(f"Inserted test row. brand_id = {new_id}")

    # 2. Read it back
    cur.execute("SELECT name, website FROM brands WHERE brand_id = %s;", (new_id,))
    row = cur.fetchone()
    print(f"Read back: name={row[0]}, website={row[1]}")

    # 3. Clean up — delete the test row so the table stays empty
    cur.execute("DELETE FROM brands WHERE brand_id = %s;", (new_id,))
    conn.commit()
    print("Test row deleted. Cleanup done.")

    cur.close()
    conn.close()
    print("\nConnection test PASSED — your database is ready to use.")


if __name__ == "__main__":
    run_test()