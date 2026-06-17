import re
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, current_app
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from rapidfuzz import process, fuzz

from models import db, User, Fixture, Prediction
from predictions import get_leaderboard

logger = logging.getLogger(__name__)
whatsapp_bp = Blueprint('whatsapp', __name__)


def send_whatsapp(to_number, body):
    """Send a WhatsApp message via Twilio. Must be called within an app context."""
    client = Client(
        current_app.config['TWILIO_ACCOUNT_SID'],
        current_app.config['TWILIO_AUTH_TOKEN'],
    )
    to = f'whatsapp:{to_number}' if not to_number.startswith('whatsapp:') else to_number
    client.messages.create(
        from_=current_app.config['TWILIO_WHATSAPP_FROM'],
        to=to,
        body=body,
    )
    logger.info("WhatsApp sent to %s", to_number)


def _normalize_phone(number):
    return number.replace('whatsapp:', '').strip()


def _get_user_by_whatsapp(phone):
    return User.query.filter_by(whatsapp_number=phone).first()


@whatsapp_bp.route('/api/whatsapp/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip()

    phone = _normalize_phone(from_number)
    user = _get_user_by_whatsapp(phone)

    resp = MessagingResponse()

    if not user:
        resp.message(
            "Welcome to World Cup Predictor ⚽\n\n"
            "Your number isn't linked to an account.\n"
            "Please ask the admin to add your WhatsApp number."
        )
        return str(resp)

    command = body.upper().strip()
    if command == 'HELP':
        reply = _handle_help()
    elif command == 'FIXTURES':
        reply = _handle_fixtures()
    elif command == 'TABLE':
        reply = _handle_table()
    elif command == 'MISSING':
        reply = _handle_missing(user)
    elif command == 'MYPICKS':
        reply = _handle_mypicks(user)
    else:
        reply = _handle_prediction(user, body)

    resp.message(reply)
    return str(resp)


def _handle_help():
    return (
        "Available Commands\n\n"
        "FIXTURES - Upcoming fixtures\n"
        "TABLE - League standings\n"
        "MISSING - Fixtures you haven't predicted\n"
        "MYPICKS - Your submitted predictions\n"
        "HELP - This message\n\n"
        "To predict:\nEngland 2-1 Croatia"
    )


def _handle_fixtures():
    now = datetime.utcnow()
    cutoff = now + timedelta(days=7)
    fixtures = (
        Fixture.query
        .filter(
            Fixture.scheduled_datetime >= now,
            Fixture.scheduled_datetime <= cutoff,
            Fixture.status == 'not_started',
        )
        .order_by(Fixture.scheduled_datetime)
        .limit(10)
        .all()
    )
    if not fixtures:
        return "No upcoming fixtures in the next 7 days."
    lines = ["Upcoming Fixtures\n"]
    for f in fixtures:
        lines.append(f"{f.home_team} v {f.away_team}\n{f.scheduled_datetime.strftime('%d %b %H:%M')} UTC")
    return "\n\n".join(lines)


def _handle_table():
    leaderboard = get_leaderboard()
    if not leaderboard:
        return "No scores recorded yet."
    lines = ["🏆 League Table\n"]
    for i, entry in enumerate(leaderboard, 1):
        lines.append(f"{i}. {entry['user'].username} - {entry['total_points']}")
    return "\n".join(lines)


def _handle_missing(user):
    now = datetime.utcnow()
    upcoming = (
        Fixture.query
        .filter(Fixture.scheduled_datetime >= now, Fixture.status == 'not_started')
        .order_by(Fixture.scheduled_datetime)
        .all()
    )
    predicted_ids = {p.fixture_id for p in user.predictions}
    missing = [f for f in upcoming if f.id not in predicted_ids]

    if not missing:
        return "✅ You're all caught up — predictions in for all upcoming fixtures!"
    lines = ["You still need predictions for:\n"]
    for f in missing[:10]:
        lines.append(f"{f.home_team} v {f.away_team}\n{f.scheduled_datetime.strftime('%d %b %H:%M')} UTC")
    if len(missing) > 10:
        lines.append(f"...and {len(missing) - 10} more. Reply FIXTURES for the full list.")
    return "\n\n".join(lines)


def _handle_mypicks(user):
    predictions = (
        Prediction.query
        .filter_by(user_id=user.id)
        .join(Fixture)
        .order_by(Fixture.scheduled_datetime)
        .all()
    )
    if not predictions:
        return "You have no predictions yet.\n\nTry: England 2-1 Croatia"
    lines = []
    for p in predictions:
        f = p.fixture
        line = f"{f.home_team} {p.predicted_home_score}-{p.predicted_away_score} {f.away_team}"
        if p.points_earned is not None:
            line += f"  ({p.points_earned}pts)"
        lines.append(line)
    return "\n".join(lines)


def _fuzzy_match_team(name, team_names):
    """Return best matching team name at >=70% similarity, or None."""
    if not team_names:
        return None
    result = process.extractOne(name, team_names, scorer=fuzz.token_sort_ratio)
    return result[0] if result and result[1] >= 70 else None


def _parse_prediction(body):
    """Parse 'Team1 X-Y Team2'. Returns (home_raw, home_score, away_score, away_raw) or None."""
    for pattern in (
        r'^(.+?)\s+(\d+)-(\d+)\s+(.+)$',   # England 2-1 Croatia
        r'^(.+?)\s+(\d+)\s+(\d+)\s+(.+)$',  # England 2 1 Croatia
    ):
        m = re.match(pattern, body.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip()
    return None


def _handle_prediction(user, body):
    parsed = _parse_prediction(body)
    if not parsed:
        return (
            "❓ Command not recognised.\n\n"
            "To predict a match try:\nEngland 2-1 Croatia\n\n"
            "Reply HELP for all commands."
        )

    home_raw, home_score, away_score, away_raw = parsed

    if home_score < 0 or away_score < 0 or home_score > 20 or away_score > 20:
        return "❌ Invalid score. Please use realistic values (0–20)."

    now = datetime.utcnow()
    upcoming = (
        Fixture.query
        .filter(Fixture.scheduled_datetime >= now, Fixture.status == 'not_started')
        .all()
    )
    if not upcoming:
        return "No upcoming fixtures available to predict."

    team_names = list({name for f in upcoming for name in (f.home_team, f.away_team)})
    home_match = _fuzzy_match_team(home_raw, team_names)
    away_match = _fuzzy_match_team(away_raw, team_names)

    if not home_match or not away_match:
        unmatched = []
        if not home_match:
            unmatched.append(f"'{home_raw}'")
        if not away_match:
            unmatched.append(f"'{away_raw}'")
        return (
            f"❌ Couldn't match team(s): {' and '.join(unmatched)}\n\n"
            "Reply FIXTURES to see team names."
        )

    fixture = next(
        (f for f in upcoming if f.home_team == home_match and f.away_team == away_match),
        None,
    )
    if not fixture:
        return (
            f"❌ No upcoming fixture for {home_match} v {away_match}.\n\n"
            "Note: home team must come first. Reply FIXTURES to check."
        )

    existing = Prediction.query.filter_by(user_id=user.id, fixture_id=fixture.id).first()
    if existing:
        old = f"{existing.predicted_home_score}-{existing.predicted_away_score}"
        existing.predicted_home_score = home_score
        existing.predicted_away_score = away_score
        existing.predicted_at = datetime.utcnow()
        db.session.commit()
        return (
            f"✏️ Prediction Updated\n\n"
            f"{fixture.home_team} {home_score}-{away_score} {fixture.away_team}\n"
            f"(was {old})"
        )

    prediction = Prediction(
        user_id=user.id,
        fixture_id=fixture.id,
        predicted_home_score=home_score,
        predicted_away_score=away_score,
    )
    db.session.add(prediction)
    db.session.commit()
    return (
        f"✅ Prediction Saved\n\n"
        f"{fixture.home_team} {home_score}-{away_score} {fixture.away_team}"
    )


def send_result_notification_for_fixture(fixture):
    """Send result + all predictions + leaderboard to every WhatsApp user. Idempotent."""
    if fixture.result_notification_sent:
        return

    users_with_wa = User.query.filter(User.whatsapp_number.isnot(None)).all()
    if not users_with_wa:
        return

    # Build the shared body: score, all players' picks, leaderboard
    lines = [
        f"Final Score\n\n"
        f"{fixture.home_team} {fixture.home_score}-{fixture.away_score} {fixture.away_team}\n\n"
        "Predictions:"
    ]
    all_users = User.query.order_by(User.username).all()
    for user in all_users:
        prediction = Prediction.query.filter_by(user_id=user.id, fixture_id=fixture.id).first()
        if not prediction:
            lines.append(f"{user.username}: no prediction")
        else:
            pts = prediction.points_earned or 0
            exact = prediction.predicted_home_score == fixture.home_score and \
                    prediction.predicted_away_score == fixture.away_score
            tick = " ✅" if exact else ""
            lines.append(
                f"{user.username}: {prediction.predicted_home_score}-{prediction.predicted_away_score}"
                f" ({pts}pts){tick}"
            )

    leaderboard = get_leaderboard()
    lines.append("\n🏆 Leaderboard")
    for i, entry in enumerate(leaderboard, 1):
        lines.append(f"{i}. {entry['user'].username} - {entry['total_points']}pts")

    msg = "\n".join(lines)

    for user in users_with_wa:
        try:
            send_whatsapp(user.whatsapp_number, msg)
        except Exception as e:
            logger.error("Result notification failed for %s: %s", user.username, e)

    fixture.result_notification_sent = True
    db.session.commit()
