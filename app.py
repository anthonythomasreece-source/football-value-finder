import streamlit as st
import requests
import pandas as pd
import json
from google import genai
from google.genai import types

st.set_page_config(page_title="Football Value Finder", layout="wide", page_icon="⚽")

# Initialize Gemini Client & Odds API Key
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]

st.title("⚽ Football Value Finder (All Leagues Scan)")
st.caption("Automated Odds Scanner & Gemini +EV Analyzer across all supported competitions.")

# Master list of football league keys supported by The Odds API
ALL_LEAGUES = {
    "Premier League (UK)": "soccer_epl",
    "EFL Championship (UK)": "soccer_efl_champ",
    "EFL League One (UK)": "soccer_england_league1",
    "EFL League Two (UK)": "soccer_england_league2",
    "Scottish Premiership": "soccer_spl",
    "La Liga (Spain)": "soccer_spain_la_liga",
    "Serie A (Italy)": "soccer_italy_serie_a",
    "Bundesliga (Germany)": "soccer_germany_bundesliga",
    "Ligue 1 (France)": "soccer_france_ligue_one",
    "Eredivisie (Netherlands)": "soccer_netherlands_eredivisie",
    "Primeira Liga (Portugal)": "soccer_portugal_primeira_liga",
    "UEFA Champions League": "soccer_uefa_champs_league",
    "UEFA Europa League": "soccer_uefa_europa_league"
}

def fetch_league_odds(sport_key, region="uk"):
    """Fetches upcoming odds for a specific league."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": region, "markets": "h2h", "oddsFormat": "decimal"}
    res = requests.get(url, params=params)
    return res.json() if res.status_code == 200 else []

def evaluate_with_gemini(home, away, odds, league_name):
    """Sends match info to Gemini for +EV evaluation."""
    prompt = f"""
    Analyze match: {home} vs {away} ({league_name})
    Available Best Market Odds: {home}: {odds.get('home')}, Draw: {odds.get('draw')}, {away}: {odds.get('away')}
    Calculate true probability, fair odds, and expected value (+EV).
    """
    schema = {
        "type": "OBJECT",
        "properties": {
            "recommended_bet": {"type": "STRING"},
            "fair_odds": {"type": "NUMBER"},
            "market_odds": {"type": "NUMBER"},
            "expected_value": {"type": "STRING"},
            "confidence": {"type": "STRING"},
            "reasoning": {"type": "STRING"}
        },
        "required": ["recommended_bet", "fair_odds", "market_odds", "expected_value", "confidence", "reasoning"]
    }
    
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2
            )
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

# Sidebar Controls
st.sidebar.header("Scanner Settings")

# Allow selecting specific leagues OR selecting "All Leagues"
selected_leagues = st.sidebar.multiselect(
    "Select Competitions to Scan",
    options=list(ALL_LEAGUES.keys()),
    default=list(ALL_LEAGUES.keys()),  # Default: All selected
    help="Deselect competitions if you want to speed up scans or save API quota."
)

region = st.sidebar.selectbox("Bookmaker Region", ["uk", "eu", "us", "au"])
run_btn = st.sidebar.button("🚀 Run All-League Value Scan", type="primary")

if run_btn:
    if not selected_leagues:
        st.warning("Please select at least one league to scan.")
        st.stop()

    all_results = []
    
    with st.status("Scanning selected leagues & analyzing value...", expanded=True) as status:
        for league_label in selected_leagues:
            sport_key = ALL_LEAGUES[league_label]
            st.write(f"📡 Fetching market odds for **{league_label}**...")
            
            games = fetch_league_odds(sport_key, region)
            
            if not games:
                st.write(f"⚠️ No active matches found for {league_label}.")
                continue
                
            for g in games[:3]:  # Top 3 fixtures per league to balance speed & API usage
                home, away = g["home_team"], g["away_team"]
                best_odds = {"home": 0.0, "draw": 0.0, "away": 0.0}
                
                for b in g.get("bookmakers", []):
                    for m in b.get("markets", []):
                        if m["key"] == "h2h":
                            for o in m["outcomes"]:
                                if o["name"] == home: best_odds["home"] = max(best_odds["home"], o["price"])
                                elif o["name"] == away: best_odds["away"] = max(best_odds["away"], o["price"])
                                elif o["name"] == "Draw": best_odds["draw"] = max(best_odds["draw"], o["price"])
                
                st.write(f"♊ Gemini processing **{home} vs {away}**...")
                eval_data = evaluate_with_gemini(home, away, best_odds, league_label)
                
                if "error" not in eval_data:
                    all_results.append({
                        "League": league_label,
                        "Match": f"{home} vs {away}",
                        "Recommended Bet": eval_data.get("recommended_bet"),
                        "Market Odds": eval_data.get("market_odds"),
                        "Model Fair Odds": eval_data.get("fair_odds"),
                        "Expected Value": eval_data.get("expected_value"),
                        "Confidence": eval_data.get("confidence"),
                        "Reasoning": eval_data.get("reasoning")
                    })
                    
        status.update(label="All-League Scan Complete!", state="complete", expanded=False)

    # Output Results
    st.subheader("All-League Scan Summary")
    c1, c2 = st.columns(2)
    c1.metric("Competitions Scanned", len(selected_leagues))
    value_count = sum(1 for r in all_results if r["Recommended Bet"].lower() != "no value")
    c2.metric("Total Value Bets Found", value_count)

    if all_results:
        df = pd.DataFrame(all_results)
        st.dataframe(
            df,
            column_config={
                "Market Odds": st.column_config.NumberColumn(format="%.2f"),
                "Model Fair Odds": st.column_config.NumberColumn(format="%.2f"),
                "Reasoning": st.column_config.TextColumn(width="large")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No value bets found matching the criteria across selected competitions.")