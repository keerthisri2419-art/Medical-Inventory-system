"""
seed_passwords.py — Run this ONCE after importing database.sql
to set real password hashes for the default users.

Usage:
    python seed_passwords.py
"""

import mysql.connector
from werkzeug.security import generate_password_hash
from config import Config

USERS = [
    ('admin',  'admin123'),
    ('staff1', 'staff123'),
]

def seed():
    conn = mysql.connector.connect(
        host     = Config.DB_HOST,
        port     = Config.DB_PORT,
        user     = Config.DB_USER,
        password = Config.DB_PASSWORD,
        database = Config.DB_NAME
    )
    cursor = conn.cursor()

    for username, password in USERS:
        hashed = generate_password_hash(password)
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE username = %s",
            (hashed, username)
        )
        print(f"✓ Password set for '{username}'")

    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ All passwords seeded successfully!")
    print("   admin  → admin123")
    print("   staff1 → staff123")

if __name__ == '__main__':
    seed()
