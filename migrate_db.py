"""
Database migration script.
Drops existing database and creates new schema with hierarchical fact structure.

Usage:
    python migrate_db.py
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Drop existing database and create new schema."""
    # Define database path
    db_path = os.path.join('instance', 'fact_checker.db')
    
    print("=" * 60)
    print("DATABASE MIGRATION TOOL")
    print("=" * 60)
    print("\nWARNING: This will delete the existing database!")
    print(f"Database location: {db_path}")
    print("\nChanges in new schema:")
    print("  - Fact model now hierarchical (WHAT and CLAIM are primary)")
    print("  - WHO, WHERE, WHEN are now related entities within facts")
    print("  - Added importance_score field for search prioritization")
    print("  - Added parent_fact_id for hierarchical relationships")
    print("=" * 60)
    
    # Check if database exists
    if os.path.exists(db_path):
        print(f"\n✓ Found existing database at {db_path}")
        response = input("\nAre you sure you want to delete it? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("\nMigration cancelled.")
            return
        
        # Delete existing database
        try:
            os.remove(db_path)
            print(f"✓ Existing database deleted")
        except Exception as e:
            print(f"✗ Error deleting database: {e}")
            return
    else:
        print(f"\n! No existing database found at {db_path}")
    
    # Create instance directory if it doesn't exist
    instance_dir = 'instance'
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"✓ Created instance directory")
    
    # Import and create schema
    try:
        from app import create_app
        from app.models import db
        
        app = create_app()
        
        with app.app_context():
            db.create_all()
            print("✓ New database schema created successfully")
            
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print("\nCreated tables:")
            for table in tables:
                print(f"  - {table}")
            
            print("\n" + "=" * 60)
            print("MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Set up your API keys in .env file")
            print("  2. Run the application: python run.py")
            print("  3. Start analyzing articles!")
            
    except Exception as e:
        print(f"\n✗ Error creating database schema: {e}")
        import traceback
        traceback.print_exc()
        print("\nMigration failed!")
        return


if __name__ == '__main__':
    migrate_database()
