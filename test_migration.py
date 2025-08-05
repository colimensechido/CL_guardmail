#!/usr/bin/env python3
"""
Test script to verify database migration works correctly.
"""

import sqlite3
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SpamDatabase

def test_migration():
    """Test the database migration."""
    print("🧪 Testing database migration...")
    
    try:
        # Create database instance (this will run migrations)
        db = SpamDatabase("spam_detector.db")
        
        # Check if model_id column exists
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA table_info(training_examples)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"📋 Columns in training_examples table: {columns}")
        
        if 'model_id' in columns:
            print("✅ Migration successful! model_id column exists.")
            
            # Check if we have the new schema columns
            required_columns = ['title', 'content', 'classification', 'source_type']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"⚠️ Missing columns: {missing_columns}")
                print("🔄 Need to update table schema...")
                
                # Show current vs expected schema
                print("\nCurrent schema:")
                for column in columns:
                    print(f"  - {column}")
                
                print("\nExpected schema:")
                expected_columns = ['id', 'model_id', 'title', 'content', 'classification', 'source_type', 'email_id', 'features_extracted', 'created_at', 'created_by', 'is_validated']
                for column in expected_columns:
                    print(f"  - {column}")
                
            else:
                print("✅ All required columns exist!")
                
                # Test adding a training example
                try:
                    # First, create a test model if it doesn't exist
                    model_id = db.create_ml_model(
                        name="Test Model",
                        description="Test model for migration",
                        model_type="spam_detector",
                        algorithm="naive_bayes"
                    )
                    
                    # Add a training example
                    example_id = db.add_training_example(
                        model_id=model_id,
                        title="Test Example",
                        content="This is a test example for migration",
                        classification=True,
                        source_type='manual'
                    )
                    
                    print(f"✅ Successfully added training example with ID: {example_id}")
                    
                except Exception as e:
                    print(f"❌ Error adding training example: {e}")
                
        else:
            print("❌ Migration failed! model_id column not found.")
            
    except Exception as e:
        print(f"❌ Error during migration test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_migration() 