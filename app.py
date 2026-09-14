import streamlit as st
import requests
import pandas as pd
import json
from google import genai
from google.genai import types

st.set_page_config(page_title="Football Value Finder - Deep European Scanner", layout="wide", page_icon="⚽")

# Initialize Gemini Client & Odds API Key
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]

st.title("⚽ Football Value Finder (Comprehensive European Scanner)")
st.caption("Deep-tier scanner across European domestic pyramids down to Tier 3/4 divisions.")

# ---------------------------------------------------------
# COMPREHENSIVE EUROPEAN LEAGUES DICTIONARY
# Maps The Odds API keys down to domestic lower tiers
# ---------------------------------------------------------
EUROPEAN_LEAGUES = {
    # UNITED KINGDOM & IRELAND (Down to Tier 4)
    "UK & Ireland": {
        "English Premier League (Tier 1)": "soccer_epl",
        "EFL Championship (Tier 2)": "soccer_efl_champ",
        "EFL League One (Tier 3)": "soccer_england_league1",
        "EFL League Two (Tier 4)": "soccer_england_league2",
        "Scottish Premiership (Tier 1)": "soccer_spl",
        "Irish Premier Division (Tier 1)": "soccer_ireland_premier_league"
    },
    # SPAIN (Down to Segunda Division / Tier 2)
    "Spain": {
        "La Liga (Tier 1)": "soccer_spain_la_liga",
        "La Liga 2 / Segunda (Tier 2)": "soccer_spain_segunda_division"
    },
    # GERMANY (Down to 3. Liga / Tier 3)
    "Germany": {
        "Bundesliga (Tier 1)": "soccer_germany_bundesliga",
        "2. Bundesliga (Tier 2)": "soccer_germany_bundesliga2",
        "3. Liga (Tier 3)": "soccer_germany_3liga"
    },
    # ITALY (Down to Serie B / Tier 2)
    "Italy": {
        "Serie A (Tier 1)": "soccer_italy_serie_a",
        "Serie B (Tier 2)": "soccer_italy_serie_b"
    },
    # FRANCE (Down to Ligue 2 / Tier 2)
    "France": {
        "Ligue 1 (Tier 1)": "soccer_france_ligue_one",
        "Ligue 2 (Tier 2)": "soccer_france_ligue_two"
    },
    # BENELUX
    "Benelux": {
        "Eredivisie Netherlands (Tier 1)": "soccer_netherlands_eredivisie",
        "Eerste Divisie Netherlands (Tier 2)": "soccer_netherlands_eerste_divisie",
        "Belgian Pro League (Tier 1)": "soccer_belgium_first_div"
    },
    # CENTRAL & EASTERN EUROPE
    "Central & Eastern Europe": {
        "Primeira Liga Portugal (Tier 1)": "soccer_portugal_primeira_liga",
        "Süper Lig Turkey (Tier 1)": "soccer_turkey_super_league",
        "Austrian Bundesliga (Tier 1)": "soccer_austria_bundesliga",
        "Swiss Super League (Tier 1)": "soccer_switzerland_super_league",
        "Superliga Denmark (Tier 1)": "soccer_denmark_superliga",
        "Allsvenskan Sweden (Tier 1)": "soccer_sweden_allsvenskan",
        "Eliteserien Norway (Tier 1)": "soccer_norway_eliteserien",
        "Ekstraklasa Poland (Tier 1)": "soccer_poland_ekstraklasa",
        "Super League Greece (Tier 1)": "soccer_greece_super_league"
    },
    # UEFA COMPETITIONS
    "UEFA European Competitions": {
        "UEFA Champions League": "soccer_uefa_champs_league",
        "UEFA Europa League": "soccer_uefa_europa_league",
        "UEFA Europa Conference League": "soccer_uefa_europa_conference_league"
    }
}

def fetch_league_odds(sport_key, region="uk"):
    """Fetches market odds for a specific league key."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": region, "markets": "h2h", "oddsFormat": "decimal"}
    try:
        res = requests.get(url, params=params, timeout=10)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

def evaluate_with_gemini(home, away, odds, league_name):
    """Evaluates match odds using Gemini 2.5 Flash."""
    prompt = f"""
    Analyze match: {home} vs {away} ({league_name})
    Available Market Odds: {home}: {odds.get('home')}, Draw: {odds.get('draw')}, {away}: {odds.get('away')}
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

# ---------------------------------------------------------
# SIDEBAR CONTROLS & REGION SELECTION
# ---------------------------------------------------------
st.sidebar.header("Scan Parameters")

# Region selector
region_choice = st.sidebar.selectbox("Bookmaker Odds Region", ["uk", "eu", "us", "au"])

# Multi-select category filter
st.sidebar.subheader("Select Regions / Pyramids")
selected_categories = st.sidebar.multiselect(
    "Filter Categories",
    options=list(EUROPEAN_LEAGUES.keys()),
    default=list(EUROPEAN_LEAGUES.keys())
)

# Flatten selected leagues into a target list
active_leagues_to_scan = {}
for cat in selected_categories:
    active_leagues_to_scan.update(EUROPEAN_LEAGUES[cat])

st.sidebar.caption(f"Total Active Leagues Selected: **{len(active_leagues_to_scan)}**")
run_btn = st.sidebar.button("🚀 Run Comprehensive Scan", type="primary")

# ---------------------------------------------------------
# MAIN SCANNER ENGINE
# ---------------------------------------------------------
if run_btn:
    if not active_leagues_to_scan:
        st.warning("Please select at least one region/category in the sidebar.")
        st.stop()

    all_results = []
    
    with st.status("Scanning deep European leagues and calculating value...", expanded=True) as status:
        for league_label, sport_key in active_leagues_to_scan.items():
            st.write(f"📡 Scanning **{league_label}**...")
            games = fetch_league_odds(sport_key, region=region_choice)
            
            if not games:
                st.write(f"ℹ️ No active market fixtures for {league_label}.")
                continue
                
            for g in games[:2]:  # Scanning top 2 fixtures per league to optimize runtime across ~30 divisions
                home, away = g["home_team"], g["away_team"]
                best_odds = {"home": 0.0, "draw": 0.0, "away": 0.0}
                
                for b in g.get("bookmakers", []):
                    for m in b.get("markets", []):
                        if m["key"] == "h2h":
                            for o in m["outcomes"]:
                                if o["name"] == home: best_odds["home"] = max(best_odds["home"], o["price"])
                                elif o["name"] == away: best_odds["away"] = max(best_odds["away"], o["price"])
                                elif o["name"] == "Draw": best_odds["draw"] = max(best_odds["draw"], o["price"])
                
                st.write(f"♊ Gemini processing: **{home} vs {away}** ({league_label})...")
                eval_data = evaluate_with_gemini(home, away, best_odds, league_label)
                
                if "error" not in eval_data:
                    all_results.append({
                        "League / Division": league_label,
                        "Match": f"{home} vs {away}",
                        "Recommended Bet": eval_data.get("recommended_bet"),
                        "Market Odds": eval_data.get("market_odds"),
                        "Model Fair Odds": eval_data.get("fair_odds"),
                        "Expected Value": eval_data.get("expected_value"),
                        "Confidence": eval_data.get("confidence"),
                        "Reasoning": eval_data.get("reasoning")
                    })
                    
        status.update(label="Deep European Scan Complete!", state="complete", expanded=False)

    # ---------------------------------------------------------
    # DISPLAY RESULTS METRICS & TABLE
    # ---------------------------------------------------------
    st.subheader("Deep Scan Value Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Leagues Scanned", len(active_leagues_to_scan))
    c2.metric("Fixtures Processed", len(all_results))
    value_count = sum(1 for r in all_results if r["Recommended Bet"].lower() != "no value")
    c3.metric("Positive EV Bets Found", value_count)

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
        st.info("No value bets found matching the model's threshold across the selected divisions.")