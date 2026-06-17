import logging
import atexit
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = None

_LONDON = ZoneInfo('Europe/London')


def init_scheduler(app):
    """Start the background reminder scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)

    # 9am UK time: daily digest of upcoming fixtures + leaderboard
    _scheduler.add_job(
        func=lambda: _morning_digest_job(app),
        trigger='cron',
        hour=9,
        minute=0,
        timezone=_LONDON,
        id='morning_digest',
        replace_existing=True,
    )
    # Every 30 min: remind users about fixtures kicking off in ~1 hour
    _scheduler.add_job(
        func=lambda: _pre_kickoff_job(app),
        trigger='interval',
        minutes=30,
        id='pre_kickoff',
        replace_existing=True,
    )
    # Every 15 min: send result notifications for games that finished 2.5h+ ago
    _scheduler.add_job(
        func=lambda: _post_match_job(app),
        trigger='interval',
        minutes=15,
        id='post_match',
        replace_existing=True,
    )

    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    logger.info("WhatsApp scheduler started (morning digest, pre-kickoff, post-match)")
    return _scheduler


def _morning_digest_job(app):
    """9am UK: upcoming fixtures in next 24h + current leaderboard."""
    with app.app_context():
        from models import User, Fixture
        from whatsapp import send_whatsapp
        from predictions import get_leaderboard

        now = datetime.utcnow()
        cutoff = now + timedelta(hours=24)
        upcoming = (
            Fixture.query
            .filter(
                Fixture.scheduled_datetime >= now,
                Fixture.scheduled_datetime <= cutoff,
                Fixture.status == 'not_started',
            )
            .order_by(Fixture.scheduled_datetime)
            .all()
        )
        if not upcoming:
            return

        fixture_lines = ["⚽ Today's Fixtures\n"]
        for f in upcoming:
            kickoff_bst = (f.scheduled_datetime + timedelta(hours=1)).strftime('%H:%M BST')
            fixture_lines.append(f"{f.home_team} v {f.away_team}  {kickoff_bst}")

        leaderboard = get_leaderboard()
        table_lines = ["\n🏆 Leaderboard\n"]
        for i, entry in enumerate(leaderboard, 1):
            table_lines.append(f"{i}. {entry['user'].username} - {entry['total_points']}pts")

        msg = "\n".join(fixture_lines + table_lines)

        users = User.query.filter(User.whatsapp_number.isnot(None)).all()
        for user in users:
            try:
                send_whatsapp(user.whatsapp_number, msg)
            except Exception as e:
                logger.error("Morning digest failed for %s: %s", user.username, e)


def _pre_kickoff_job(app):
    """Every 30 min: per-user reminder for fixtures kicking off in ~1 hour.

    Uses a 90-minute window (30–120 min before kickoff) with a kickoff_reminder_sent
    flag to guarantee delivery regardless of when the scheduler happened to start.
    The wide window ensures a 30-minute interval always catches every fixture.
    """
    with app.app_context():
        from models import db, User, Fixture, Prediction
        from whatsapp import send_whatsapp

        now = datetime.utcnow()
        # Wide window: 30–120 min before kickoff. The flag prevents double-sends.
        window_start = now + timedelta(minutes=30)
        window_end = now + timedelta(minutes=120)

        fixtures = (
            Fixture.query
            .filter(
                Fixture.scheduled_datetime >= window_start,
                Fixture.scheduled_datetime <= window_end,
                Fixture.status == 'not_started',
                Fixture.kickoff_reminder_sent == False,
            )
            .all()
        )
        if not fixtures:
            return

        users = User.query.filter(User.whatsapp_number.isnot(None)).all()
        for f in fixtures:
            kickoff_bst = (f.scheduled_datetime + timedelta(hours=1)).strftime('%H:%M BST')
            for user in users:
                prediction = Prediction.query.filter_by(
                    user_id=user.id, fixture_id=f.id
                ).first()
                if prediction:
                    msg = (
                        f"⏰ Kick-off reminder\n\n"
                        f"{f.home_team} v {f.away_team}  {kickoff_bst}\n\n"
                        f"Your prediction: "
                        f"{prediction.predicted_home_score}-{prediction.predicted_away_score}"
                    )
                else:
                    msg = (
                        f"⏰ Kick-off reminder\n\n"
                        f"{f.home_team} v {f.away_team}  {kickoff_bst}\n\n"
                        f"No prediction yet!\n"
                        f"Reply: {f.home_team} 2-1 {f.away_team}"
                    )
                try:
                    send_whatsapp(user.whatsapp_number, msg)
                except Exception as e:
                    logger.error("Pre-kickoff reminder failed for %s / %s: %s", user.username, f.home_team, e)

            # Mark sent so subsequent job runs don't re-send
            f.kickoff_reminder_sent = True
            db.session.commit()


def _post_match_job(app):
    """Every 15 min: send result notifications for completed games 2.5h+ after kickoff."""
    with app.app_context():
        from models import Fixture
        from whatsapp import send_result_notification_for_fixture

        cutoff = datetime.utcnow() - timedelta(hours=2, minutes=30)
        fixtures = (
            Fixture.query
            .filter(
                Fixture.status == 'completed',
                Fixture.result_notification_sent == False,
                Fixture.scheduled_datetime <= cutoff,
            )
            .all()
        )
        for fixture in fixtures:
            send_result_notification_for_fixture(fixture)
