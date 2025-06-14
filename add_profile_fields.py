#!/usr/bin/env python3
"""
Database migration script to add profile fields to User model
"""

import pymysql
from datetime import datetime

# Database connection
connection = pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='afropeople_forum',
    charset='utf8mb4'
)

def add_profile_fields():
    """Add profile fields to the user table"""
    try:
        with connection.cursor() as cursor:
            # Add profile fields to user table
            profile_fields = [
                "ALTER TABLE user ADD COLUMN profile_image VARCHAR(255) DEFAULT 'default.jpg'",
                "ALTER TABLE user ADD COLUMN bio TEXT",
                "ALTER TABLE user ADD COLUMN location VARCHAR(100)",
                "ALTER TABLE user ADD COLUMN website VARCHAR(200)",
                "ALTER TABLE user ADD COLUMN twitter_handle VARCHAR(50)",
                "ALTER TABLE user ADD COLUMN linkedin_url VARCHAR(200)",
                "ALTER TABLE user ADD COLUMN github_url VARCHAR(200)",
                "ALTER TABLE user ADD COLUMN birth_date DATE",
                "ALTER TABLE user ADD COLUMN occupation VARCHAR(100)",
                "ALTER TABLE user ADD COLUMN interests TEXT",
                "ALTER TABLE user ADD COLUMN profile_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ]
            
            for sql in profile_fields:
                try:
                    cursor.execute(sql)
                    print(f"✓ Executed: {sql}")
                except pymysql.err.OperationalError as e:
                    if "Duplicate column name" in str(e):
                        print(f"⚠ Column already exists: {sql}")
                    else:
                        print(f"✗ Error: {sql} - {e}")
            
            connection.commit()
            print("\n✅ Profile fields migration completed successfully!")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    print("🚀 Starting profile fields migration...")
    add_profile_fields() 