import time
import requests

# ==========================================
# CONFIGURATION
# ==========================================
API_KEY = "YOUR_THE_ODDS_API_KEY"  # Replace with your API key
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Target regions & market parameters
REGIONS = "uk,eu"       # Mandatory parameter to return bookies like Betfair, Bet365, Unibet, etc.
MARKETS = "h2h"         # 1X2 / Match Winner odds
ODDS_FORMAT = "decimal"
MIN_EV_THRESHOLD = 0.02 # 2.0% minimum Positive EV threshold (e.g., 0.02 = 2%)

# Targeted list of European & domestic soccer league keys
LEAGUES_TO_SCAN = [
    "soccer_epl",                       # English Premier League
    "soccer_england_league1",           # EFL League One
    "soccer_england_league2",           # EFL League Two
    "soccer_spain_la_liga",             # La Liga
    "soccer_germany_bundesliga",        # Bundesliga
    "soccer_italy_serie_a",             # Serie A
    "soccer_france_ligue_one",          # Ligue 1
    "soccer_netherlands_eredivisie",    # Eredivisie
    "soccer_portugal_primeira_liga",    # Primeira Liga
    "soccer_belgium_first_div",         # Belgian Pro League
    "soccer_turkey_super_league",       # Süper Lig
    "soccer_austria_bundesliga",        # Austrian Bundesliga
    "soccer_switzerland_super_league",  # Swiss Super League
    "soccer_uefa_champs_league",        # UEFA Champions League
    "soccer_uefa_europa_league"         # UEFA Europa League
]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def calculate_no_vig_probs(home_odds, draw_odds, away_odds):
    """Removes the bookmaker margin to derive true no-vig probabilities."""
    raw_sum = (1 / home_odds) + (1 / draw_odds) + (1 / away_odds)
    return {
        "home": (1 / home_odds) / raw_sum,
        "draw": (1 / draw_odds) / raw_sum,
        "away": (1 / away_odds) / raw_sum
    }

def scan_leagues():
    leagues_scanned = 0
    fixtures_processed = 0
    positive_ev_found = 0
    ev_bets = []

    print("🚀 Starting +EV Football Scanner...\n")

    for sport_key in LEAGUES_TO_SCAN:
        leagues_scanned += 1
        url = f"{BASE_URL}/{sport_key}/odds/"
        
        # Mandatory parameters required by The Odds API
        params = {
            "apiKey": API_KEY,
            "regions": REGIONS,
            "markets": MARKETS,
            "oddsFormat": ODDS_FORMAT
        }

        try:
            response = requests.get(url, params=params)
            
            # API rate limit check
            if response.status_code == 429:
                print(f"⚠️ Rate limit hit on {sport_key}. Sleeping 2 seconds...")
                time.sleep(2)
                continue
            elif response.status_code != 200:
                print(f"❌ Error fetching {sport_key}: HTTP {response.status_code}")
                continue

            fixtures = response.json()
            
            # If empty array returned, log and continue
            if not isinstance(fixtures, list) or len(fixtures) == 0:
                print(f" [–] {sport_key}: 0 active fixtures found in time window.")
                continue

            print(f" [+] {sport_key}: Found {len(fixtures)} active fixtures.")

            # Process each fixture in the league
            for fixture in fixtures:
                fixtures_processed += 1
                home_team = fixture.get("home_team")
                away_team = fixture.get("away_team")
                bookmakers = fixture.get("bookmakers", [])

                if not bookmakers:
                    continue

                # Find sharp reference line (Pinnacle preferred, fallback to market average)
                pinnacle_data = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                
                fair_probs = None
                if pinnacle_data:
                    h2h_market = next((m for m in pinnacle_data["markets"] if m["key"] == "h2h"), None)
                    if h2h_market and len(h2h_market["outcomes"]) == 3:
                        p_home = next(o["price"] for o in h2h_market["outcomes"] if o["name"] == home_team)
                        p_draw = next(o["price"] for o in h2h_market["outcomes"] if o["name"] == "Draw")
                        p_away = next(o["price"] for o in h2h_market["outcomes"] if o["name"] == away_team)
                        fair_probs = calculate_no_vig_probs(p_home, p_draw, p_away)

                # Scan all soft/retail bookmakers against true probability
                for bookie in bookmakers:
                    # Skip sharp benchmark book
                    if bookie["key"] == "pinnacle":
                        continue

                    h2h = next((m for m in bookie["markets"] if m["key"] == "h2h"), None)
                    if not h2h:
                        continue

                    for outcome in h2h["outcomes"]:
                        selection = outcome["name"]
                        book_odds = outcome["price"]

                        # Target probability mapping
                        if fair_probs:
                            if selection == home_team:
                                true_prob = fair_probs["home"]
                            elif selection == away_team:
                                true_prob = fair_probs["away"]
                            else:
                                true_prob = fair_probs["draw"]

                            # Expected Value Calculation: EV = (Odds * True_Prob) - 1
                            ev = (book_odds * true_prob) - 1

                            if ev >= MIN_EV_THRESHOLD:
                                positive_ev_found += 1
                                ev_bets.append({
                                    "match": f"{home_team} vs {away_team}",
                                    "league": sport_key,
                                    "bookmaker": bookie["title"],
                                    "selection": selection,
                                    "odds": book_odds,
                                    "fair_odds": round(1 / true_prob, 2),
                                    "ev_percent": f"{round(ev * 100, 2)}%"
                                })

        except Exception as e:
            print(f"❌ Unexpected error scanning {sport_key}: {e}")

        # Respect request throttling
        time.sleep(0.2)

    # Output Scan Summary
    print("\n" + "=" * 45)
    print(" SCANNING COMPLETE")
    print("=" * 45)
    print(f"Leagues Scanned      = {leagues_scanned}")
    print(f"Fixtures Processed   = {fixtures_processed}")
    print(f"Positive EV Bets Found = {positive_ev_found}")
    print("=" * 45)

    if ev_bets:
        print("\n🎯 Found +EV Opportunities:")
        for bet in ev_bets:
            print(f"• {bet['match']} ({bet['league']})")
            print(f"  Selection: {bet['selection']} @ {bet['odds']} [{bet['bookmaker']}]")
            print(f"  Fair Odds: {bet['fair_odds']} | Expected Value: {bet['ev_percent']}\n")

# Run Scanner
if __name__ == "__main__":
    scan_leagues()