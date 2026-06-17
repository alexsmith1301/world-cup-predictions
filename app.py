from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from functools import wraps
from datetime import datetime
import logging
import os
import csv
import io
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)

# Load .env file
load_dotenv()

from config import Config
from models import db, User, Fixture, Prediction
from database import init_db
from auth import login_required, get_current_user, login_user, logout_user
from predictions import get_leaderboard, get_user_stats, calculate_points
from api_client import LiveScoresAPIClient
from whatsapp import whatsapp_bp, send_result_notification_for_fixture
from scheduler import init_scheduler

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)
with app.app_context():
    init_db(app)

# Register WhatsApp blueprint
app.register_blueprint(whatsapp_bp)

# Initialize API client
api_client = LiveScoresAPIClient()

# Start background reminder scheduler
init_scheduler(app)

def sync_fixtures_on_startup():
    """Auto-sync World Cup fixtures on app startup if database has no real API fixtures"""
    with app.app_context():
        real_count = Fixture.query.filter(~Fixture.api_id.like('fallback_%')).count()
        if real_count == 0:
            print("\n📥 Syncing World Cup 2026 fixtures...")
            synced = api_client.fetch_and_sync_fixtures()
            if synced > 0:
                api_client.log_sync('fixtures', synced, status='success')
                print(f"✅ Successfully synced {synced} World Cup 2026 fixtures!\n")
            else:
                print("⚠️  Could not sync fixtures. Try manual sync from Admin panel.\n")

# Sync fixtures on startup
sync_fixtures_on_startup()

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

    # Get all other users' predictions keyed by fixture_id
    opponent_predictions = {}
    for p in Prediction.query.filter(Prediction.user_id != user.id).all():
        opponent_predictions.setdefault(p.fixture_id, []).append(p)

    # Organize fixtures by date
    fixtures_by_date = {}
    for fixture in fixtures:
        date_key = fixture.scheduled_datetime.strftime('%Y-%m-%d')
        if date_key not in fixtures_by_date:
            fixtures_by_date[date_key] = []
        fixtures_by_date[date_key].append(fixture)

    leaderboard_data = get_leaderboard()

    return render_template(
        'predictions.html',
        fixtures_by_date=fixtures_by_date,
        user_predictions=user_predictions,
        opponent_predictions=opponent_predictions,
        user=user,
        leaderboard=leaderboard_data,
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
    if user.username not in ['Alex']:
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
    if user.username not in ['Alex']:
        return jsonify({'error': 'Access denied'}), 403

    count = api_client.fetch_and_sync_fixtures()
    api_client.log_sync('fixtures', count)
    flash(f'Synced {count} fixtures', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/sync-results', methods=['POST'])
@login_required
def sync_results():
    user = get_current_user()
    if user.username not in ['Alex']:
        return jsonify({'error': 'Access denied'}), 403

    count, newly_completed = api_client.fetch_live_scores()
    api_client.log_sync('results', count)
    for fixture in newly_completed:
        send_result_notification_for_fixture(fixture)
    flash(f'Updated {count} fixtures with live scores', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add-prediction', methods=['POST'])
@login_required
def admin_add_prediction():
    user = get_current_user()
    if user.username not in ['Alex']:
        return jsonify({'error': 'Access denied'}), 403

    from predictions import update_prediction_points

    user_ids = request.form.getlist('user_id[]')
    fixture_ids = request.form.getlist('fixture_id[]')
    home_scores = request.form.getlist('home_score[]')
    away_scores = request.form.getlist('away_score[]')

    saved = 0
    errors = []
    for i, (uid, fid, hs, aws) in enumerate(zip(user_ids, fixture_ids, home_scores, away_scores), start=1):
        try:
            uid, fid, hs, aws = int(uid), int(fid), int(hs), int(aws)
        except (ValueError, TypeError):
            errors.append(f'Row {i}: invalid input')
            continue

        fixture = Fixture.query.get(fid)
        target_user = User.query.get(uid)
        if not fixture or not target_user:
            errors.append(f'Row {i}: user or fixture not found')
            continue

        prediction = Prediction.query.filter_by(user_id=uid, fixture_id=fid).first()
        if prediction:
            prediction.predicted_home_score = hs
            prediction.predicted_away_score = aws
            prediction.predicted_at = datetime.utcnow()
        else:
            prediction = Prediction(
                user_id=uid,
                fixture_id=fid,
                predicted_home_score=hs,
                predicted_away_score=aws,
            )
            db.session.add(prediction)

        db.session.flush()

        if fixture.status == 'completed':
            update_prediction_points(prediction)

        saved += 1

    db.session.commit()

    if saved:
        flash(f'Saved {saved} prediction{"s" if saved != 1 else ""}', 'success')
    for msg in errors:
        flash(msg, 'error')

    return redirect(url_for('admin'))

@app.route('/admin/delete-prediction/<int:prediction_id>', methods=['POST'])
@login_required
def delete_prediction(prediction_id):
    user = get_current_user()
    if user.username not in ['Alex']:
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
    if user.username not in ['Alex']:
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
    send_result_notification_for_fixture(fixture)

    flash(f'Score set for {fixture.home_team} vs {fixture.away_team}', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/set-whatsapp/<int:user_id>', methods=['POST'])
@login_required
def set_whatsapp(user_id):
    current = get_current_user()
    if current.username not in ['Alex']:
        return jsonify({'error': 'Access denied'}), 403

    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin'))

    number = request.form.get('whatsapp_number', '').strip().replace('whatsapp:', '')
    if number:
        if not number.startswith('+'):
            number = '+' + number
        user.whatsapp_number = number
        flash(f'WhatsApp number updated for {user.username}', 'success')
    else:
        user.whatsapp_number = None
        flash(f'WhatsApp number cleared for {user.username}', 'success')

    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/send-kickoff-reminders', methods=['POST'])
@login_required
def send_kickoff_reminders():
    user = get_current_user()
    if user.username not in ['Alex']:
        return jsonify({'error': 'Access denied'}), 403

    from datetime import timedelta
    from models import User as U, Fixture as F, Prediction as P
    from whatsapp import send_whatsapp

    now = datetime.utcnow()
    # Find upcoming fixtures in the next 3 hours that haven't had a reminder sent
    fixtures = (
        F.query
        .filter(
            F.scheduled_datetime >= now,
            F.scheduled_datetime <= now + timedelta(hours=3),
            F.status == 'not_started',
            F.kickoff_reminder_sent == False,
        )
        .order_by(F.scheduled_datetime)
        .all()
    )

    if not fixtures:
        flash('No upcoming fixtures needing a reminder in the next 3 hours', 'error')
        return redirect(url_for('admin'))

    wa_users = U.query.filter(U.whatsapp_number.isnot(None)).all()
    if not wa_users:
        flash('No users have WhatsApp numbers set', 'error')
        return redirect(url_for('admin'))

    sent = 0
    for f in fixtures:
        kickoff_bst = (f.scheduled_datetime + timedelta(hours=1)).strftime('%H:%M BST')
        for u in wa_users:
            pred = P.query.filter_by(user_id=u.id, fixture_id=f.id).first()
            if pred:
                msg = (
                    f"⏰ Kick-off reminder\n\n"
                    f"{f.home_team} v {f.away_team}  {kickoff_bst}\n\n"
                    f"Your prediction: {pred.predicted_home_score}-{pred.predicted_away_score}"
                )
            else:
                msg = (
                    f"⏰ Kick-off reminder\n\n"
                    f"{f.home_team} v {f.away_team}  {kickoff_bst}\n\n"
                    f"No prediction yet!\nReply: {f.home_team} 2-1 {f.away_team}"
                )
            try:
                send_whatsapp(u.whatsapp_number, msg)
                sent += 1
            except Exception as e:
                flash(f'Failed to send to {u.username}: {e}', 'error')

        f.kickoff_reminder_sent = True
        db.session.commit()

    flash(f'Sent {sent} kickoff reminder{"s" if sent != 1 else ""}', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/export-csv')
@login_required
def export_csv():
    user = get_current_user()
    if user.username not in ['Alex']:
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    app.run(debug=False, port=args.port)
