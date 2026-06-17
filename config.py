import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration"""
    _db_url = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(basedir, "predictions.db")}'
    SQLALCHEMY_DATABASE_URI = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = bool(os.environ.get('RAILWAY_ENVIRONMENT'))
    SESSION_COOKIE_HTTPONLY = True

    # API Configuration
    LIVE_SCORES_API_KEY = os.environ.get('LIVE_SCORES_API_KEY', '')
    LIVE_SCORES_API_URL = os.environ.get('LIVE_SCORES_API_URL', 'https://api.zafronix.com/fifa/worldcup/v1')

    # Sync configuration
    FIXTURES_SYNC_INTERVAL = 3600  # 1 hour in seconds
    RESULTS_SYNC_INTERVAL = 300    # 5 minutes in seconds

    # Twilio WhatsApp configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
