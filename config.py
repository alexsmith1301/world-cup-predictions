import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration"""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(basedir, "predictions.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY = True

    # API Configuration
    LIVE_SCORES_API_KEY = os.environ.get('LIVE_SCORES_API_KEY', '')
    LIVE_SCORES_API_URL = os.environ.get('LIVE_SCORES_API_URL', 'https://v3.football.api-sports.io')

    # Sync configuration
    FIXTURES_SYNC_INTERVAL = 3600  # 1 hour in seconds
    RESULTS_SYNC_INTERVAL = 300    # 5 minutes in seconds
