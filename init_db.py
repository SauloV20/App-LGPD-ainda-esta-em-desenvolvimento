import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys=ON")

conn.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT DEFAULT 'free',
    scans_used INTEGER DEFAULT 0,
    scans_this_month INTEGER DEFAULT 0,
    month_reset TEXT DEFAULT '',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT DEFAULT 'none',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    source_type TEXT DEFAULT 'text',
    total_matches INTEGER DEFAULT 0,
    risk_level TEXT DEFAULT 'nenhum',
    details TEXT,
    raw_text TEXT,
    anonymized_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    data_type TEXT NOT NULL,
    value TEXT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

# Migrações seguras para bancos existentes
migrations = [
    ("users", "scans_this_month",       "ALTER TABLE users ADD COLUMN scans_this_month INTEGER DEFAULT 0"),
    ("users", "month_reset",            "ALTER TABLE users ADD COLUMN month_reset TEXT DEFAULT ''"),
    ("users", "plan",                   "ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'"),
    ("users", "stripe_customer_id",     "ALTER TABLE users ADD COLUMN stripe_customer_id TEXT"),
    ("users", "stripe_subscription_id", "ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT"),
    ("users", "subscription_status",    "ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'none'"),
    ("scans", "anonymized_text",        "ALTER TABLE scans ADD COLUMN anonymized_text TEXT"),
    ("scans", "source_type",            "ALTER TABLE scans ADD COLUMN source_type TEXT DEFAULT 'text'"),
    ("scans", "risk_level",             "ALTER TABLE scans ADD COLUMN risk_level TEXT DEFAULT 'nenhum'"),
    ("scans", "raw_text",               "ALTER TABLE scans ADD COLUMN raw_text TEXT"),
]

for table, col, sql in migrations:
    existing = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in existing:
        conn.execute(sql)
        print(f"  + Migração aplicada: {table}.{col}")

conn.commit()
conn.close()
print("Banco de dados pronto.")
