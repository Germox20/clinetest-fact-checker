"""
Database migration script for Curator Agent features.
Adds merge tracking fields to the Report model.

Run this script to update your database schema:
    python migrate_curator.py
"""
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Report
from sqlalchemy import text

def migrate_database():
    """Migrate database to add Curator Agent fields."""
    app = create_app()
    
    with app.app_context():
        print("="*60)
        print("Curator Agent Database Migration")
        print("="*60)
        
        # Check if migration is needed
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('reports')]
        
        needs_migration = 'is_merged' not in columns
        
        if not needs_migration:
            print("\n✓ Database already has Curator Agent fields")
            print("  No migration needed.")
            return
        
        print("\n→ Adding Curator Agent fields to reports table...")
        
        try:
            # Add new columns
            with db.engine.connect() as conn:
                # Add is_merged column
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN is_merged BOOLEAN DEFAULT 0"
                ))
                print("  ✓ Added is_merged column")
                
                # Add merge_count column
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN merge_count INTEGER DEFAULT 0"
                ))
                print("  ✓ Added merge_count column")
                
                # Add analysis_attempts column
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN analysis_attempts INTEGER DEFAULT 1"
                ))
                print("  ✓ Added analysis_attempts column")
                
                # Add parent_report_id column
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN parent_report_id INTEGER"
                ))
                print("  ✓ Added parent_report_id column")
                
                # Add last_updated column
                conn.execute(text(
                    f"ALTER TABLE reports ADD COLUMN last_updated DATETIME DEFAULT '{datetime.utcnow().isoformat()}'"
                ))
                print("  ✓ Added last_updated column")
                
                conn.commit()
            
            print("\n" + "="*60)
            print("✓ Migration completed successfully!")
            print("="*60)
            print("\nCurator Agent is now ready to use:")
            print("  • Query optimization for better search results")
            print("  • Duplicate detection and filtering")
            print("  • Report merging for re-analyzed articles")
            print("  • Iterative analysis (up to 3 attempts)")
            print("\nYou can now run the application:")
            print("  python run.py")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            print("\nIf you encounter errors, you may need to:")
            print("  1. Backup your current database")
            print("  2. Delete the database file: rm instance/fact_checker.db")
            print("  3. Recreate it: python run.py init-db")
            raise

if __name__ == '__main__':
    migrate_database()
