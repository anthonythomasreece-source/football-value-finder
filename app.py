import os
import requests
from flask import Flask, render_template_string
from dotenv import load_dotenv

# 1. Load Environment Variables securely
load_dotenv()
API_KEY = os.getenv("THE_ODDS_API_KEY")

app = Flask(__name__)

BASE_URL = "https://api.the-odds-api.com/v4/sports"

def calculate_no_vig_probs(home_odds, draw_odds, away_odds):
    """Removes bookmaker margin to derive fair implied probabilities."""
    raw_sum = (1 / home_odds) + (1 / draw_odds) + (1 / away_odds)
    return {
        "home": (1 / home_odds) / raw_sum,
        "draw": (1 / draw_odds) / raw_sum,
        "away": (1 / away_odds) / raw_sum
    }

def get_active_soccer_leagues():
    """Dynamically fetches all currently active soccer leagues to avoid 0-fixture errors."""
    if not API_KEY:
        print("❌ Error: THE_ODDS_API_KEY environment variable is missing.")
        return []
        
    url = f"{BASE_URL}/?apiKey={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ Error fetching sports list: HTTP {response.status_code}")
            return []
        
        sports = response.json()
        # Filter strictly for active soccer/football leagues
        active_soccer = [s["key"] for s in sports if s.get("group") == "Soccer" and s.get("active")]
        return active_soccer
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        return []

def scan_ev_bets():
    if not API_KEY:
        return 0, 0, [], "API Key is missing. Please set THE_ODDS_API_KEY in your .env file."

    leagues_to_scan = get_active_soccer_leagues()
    if not leagues_to_scan:
        return 0, 0, [], "No active soccer leagues found or API key quota exceeded."

    leagues_scanned = 0
    fixtures_processed = 0
    ev_bets = []

    for sport_key in leagues_to_scan:
        leagues_scanned += 1
        url = f"{BASE_URL}/{sport_key}/odds/"
        params = {
            "apiKey": API_KEY,
            "regions": "uk,eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }

        try:
            res = requests.get(url, params=params)
            if res.status_code != 200:
                continue

            fixtures = res.json()
            if not isinstance(fixtures, list):
                continue

            for fixture in fixtures:
                fixtures_processed += 1
                home_team = fixture.get("home_team")
                away_team = fixture.get("away_team")
                bookmakers = fixture.get("bookmakers", [])

                if not bookmakers:
                    continue

                # Find Pinnacle for sharp market benchmark
                pinnacle = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                fair_probs = None
                
                if pinnacle:
                    h2h = next((m for m in pinnacle["markets"] if m["key"] == "h2h"), None)
                    if h2h and len(h2h["outcomes"]) == 3:
                        try:
                            p_home = next(o["price"] for o in h2h["outcomes"] if o["name"] == home_team)
                            p_draw = next(o["price"] for o in h2h["outcomes"] if o["name"] == "Draw")
                            p_away = next(o["price"] for o in h2h["outcomes"] if o["name"] == away_team)
                            fair_probs = calculate_no_vig_probs(p_home, p_draw, p_away)
                        except StopIteration:
                            pass

                # Scan soft books
                for bookie in bookmakers:
                    if bookie["key"] == "pinnacle":
                        continue

                    h2h = next((m for m in bookie["markets"] if m["key"] == "h2h"), None)
                    if not h2h:
                        continue

                    for outcome in h2h["outcomes"]:
                        selection = outcome["name"]
                        book_odds = outcome["price"]

                        if fair_probs:
                            if selection == home_team:
                                true_prob = fair_probs["home"]
                            elif selection == away_team:
                                true_prob = fair_probs["away"]
                            else:
                                true_prob = fair_probs["draw"]

                            ev = (book_odds * true_prob) - 1

                            if ev >= 0.02:  # +2.0% EV Threshold
                                ev_bets.append({
                                    "match": f"{home_team} vs {away_team}",
                                    "league": sport_key.replace("soccer_", "").replace("_", " ").title(),
                                    "bookmaker": bookie["title"],
                                    "selection": selection,
                                    "odds": book_odds,
                                    "fair_odds": round(1 / true_prob, 2),
                                    "ev_percent": f"{round(ev * 100, 2)}%"
                                })
        except Exception as e:
            print(f"Error processing {sport_key}: {e}")

    return leagues_scanned, fixtures_processed, ev_bets, None

# Basic Responsive HTML UI Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>+EV Value Betting Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f4f6f8; color: #333; }
        .card { background: white; padding: 24px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 24px; }
        .stats { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-box { background: #eef2f5; padding: 15px 20px; border-radius: 6px; flex: 1; }
        .stat-number { font-size: 24px; font-weight: bold; color: #0066cc; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .badge { background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 6px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚽ +EV Football Scanner Dashboard</h2>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% else %}
            <div class="stats">
                <div class="stat-box">
                    <div>Leagues Scanned</div>
                    <div class="stat-number">{{ leagues_scanned }}</div>
                </div>
                <div class="stat-box">
                    <div>Fixtures Processed</div>
                    <div class="stat-number">{{ fixtures_processed }}</div>
                </div>
                <div class="stat-box">
                    <div>+EV Bets Found</div>
                    <div class="stat-number">{{ ev_bets|length }}</div>
                </div>
            </div>

            {% if ev_bets %}
                <table>
                    <thead>
                        <tr>
                            <th>Match</th>
                            <th>League</th>
                            <th>Selection</th>
                            <th>Bookmaker</th>
                            <th>Odds</th>
                            <th>Fair Odds</th>
                            <th>Expected Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for bet in ev_bets %}
                        <tr>
                            <td><b>{{ bet.match }}</b></td>
                            <td>{{ bet.league }}</td>
                            <td>{{ bet.selection }}</td>
                            <td>{{ bet.bookmaker }}</td>
                            <td><b>{{ bet.odds }}</b></td>
                            <td>{{ bet.fair_odds }}</td>
                            <td><span class="badge">+{{ bet.ev_percent }}</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% else %}
                <p>No positive EV opportunities found right now across current active leagues.</p>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    scanned, processed, bets, error = scan_ev_bets()
    return render_template_string(
        HTML_TEMPLATE,
        leagues_scanned=scanned,
        fixtures_processed=processed,
        ev_bets=bets,
        error=error
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)