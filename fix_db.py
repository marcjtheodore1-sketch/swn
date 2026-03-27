from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Add notify_leader column
        db.session.execute(text("ALTER TABLE walk_event ADD COLUMN notify_leader BOOLEAN DEFAULT 0"))
        print("✓ Added notify_leader column")
    except Exception as e:
        print(f"notify_leader: {e}")
    
    try:
        # Add leader_email column  
        db.session.execute(text("ALTER TABLE walk_event ADD COLUMN leader_email VARCHAR(120)"))
        print("✓ Added leader_email column")
    except Exception as e:
        print(f"leader_email: {e}")
    
    db.session.commit()
    print("\nDatabase updated! Reload your web app.")
