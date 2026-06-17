import logging
import requests
import os
from datetime import datetime
from models import Fixture, SyncLog, db
from predictions import update_all_prediction_points_for_fixture

logger = logging.getLogger(__name__)


class LiveScoresAPIClient:
    """Client for fetching World Cup 2026 fixtures and live scores"""

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.environ.get('LIVE_SCORES_API_KEY')
        self.api_url = api_url or os.environ.get('LIVE_SCORES_API_URL', 'https://api.zafronix.com/fifa/worldcup/v1')
        self.headers = {
            'X-API-Key': self.api_key
        }
        self.season = 2026

    def get_fixtures(self):
        """Fetch all World Cup 2026 fixtures from Zafronix API"""
        url = f"{self.api_url}/matches"
        params = {'year': self.season}
        logger.info("GET %s params=%s headers=%s", url, params, self.headers)
        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        logger.info("Response status: %s", response.status_code)
        logger.debug("Response body: %s", response.text[:2000])
        response.raise_for_status()
        data = response.json()
        fixtures = data.get('data', [])
        logger.info("Fixtures returned by API: %d", len(fixtures))
        return fixtures

    def fetch_and_sync_fixtures(self):
        """Fetch fixtures from Zafronix API and sync to database."""
        try:
            fixtures_data = self.get_fixtures()
        except Exception as e:
            logger.error("Failed to fetch fixtures from API: %s", e)
            return 0

        if not fixtures_data:
            logger.warning("API returned 0 fixtures — nothing synced")
            return 0

        synced_count = 0
        for fixture_data in fixtures_data:
            api_id = str(fixture_data.get('id', ''))
            home_team = fixture_data.get('homeTeam')
            away_team = fixture_data.get('awayTeam')
            date_str = fixture_data.get('date', '')

            if not api_id:
                logger.warning("Skipping fixture with no id: %s", fixture_data)
                continue

            if not home_team or not away_team:
                logger.debug("Skipping fixture %s — teams not yet determined (%s vs %s)", api_id, home_team, away_team)
                continue

            kickoff_utc = fixture_data.get('kickoffUtc') or date_str
            if not kickoff_utc:
                logger.warning("Skipping fixture %s — no date/kickoffUtc field", api_id)
                continue

            try:
                scheduled_datetime = datetime.fromisoformat(kickoff_utc.replace('Z', '+00:00')).replace(tzinfo=None)
            except ValueError as e:
                logger.warning("Skipping fixture %s — could not parse datetime %r: %s", api_id, kickoff_utc, e)
                continue

            fixture = Fixture.query.filter_by(api_id=api_id).first()
            if not fixture:
                fixture = Fixture(
                    api_id=api_id,
                    home_team=home_team,
                    away_team=away_team,
                    scheduled_datetime=scheduled_datetime,
                    status='not_started'
                )
                db.session.add(fixture)
                synced_count += 1
                logger.debug("Added fixture %s: %s vs %s", api_id, home_team, away_team)
            elif fixture.scheduled_datetime != scheduled_datetime:
                fixture.scheduled_datetime = scheduled_datetime
                logger.debug("Updated kickoff time for fixture %s to %s", api_id, scheduled_datetime)

        db.session.commit()
        logger.info("Synced %d new fixtures", synced_count)
        return synced_count

    def fetch_live_scores(self):
        """Fetch live scores and update fixture results"""
        try:
            fixtures_data = self.get_fixtures()
        except Exception as e:
            logger.error("Failed to fetch live scores from API: %s", e)
            return 0

        if not fixtures_data:
            logger.warning("API returned 0 fixtures during live score sync")
            return 0

        updated_count = 0
        for fixture_data in fixtures_data:
            api_id = str(fixture_data.get('id', ''))
            fixture = Fixture.query.filter_by(api_id=api_id).first()

            if not fixture:
                logger.debug("No local fixture found for api_id=%s", api_id)
                continue

            home_score = fixture_data.get('homeScore')
            away_score = fixture_data.get('awayScore')
            new_status = 'completed' if (home_score is not None and away_score is not None) else 'not_started'

            if (fixture.home_score != home_score or
                    fixture.away_score != away_score or
                    fixture.status != new_status):
                was_completed = fixture.status == 'completed'
                fixture.home_score = home_score
                fixture.away_score = away_score
                fixture.status = new_status
                fixture.last_updated = datetime.utcnow()
                updated_count += 1
                logger.info("Updated fixture %s (%s vs %s): %s-%s status=%s",
                            api_id, fixture.home_team, fixture.away_team,
                            home_score, away_score, new_status)

                if new_status == 'completed' and not was_completed:
                    update_all_prediction_points_for_fixture(fixture)

        db.session.commit()
        logger.info("Live score sync complete — %d fixtures updated", updated_count)
        return updated_count

    def log_sync(self, sync_type, fixtures_updated, status='success', error_message=None):
        """Log a sync operation"""
        try:
            log = SyncLog(
                sync_type=sync_type,
                fixtures_updated=fixtures_updated,
                status=status,
                error_message=error_message
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error("Error logging sync: %s", e)
