from flask import session, redirect, url_for, request
from functools import wraps
from models import User

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get the currently logged in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def login_user(user):
    """Log in a user"""
    session['user_id'] = user.id
    session['username'] = user.username
    session.permanent = True

def logout_user():
    """Log out the current user"""
    session.clear()
