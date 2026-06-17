from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    whatsapp_number = db.Column(db.String(30), unique=True, nullable=True)

    predictions = db.relationship('Prediction', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_total_points(self):
        predictions = Prediction.query.filter_by(user_id=self.id).all()
        return sum(p.points_earned or 0 for p in predictions)

    def __repr__(self):
        return f'<User {self.username}>'


class Fixture(db.Model):
    __tablename__ = 'fixtures'
    id = db.Column(db.Integer, primary_key=True)
    api_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    scheduled_datetime = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), default='not_started', nullable=False)  # not_started, in_progress, completed
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    result_notification_sent = db.Column(db.Boolean, default=False, nullable=False)

    predictions = db.relationship('Prediction', backref='fixture', lazy=True, cascade='all, delete-orphan')

    def is_kickoff_passed(self):
        """Check if the match has started"""
        return datetime.utcnow() >= self.scheduled_datetime

    def get_goal_difference(self):
        """Get the actual goal difference"""
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score - self.away_score

    def get_result(self):
        """Get the match result: 'home', 'away', or 'draw'"""
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return 'home'
        elif self.away_score > self.home_score:
            return 'away'
        else:
            return 'draw'

    def __repr__(self):
        return f'<Fixture {self.home_team} vs {self.away_team}>'


class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    fixture_id = db.Column(db.Integer, db.ForeignKey('fixtures.id'), nullable=False, index=True)
    predicted_home_score = db.Column(db.Integer, nullable=False)
    predicted_away_score = db.Column(db.Integer, nullable=False)
    predicted_at = db.Column(db.DateTime, default=datetime.utcnow)
    points_earned = db.Column(db.Integer, nullable=True)
    points_breakdown = db.Column(db.String(200), nullable=True)  # JSON: {exact: 0, diff: 3, result: 5}

    __table_args__ = (db.UniqueConstraint('user_id', 'fixture_id', name='_user_fixture_uc'),)

    def get_predicted_goal_difference(self):
        return self.predicted_home_score - self.predicted_away_score

    def get_predicted_result(self):
        if self.predicted_home_score > self.predicted_away_score:
            return 'home'
        elif self.predicted_away_score > self.predicted_home_score:
            return 'away'
        else:
            return 'draw'

    def get_points_breakdown(self):
        """Get breakdown of points as dict"""
        if self.points_breakdown:
            return json.loads(self.points_breakdown)
        return {'exact': 0, 'diff': 0, 'result': 0}

    def set_points_breakdown(self, breakdown):
        """Set breakdown from dict"""
        self.points_breakdown = json.dumps(breakdown)

    def __repr__(self):
        return f'<Prediction {self.user.username} -> {self.fixture}>'


class SyncLog(db.Model):
    __tablename__ = 'sync_logs'
    id = db.Column(db.Integer, primary_key=True)
    sync_type = db.Column(db.String(20), nullable=False)  # 'fixtures' or 'results'
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
    fixtures_updated = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='success')  # 'success' or 'failed'
    error_message = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f'<SyncLog {self.sync_type} at {self.synced_at}>'
