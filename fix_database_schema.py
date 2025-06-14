#!/usr/bin/env python3
"""
Database Schema Fix Script
Adds missing columns to category and ad_sense tables
"""

import pymysql
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'afropeople_forum'),
    'charset': 'utf8mb4'
}

def fix_database_schema():
    """Fix missing columns in database tables"""
    try:
        # Create database connection
        connection_string = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
        engine = create_engine(connection_string)
        
        with engine.connect() as conn:
            print("🔧 Starting database schema fixes...")
            
            # Fix Category table - add slug column if missing
            try:
                conn.execute(text("SELECT slug FROM category LIMIT 1"))
                print("✅ Category.slug column already exists")
            except Exception:
                print("➕ Adding slug column to category table...")
                conn.execute(text("ALTER TABLE category ADD COLUMN slug VARCHAR(100) UNIQUE"))
                
                # Generate slugs for existing categories
                categories = conn.execute(text("SELECT id, name FROM category")).fetchall()
                for category in categories:
                    slug = generate_slug(category.name)
                    conn.execute(text("UPDATE category SET slug = :slug WHERE id = :id"), 
                               {"slug": slug, "id": category.id})
                print("✅ Category.slug column added and populated")
            
            # Fix AdSense table - add missing columns
            missing_columns = [
                ('category_ad_code', 'TEXT'),
                ('profile_ad_code', 'TEXT'),
                ('auto_ads_enabled', 'BOOLEAN DEFAULT FALSE'),
                ('ad_frequency', 'VARCHAR(20) DEFAULT "always"'),
                ('responsive_ads', 'BOOLEAN DEFAULT TRUE')
            ]
            
            for column_name, column_type in missing_columns:
                try:
                    conn.execute(text(f"SELECT {column_name} FROM ad_sense LIMIT 1"))
                    print(f"✅ AdSense.{column_name} column already exists")
                except Exception:
                    print(f"➕ Adding {column_name} column to ad_sense table...")
                    conn.execute(text(f"ALTER TABLE ad_sense ADD COLUMN {column_name} {column_type}"))
                    print(f"✅ AdSense.{column_name} column added")
            
            # Commit all changes
            conn.commit()
            print("🎉 Database schema fixes completed successfully!")
            
    except Exception as e:
        print(f"❌ Error fixing database schema: {e}")
        return False
    
    return True

def generate_slug(name):
    """Generate a URL-friendly slug from a name"""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    
    # Ensure slug is not empty
    if not slug:
        slug = 'category'
    
    return slug

if __name__ == "__main__":
    print("🚀 AfroPeople Database Schema Fix")
    print("=" * 40)
    
    if fix_database_schema():
        print("\n✅ All database schema issues have been resolved!")
        print("You can now restart your Flask application.")
    else:
        print("\n❌ Failed to fix database schema.")
        print("Please check the error messages above.") 