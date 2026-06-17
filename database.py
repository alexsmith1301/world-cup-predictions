from models import db, User
from datetime import datetime

def _run_migrations(app):
    """Add new columns to existing tables (safe to run on every startup)."""
    migrations = [
        'ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(30)',
        'ALTER TABLE fixtures ADD COLUMN result_notification_sent BOOLEAN DEFAULT FALSE',
        'ALTER TABLE fixtures ADD COLUMN kickoff_reminder_sent BOOLEAN DEFAULT FALSE',
    ]
    with app.app_context():
        # Use a separate connection per statement so a failed ALTER TABLE
        # (column already exists) doesn't abort subsequent migrations.
        for stmt in migrations:
            with db.engine.connect() as conn:
                try:
                    conn.execute(db.text(stmt))
                    conn.commit()
                except Exception:
                    conn.rollback()

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
