from models import db, User
from datetime import datetime

def _run_migrations(app):
    """Add new columns to existing tables (safe to run on every startup)."""
    with app.app_context():
        with db.engine.connect() as conn:
            try:
                conn.execute(db.text('ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(30)'))
                conn.commit()
            except Exception:
                pass  # Column already exists
            try:
                conn.execute(db.text('ALTER TABLE fixtures ADD COLUMN result_notification_sent BOOLEAN DEFAULT 0'))
                conn.commit()
            except Exception:
                pass  # Column already exists
            try:
                conn.execute(db.text('ALTER TABLE fixtures ADD COLUMN kickoff_reminder_sent BOOLEAN DEFAULT 0'))
                conn.commit()
            except Exception:
                pass  # Column already exists

def init_db(app):
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        _run_migrations(app)

        # Create default users if they don't exist
        if User.query.filter_by(username='Alex').first() is None:
            alex = User(username='Alex')
            alex.set_password('alex123')
            db.session.add(alex)

        if User.query.filter_by(username='Phoebe').first() is None:
            phoebe = User(username='Phoebe')
            phoebe.set_password('phoebe123')
            db.session.add(phoebe)

        db.session.commit()
        print("Database initialized with default users")

def reset_db(app):
    """Reset the database (drop all tables and recreate)"""
    with app.app_context():
        db.drop_all()
        init_db(app)
        print("Database reset")
