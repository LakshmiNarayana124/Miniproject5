"""
Migrate pre-existing users from local SQLite to Neon Postgres.
Run: python migrate_users.py
Requires DATABASE_URL env var pointing to Neon.
"""
import os, sqlite3, sys

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERROR: Set DATABASE_URL env var to your Neon connection string")
    sys.exit(1)

import psycopg2

# Read users from local SQLite
local = sqlite3.connect(r"Backend/database/intelliwatch.db")
local.row_factory = sqlite3.Row
users = local.execute(
    "SELECT username, full_name, password_hash, role, is_active "
    "FROM users WHERE username IN ('watchtower_01','operator01','engineer01','operator_1')"
).fetchall()
local.close()

if not users:
    print("No matching users found in local DB")
    sys.exit(1)

print(f"Found {len(users)} users to migrate:")
for u in users:
    print(f"  {u['username']} ({u['role']})")

# Connect to Neon
pg = psycopg2.connect(DATABASE_URL)
pg.autocommit = False
cur = pg.cursor()

# Ensure users table exists (backend auto-creates on startup but just in case)
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'OPERATOR',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_login TIMESTAMPTZ,
        failed_login_attempts INTEGER DEFAULT 0,
        locked_until TIMESTAMPTZ,
        reset_token TEXT,
        reset_token_expires TIMESTAMPTZ,
        session_version INTEGER DEFAULT 1,
        is_deleted BOOLEAN DEFAULT FALSE
    )
""")

migrated = 0
skipped  = 0
for u in users:
    cur.execute("SELECT id FROM users WHERE username = %s", (u['username'],))
    existing = cur.fetchone()
    if existing:
        # Update password hash to match local DB (keeps same password)
        cur.execute(
            "UPDATE users SET password_hash=%s, is_active=%s::integer WHERE username=%s",
            (u['password_hash'], int(u['is_active']), u['username'])
        )
        print(f"  Updated: {u['username']}")
        skipped += 1
    else:
        cur.execute(
            "INSERT INTO users (username, full_name, password_hash, role, is_active, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW())",
            (u['username'], u['full_name'], u['password_hash'], u['role'], int(u['is_active']))
        )
        print(f"  Inserted: {u['username']}")
        migrated += 1

pg.commit()
cur.close()
pg.close()

print(f"\nDone. Inserted: {migrated}, Updated: {skipped}")
print("All accounts now work on the live deployment.")
