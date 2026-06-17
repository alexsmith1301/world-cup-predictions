# Using the Zafronix FIFA World Cup API to Retrieve All 2026 World Cup Scores

## Overview

This guide explains how to use the Zafronix FIFA World Cup API to retrieve scores for every match in the 2026 FIFA World Cup.

The primary endpoint required is:

```http
GET /matches?year=2026
```

This endpoint returns all matches for the tournament, including completed results and future fixtures.

Base URL:

```text
https://api.zafronix.com/fifa/worldcup/v1
```

---

## Authentication

Most match-related endpoints require an API key supplied via the `X-API-Key` header.

Example:

```http
X-API-Key: YOUR_API_KEY
```

Example cURL request:

```bash
curl \
  -H "X-API-Key: YOUR_API_KEY" \
  "https://api.zafronix.com/fifa/worldcup/v1/matches?year=2026"
```

---

## Discover Available Tournaments

You can retrieve available tournaments using:

```http
GET /tournaments
```

Example:

```bash
curl https://api.zafronix.com/fifa/worldcup/v1/tournaments
```

Example response:

```json
[
  {
    "year": 2026,
    "host": [
      "United States",
      "Canada",
      "Mexico"
    ]
  }
]
```

---

## Retrieve All Matches

To retrieve every match in the 2026 World Cup:

```http
GET /matches?year=2026
```

Example:

```bash
curl \
  -H "X-API-Key: YOUR_API_KEY" \
  "https://api.zafronix.com/fifa/worldcup/v1/matches?year=2026"
```

Example response:

```json
{
  "year": 2026,
  "count": 104,
  "data": [
    {
      "id": "2026-001",
      "date": "2026-06-11",
      "stage": "group_a",
      "homeTeam": "Mexico",
      "awayTeam": "South Africa",
      "homeScore": 2,
      "awayScore": 0,
      "result": "2-0"
    }
  ]
}
```

---

## Important Match Fields

| Field       | Description               |
| ----------- | ------------------------- |
| `id`        | Unique match identifier   |
| `date`      | Match date                |
| `stage`     | Tournament stage          |
| `homeTeam`  | Home team                 |
| `awayTeam`  | Away team                 |
| `homeScore` | Goals scored by home team |
| `awayScore` | Goals scored by away team |
| `result`    | Formatted scoreline       |

---

## Identifying Completed Matches

Matches that have not yet been played will have `null` scores.

Example fixture:

```json
{
  "homeTeam": "England",
  "awayTeam": "Croatia",
  "homeScore": null,
  "awayScore": null
}
```

Example completed match:

```json
{
  "homeTeam": "Mexico",
  "awayTeam": "South Africa",
  "homeScore": 2,
  "awayScore": 0
}
```

---

## Retrieve Only Completed Results

### JavaScript Example

```javascript
const response = await fetch(
  "https://api.zafronix.com/fifa/worldcup/v1/matches?year=2026",
  {
    headers: {
      "X-API-Key": process.env.ZAFRONIX_API_KEY
    }
  }
);

const data = await response.json();

const completedMatches = data.data.filter(
  match =>
    match.homeScore !== null &&
    match.awayScore !== null
);

console.log(completedMatches);
```

---

## Create a Simple Scores Feed

```javascript
const scores = data.data
  .filter(match => match.homeScore !== null)
  .map(match => ({
    matchId: match.id,
    score: `${match.homeTeam} ${match.homeScore}-${match.awayScore} ${match.awayTeam}`
  }));
```

Example output:

```json
[
  {
    "matchId": "2026-001",
    "score": "Mexico 2-0 South Africa"
  },
  {
    "matchId": "2026-002",
    "score": "South Korea 2-1 Czechia"
  }
]
```

---

## Polling for Updates

For applications that regularly refresh scores, use conditional requests with ETags.

### Initial Request

```http
GET /matches?year=2026
```

Response headers:

```http
ETag: "abc123"
```

### Subsequent Requests

```http
GET /matches?year=2026
If-None-Match: "abc123"
```

If nothing has changed:

```http
304 Not Modified
```

This reduces bandwidth and API usage.

---

## Retrieve Detailed Match Information

Once you have a match ID, you can retrieve additional match details.

```http
GET /matches/{id}
```

Example:

```bash
curl \
  -H "X-API-Key: YOUR_API_KEY" \
  "https://api.zafronix.com/fifa/worldcup/v1/matches/2026-001"
```

Example response:

```json
{
  "id": "2026-001",
  "goals": [
    {
      "minute": 12,
      "scorer": "Player Name",
      "team": "Mexico"
    }
  ]
}
```

Potential additional information includes:

* Goal events
* Scorers
* Assists
* Penalty shootouts
* Captains
* Cards
* Substitutions
* Weather
* Attendance
* Referee information

---

## Recommended Architecture

### Initial Load

Retrieve and store all matches:

```http
GET /matches?year=2026
```

### Periodic Refresh

Refresh every 30–60 seconds:

```http
GET /matches?year=2026
If-None-Match: previous-etag
```

### Detect Changes

Monitor changes to:

* `homeScore`
* `awayScore`
* `attendance`
* `referee`
* Match status fields

### Match Detail View

When a user selects a match:

```http
GET /matches/{id}
```

Use the detailed endpoint to display events, scorers, cards, substitutions, and other match-specific information.

---

## Summary

To retrieve every World Cup score:

1. Obtain an API key.
2. Call:

```http
GET /matches?year=2026
```

3. Filter matches where scores are not `null`.
4. Use ETags for efficient polling.
5. Use:

```http
GET /matches/{id}
```

for detailed match information.

The `/matches?year=2026` endpoint provides everything needed to build a complete World Cup scores service, including fixtures, results, and live tournament updates.
