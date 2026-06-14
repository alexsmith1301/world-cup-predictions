from models import Prediction, Fixture, db

def calculate_points(prediction: Prediction) -> dict:
    """
    Calculate points for a prediction based on the fixture result.
    Returns dict with keys: exact, diff, result, total

    Scoring:
    - 5 points for correct exact score
    - 3 points for correct goal difference
    - 2 points for correct result (win/loss/draw)
    """
    fixture = prediction.fixture

    if fixture.home_score is None or fixture.away_score is None:
        return {'exact': 0, 'diff': 0, 'result': 0, 'total': 0}

    points = {'exact': 0, 'diff': 0, 'result': 0, 'total': 0}

    # Check for exact score
    if (prediction.predicted_home_score == fixture.home_score and
        prediction.predicted_away_score == fixture.away_score):
        points['exact'] = 5
        points['total'] += 5

    # Check for correct goal difference (only if not exact)
    if points['exact'] == 0:
        pred_diff = prediction.get_predicted_goal_difference()
        actual_diff = fixture.get_goal_difference()
        if pred_diff == actual_diff:
            points['diff'] = 3
            points['total'] += 3
        else:
            # Check for correct result (only if not exact and not goal diff)
            pred_result = prediction.get_predicted_result()
            actual_result = fixture.get_result()
            if pred_result == actual_result:
                points['result'] = 2
                points['total'] += 2

    return points

def update_prediction_points(prediction: Prediction):
    """Update points for a single prediction after fixture is completed"""
    if prediction.fixture.status == 'completed':
        points = calculate_points(prediction)
        prediction.points_earned = points['total']
        prediction.set_points_breakdown(points)
        db.session.commit()

def update_all_prediction_points_for_fixture(fixture: Fixture):
    """Update points for all predictions on a completed fixture"""
    if fixture.status == 'completed':
        predictions = Prediction.query.filter_by(fixture_id=fixture.id).all()
        for prediction in predictions:
            update_prediction_points(prediction)

def get_user_total_points(user) -> int:
    """Get total points for a user across all predictions"""
    predictions = Prediction.query.filter_by(user_id=user.id).all()
    return sum(p.points_earned or 0 for p in predictions)

def get_user_stats(user) -> dict:
    """Get detailed stats for a user"""
    predictions = Prediction.query.filter_by(user_id=user.id).all()
    completed = [p for p in predictions if p.points_earned is not None]
    total_points = sum(p.points_earned or 0 for p in predictions)

    exact_count = 0
    diff_count = 0
    result_count = 0

    for pred in completed:
        breakdown = pred.get_points_breakdown()
        if breakdown['exact'] > 0:
            exact_count += 1
        elif breakdown['diff'] > 0:
            diff_count += 1
        elif breakdown['result'] > 0:
            result_count += 1

    return {
        'total_points': total_points,
        'predictions_made': len(predictions),
        'predictions_completed': len(completed),
        'exact_correct': exact_count,
        'diff_correct': diff_count,
        'result_correct': result_count
    }

def get_leaderboard() -> list:
    """Get leaderboard with all users and their stats, sorted by points"""
    from models import User
    users = User.query.all()
    leaderboard = []

    for user in users:
        stats = get_user_stats(user)
        leaderboard.append({
            'user': user,
            'total_points': stats['total_points'],
            'predictions_made': stats['predictions_made'],
            'predictions_completed': stats['predictions_completed'],
            'exact_correct': stats['exact_correct'],
            'diff_correct': stats['diff_correct'],
            'result_correct': stats['result_correct']
        })

    # Sort by total points descending
    leaderboard.sort(key=lambda x: x['total_points'], reverse=True)
    return leaderboard
