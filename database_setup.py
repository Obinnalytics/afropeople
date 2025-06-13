"""
Database setup script for AfroPeople Forum
This script creates the MySQL database required for the application.
"""

import pymysql
import sys

def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to MySQL server (without specifying a database)
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # Create database if it doesn't exist
            cursor.execute("CREATE DATABASE IF NOT EXISTS afropeople_forum CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("✓ Database 'afropeople_forum' created successfully!")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Error creating database: {e}")
        return False

def test_connection():
    """Test the database connection"""
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
            database='afropeople_forum',
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✓ Successfully connected to MySQL version: {version[0]}")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Error connecting to database: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Setting up AfroPeople Forum Database...")
    print("=" * 50)
    
    # Create the database
    if create_database():
        # Test the connection
        if test_connection():
            print("=" * 50)
            print("✅ Database setup completed successfully!")
            print("You can now run the Flask application with: python app.py")
        else:
            print("❌ Database connection test failed!")
            sys.exit(1)
    else:
        print("❌ Database creation failed!")
        sys.exit(1) 