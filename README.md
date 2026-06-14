# World Cup Predictions 2026

A Python-based web app where players can predict match results for the 2026 FIFA World Cup, earn points based on accuracy, and compete on a live leaderboard.

## Features

- 🔐 **Secure Login**: Simple username/password authentication for Alex and Phoebe
- 🎯 **Make Predictions**: Submit predictions for upcoming World Cup fixtures before kickoff
- ⚽ **Live Scores**: View live match scores from an external API
- 📊 **Points System**:
  - 5 points for correct exact score
  - 3 points for correct goal difference
  - 2 points for correct result (win/loss/draw)
- 🏆 **Live Leaderboard**: See real-time rankings and statistics
- ⚙️ **Admin Panel**: Manual fixture syncing, result entry, and prediction management
- 💾 **Export Data**: Download predictions as CSV

## Prerequisites

- Python 3.8+
- pip

## Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd world-cup-predictions
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your API key if using live scores API
```

### 5. Initialize Database
```bash
python3
>>> from app import app
>>> from database import init_db
>>> init_db(app)
>>> exit()
```

### 6. Run the Application
```bash
python3 app.py
```

The app will be available at `http://localhost:5000`

## Default Credentials

- **Alex**: username: `Alex`, password: `alex123`
- **Phoebe**: username: `Phoebe`, password: `phoebe123`

## Usage

### 1. Login
Visit `http://localhost:5000` and log in with your credentials

### 2. Make Predictions
- Go to the **Predictions & Results** tab
- For each upcoming fixture, enter your predicted score
- Predictions must be submitted before the match starts (kickoff time)
- You can update your prediction anytime before kickoff

### 3. View Results
- Once a match is completed, the actual score appears
- Your points are automatically calculated based on accuracy
- View detailed breakdown of points earned (exact score, goal difference, or result)

### 4. Check Leaderboard
- Go to the **Leaderboard** tab
- See rankings sorted by total points
- View individual statistics for each player

### 5. Admin Panel
- Go to the **Admin** tab (only accessible to Alex and Phoebe)
- **Sync Fixtures**: Fetch all 2026 World Cup fixtures from the API
- **Sync Results**: Update live match scores from the API
- **Manually Set Scores**: Manually enter match results if API is unavailable
- **Manage Predictions**: View, edit, or delete predictions
- **Export as CSV**: Download all prediction data

## API Integration

The app uses the [api-football.com](https://api-football.com) API (via RapidAPI) to fetch live scores.

### To Enable Live Scores:
1. Sign up at [RapidAPI](https://rapidapi.com)
2. Subscribe to [API-Football](https://rapidapi.com/api-sports/api/api-football)
3. Copy your API key
4. Add it to your `.env` file as `LIVE_SCORES_API_KEY`

### If No API Key:
The app will still work! Use the Admin panel to manually enter match scores.

## Project Structure

```
world-cup-predictions/
├── app.py                  # Main Flask application & routes
├── models.py              # Database models (User, Fixture, Prediction, SyncLog)
├── database.py            # Database initialization
├── auth.py                # Authentication utilities
├── predictions.py         # Point calculation logic
├── api_client.py          # Live scores API integration
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── static/
│   ├── style.css         # All styling
│   └── app.js            # Client-side logic
├── templates/
│   ├── base.html         # Base template with navigation
│   ├── login.html        # Login page
│   ├── predictions.html  # Predictions & results tab
│   ├── leaderboard.html  # Leaderboard tab
│   ├── admin.html        # Admin panel
│   ├── 404.html          # Error pages
│   └── 500.html
└── README.md             # This file
```

## Database Schema

### Users
- username (unique)
- password_hash
- created_at

### Fixtures
- api_id (external API ID)
- home_team, away_team
- scheduled_datetime
- status (not_started, in_progress, completed)
- home_score, away_score
- last_updated

### Predictions
- user_id, fixture_id
- predicted_home_score, predicted_away_score
- predicted_at
- points_earned
- points_breakdown (JSON)

### SyncLog
- sync_type (fixtures, results)
- synced_at
- fixtures_updated
- status, error_message

## Scoring Logic

The app awards points based on prediction accuracy:

1. **Exact Score (5 points)**
   - Predicted score matches actual score exactly

2. **Goal Difference (3 points)**
   - Prediction has correct goal difference but wrong exact score
   - Example: Predicted 3-1, actual is 2-0 (both have +2 goal diff)

3. **Result (2 points)**
   - Predicted correct outcome (win/loss/draw) but wrong score
   - Example: Predicted 2-1 home win, actual is 1-0 home win

Points are mutually exclusive - a prediction gets only the highest applicable category.

## Troubleshooting

### "No fixtures found"
- Go to Admin panel and click "Sync All Fixtures"
- Without an API key, manually add fixtures to the database

### API Key Error
- Check that `LIVE_SCORES_API_KEY` is set in `.env`
- Verify the key is active on RapidAPI
- Check API rate limits (free tier has limits)

### Predictions Won't Save
- Make sure you're before the fixture's kickoff time
- Check that fixture status is "not_started"

### Database Already Exists
To reset the database:
```bash
rm predictions.db
python3 app.py  # Will recreate with default users
```

## Development Notes

- Uses Flask for the web framework (lightweight and simple)
- SQLite for data storage (no database server needed)
- Vanilla HTML/CSS/JavaScript for the frontend (transparent, no complex dependencies)
- Session-based authentication

## Future Enhancements

- Email notifications for match updates
- Prediction statistics and analytics
- Historical leaderboard rankings
- Mobile app
- WebSocket for real-time leaderboard updates

## License

MIT

## Support

For issues or questions, open an issue on the repository.
