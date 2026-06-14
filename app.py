from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from functools import wraps
from datetime import datetime
import os
import csv
import io

from config import Config
from models import db, User, Fixture, Prediction
from database import init_db
from auth import login_required, get_current_user, login_user, logout_user
from predictions import get_leaderboard, get_user_stats, calculate_points
from api_client import LiveScoresAPIClient

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)
with app.app_context():
    init_db(app)

# Initialize API client
api_client = LiveScoresAPIClient()

@app.before_request
def set_current_user():
    """Make current user available in all templates"""
    app.jinja_env.globals['current_user'] = get_current_user()

# ==================== Authentication Routes ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next') or url_for('predictions')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

# ==================== Predictions Routes ====================

@app.route('/predictions', methods=['GET', 'POST'])
@login_required
def predictions():
    user = get_current_user()

    if request.method == 'POST':
        fixture_id = request.form.get('fixture_id')
        home_score = request.form.get('home_score')
        away_score = request.form.get('away_score')

        fixture = Fixture.query.get(fixture_id)
        if not fixture:
            flash('Fixture not found', 'error')
            return redirect(url_for('predictions'))

        # Check if kickoff has passed
        if fixture.is_kickoff_passed():
            flash('Cannot submit prediction after kickoff', 'error')
            return redirect(url_for('predictions'))

        try:
            home_score = int(home_score)
            away_score = int(away_score)
        except (ValueError, TypeError):
            flash('Invalid score input', 'error')
            return redirect(url_for('predictions'))

        # Check if prediction already exists
        prediction = Prediction.query.filter_by(
            user_id=user.id,
            fixture_id=fixture_id
        ).first()

        if prediction:
            # Update existing prediction if before kickoff
            if not fixture.is_kickoff_passed():
                prediction.predicted_home_score = home_score
                prediction.predicted_away_score = away_score
                prediction.predicted_at = datetime.utcnow()
            else:
                flash('Cannot modify prediction after kickoff', 'error')
                return redirect(url_for('predictions'))
        else:
            # Create new prediction
            prediction = Prediction(
                user_id=user.id,
                fixture_id=fixture_id,
                predicted_home_score=home_score,
                predicted_away_score=away_score
            )
            db.session.add(prediction)

        db.session.commit()
        flash('Prediction saved successfully', 'success')
        return redirect(url_for('predictions'))

    # Get all fixtures
    fixtures = Fixture.query.order_by(Fixture.scheduled_datetime).all()

    # Get user's predictions
    user_predictions = {p.fixture_id: p for p in Prediction.query.filter_by(user_id=user.id).all()}

    # Organize fixtures by date
    fixtures_by_date = {}
    for fixture in fixtures:
        date_key = fixture.scheduled_datetime.strftime('%Y-%m-%d')
        if date_key not in fixtures_by_date:
            fixtures_by_date[date_key] = []
        fixtures_by_date[date_key].append(fixture)

    return render_template(
        'predictions.html',
        fixtures_by_date=fixtures_by_date,
        user_predictions=user_predictions,
        user=user
    )

# ==================== Leaderboard Routes ====================

@app.route('/leaderboard')
@login_required
def leaderboard():
    leaderboard_data = get_leaderboard()
    return render_template('leaderboard.html', leaderboard=leaderboard_data)

# ==================== Admin Routes ====================

@app.route('/admin')
@login_required
def admin():
    # Simple check - only allow if user is one of the main users (could be expanded)
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        flash('Access denied', 'error')
        return redirect(url_for('leaderboard'))

    from models import SyncLog
    sync_logs = SyncLog.query.filter_by(sync_type='fixtures').count()
    last_sync = SyncLog.query.order_by(SyncLog.synced_at.desc()).first()

    all_predictions = Prediction.query.all()
    all_fixtures = Fixture.query.all()
    users = User.query.all()

    return render_template(
        'admin.html',
        predictions=all_predictions,
        fixtures=all_fixtures,
        users=users,
        sync_count=sync_logs,
        last_sync=last_sync
    )

@app.route('/admin/sync-fixtures', methods=['POST'])
@login_required
def sync_fixtures():
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        return jsonify({'error': 'Access denied'}), 403

    count = api_client.fetch_and_sync_fixtures()
    api_client.log_sync('fixtures', count)
    flash(f'Synced {count} fixtures', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/sync-results', methods=['POST'])
@login_required
def sync_results():
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        return jsonify({'error': 'Access denied'}), 403

    count = api_client.fetch_live_scores()
    api_client.log_sync('results', count)
    flash(f'Updated {count} fixtures with live scores', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete-prediction/<int:prediction_id>', methods=['POST'])
@login_required
def delete_prediction(prediction_id):
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        return jsonify({'error': 'Access denied'}), 403

    prediction = Prediction.query.get(prediction_id)
    if prediction:
        fixture_id = prediction.fixture_id
        db.session.delete(prediction)
        db.session.commit()
        flash('Prediction deleted', 'success')

    return redirect(url_for('admin'))

@app.route('/admin/set-score/<int:fixture_id>', methods=['POST'])
@login_required
def set_score(fixture_id):
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        return jsonify({'error': 'Access denied'}), 403

    fixture = Fixture.query.get(fixture_id)
    if not fixture:
        flash('Fixture not found', 'error')
        return redirect(url_for('admin'))

    try:
        home_score = int(request.form.get('home_score'))
        away_score = int(request.form.get('away_score'))
    except (ValueError, TypeError):
        flash('Invalid score input', 'error')
        return redirect(url_for('admin'))

    fixture.home_score = home_score
    fixture.away_score = away_score
    fixture.status = 'completed'
    db.session.commit()

    # Update points for all predictions on this fixture
    from predictions import update_all_prediction_points_for_fixture
    update_all_prediction_points_for_fixture(fixture)

    flash(f'Score set for {fixture.home_team} vs {fixture.away_team}', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/export-csv')
@login_required
def export_csv():
    user = get_current_user()
    if user.username not in ['Alex', 'Phoebe']:
        return jsonify({'error': 'Access denied'}), 403

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Username', 'Fixture', 'Predicted Score', 'Actual Score', 'Points Earned', 'Points Breakdown'])

    predictions = Prediction.query.all()
    for pred in predictions:
        fixture = pred.fixture
        pred_score = f"{pred.predicted_home_score}-{pred.predicted_away_score}"
        actual_score = f"{fixture.home_score}-{fixture.away_score}" if fixture.home_score is not None else "N/A"
        points = pred.points_earned or 0
        breakdown = pred.get_points_breakdown() if pred.points_earned else {}

        writer.writerow([
            pred.user.username,
            f"{fixture.home_team} vs {fixture.away_team}",
            pred_score,
            actual_score,
            points,
            str(breakdown)
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='predictions_export.csv'
    )

# ==================== Utility Routes ====================

@app.route('/')
def index():
    if get_current_user():
        return redirect(url_for('predictions'))
    return redirect(url_for('login'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
