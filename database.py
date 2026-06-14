from models import db, User
from datetime import datetime

def init_db(app):
    """Initialize the database"""
    with app.app_context():
        db.create_all()

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
