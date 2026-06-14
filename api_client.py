import requests
import os
from datetime import datetime
from models import Fixture, SyncLog, db
from predictions import update_all_prediction_points_for_fixture
from fixtures_fallback import WORLD_CUP_2026_FIXTURES

class LiveScoresAPIClient:
    """Client for fetching World Cup 2026 fixtures and live scores"""

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.environ.get('LIVE_SCORES_API_KEY')
        self.api_url = api_url or os.environ.get('LIVE_SCORES_API_URL', 'https://v3.football.api-sports.io')
        self.headers = {
            'x-apisports-key': self.api_key
        }
        self.league_id = 1  # FIFA World Cup
        self.season = 2026

    def get_fixtures(self):
        """Fetch all World Cup 2026 fixtures from API"""
        try:
            url = f"{self.api_url}/fixtures"
            params = {
                'league': self.league_id,
                'season': self.season
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get('response', [])
        except Exception as e:
            print(f"Error fetching fixtures from API: {e}")
            return []

    def fetch_and_sync_fixtures(self):
        """Fetch fixtures from API and sync to database. Falls back to hardcoded fixtures if API fails."""
        try:
            fixtures_data = self.get_fixtures()
            if not fixtures_data:
                print("API returned no fixtures. Using fallback fixtures...")
                return self.sync_fallback_fixtures()

            synced_count = 0
            for fixture_data in fixtures_data:
                api_id = str(fixture_data.get('fixture', {}).get('id'))
                home_team = fixture_data.get('teams', {}).get('home', {}).get('name', 'Unknown')
                away_team = fixture_data.get('teams', {}).get('away', {}).get('name', 'Unknown')

                try:
                    scheduled_datetime = datetime.fromisoformat(
                        fixture_data.get('fixture', {}).get('date', '').replace('Z', '+00:00')
                    )
                except:
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

            db.session.commit()
            return synced_count

        except Exception as e:
            print(f"Error syncing fixtures from API: {e}. Using fallback fixtures...")
            return self.sync_fallback_fixtures()

    def sync_fallback_fixtures(self):
        """Load hardcoded World Cup 2026 fixtures as fallback"""
        try:
            synced_count = 0
            for idx, fixture_data in enumerate(WORLD_CUP_2026_FIXTURES):
                api_id = f"fallback_{idx}"

                fixture = Fixture.query.filter_by(api_id=api_id).first()
                if not fixture:
                    fixture = Fixture(
                        api_id=api_id,
                        home_team=fixture_data['home_team'],
                        away_team=fixture_data['away_team'],
                        scheduled_datetime=fixture_data['scheduled_datetime'],
                        status='not_started'
                    )
                    db.session.add(fixture)
                    synced_count += 1

            db.session.commit()
            return synced_count
        except Exception as e:
            print(f"Error loading fallback fixtures: {e}")
            return 0

    def fetch_live_scores(self):
        """Fetch live scores and update fixture results"""
        try:
            fixtures_data = self.get_fixtures()
            if not fixtures_data:
                return 0

            updated_count = 0
            for fixture_data in fixtures_data:
                api_id = str(fixture_data.get('fixture', {}).get('id'))
                fixture = Fixture.query.filter_by(api_id=api_id).first()

                if not fixture:
                    continue

                # Update fixture status and scores
                fixture_status = fixture_data.get('fixture', {}).get('status', {})
                status_code = fixture_status.get('short', '')

                if status_code in ['NS', 'PST']:
                    new_status = 'not_started'
                elif status_code in ['1H', '2H', 'HT', 'BR', 'P']:
                    new_status = 'in_progress'
                elif status_code in ['FT', 'ET', 'PEN', 'AET']:
                    new_status = 'completed'
                else:
                    new_status = fixture.status

                # Update scores if they exist
                goals = fixture_data.get('goals', {})
                home_score = goals.get('home')
                away_score = goals.get('away')

                if home_score is not None and away_score is not None:
                    if (fixture.home_score != home_score or
                        fixture.away_score != away_score or
                        fixture.status != new_status):
                        fixture.home_score = home_score
                        fixture.away_score = away_score
                        fixture.status = new_status
                        fixture.last_updated = datetime.utcnow()
                        updated_count += 1

                        # Calculate points if fixture just completed
                        if new_status == 'completed' and fixture.status != 'completed':
                            update_all_prediction_points_for_fixture(fixture)

            db.session.commit()
            return updated_count

        except Exception as e:
            print(f"Error fetching live scores: {e}")
            return 0

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
            print(f"Error logging sync: {e}")
