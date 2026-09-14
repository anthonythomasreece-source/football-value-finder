import streamlit as st
import requests
import pandas as pd
import json
from google import genai
from google.genai import types
from db import init_db, save_value_bet, load_historical_bets

# 1. Initialize Database
init_db()

st.set_page_config(page_title="Football Value Finder", layout="wide", page_icon="⚽")

# Initialize Gemini Client & API Keys
gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]

st.title("⚽ Football Value Finder & Tracker")

# Multi-tab Layout
tab_scanner, tab_history = st.tabs(["🔎 Live Scanner", "📊 Bet History & Ledger"])

# ---------------------------------------------------------
# TAB 1: LIVE SCANNER WITH AUTOMATIC LOGGING
# ---------------------------------------------------------
with tab_scanner:
    st.sidebar.header("Scanner Settings")
    league = st.sidebar.selectbox("League", ["soccer_epl", "soccer_efl_champ", "soccer_spain_la_liga", "soccer_germany_bundesliga"])
    region = st.sidebar.selectbox("Region", ["uk", "eu", "us"])
    run_btn = st.sidebar.button("🚀 Run Live Scan", type="primary")

    if run_btn:
        with st.status("Scanning odds & analyzing value...", expanded=True) as status:
            # Fetch odds logic
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": ODDS_API_KEY, "regions": region, "markets": "h2h", "oddsFormat": "decimal"}
            res = requests.get(url, params=params)
            games = res.json() if res.status_code == 200 else []

            results = []
            new_saved_count = 0

            for g in games[:5]:
                home, away = g["home_team"], g["away_team"]
                best_odds = {"home": 0.0, "draw": 0.0, "away": 0.0}
                for b in g.get("bookmakers", []):
                    for m in b.get("markets", []):
                        if m["key"] == "h2h":
                            for o in m["outcomes"]:
                                if o["name"] == home: best_odds["home"] = max(best_odds["home"], o["price"])
                                elif o["name"] == away: best_odds["away"] = max(best_odds["away"], o["price"])
                                elif o["name"] == "Draw": best_odds["draw"] = max(best_odds["draw"], o["price"])

                st.write(f"Evaluating {home} vs {away} with Gemini...")
                
                # Prompt Gemini
                prompt = f"""
                Analyze match: {home} vs {away}
                Best Odds: {home}: {best_odds['home']}, Draw: {best_odds['draw']}, {away}: {best_odds['away']}
                Calculate true probability and find positive EV (+EV) value bets.
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
                    eval_data = json.loads(response.text)
                    
                    if "error" not in eval_data:
                        bet_entry = {"Match": f"{home} vs {away}", **eval_data}
                        results.append(bet_entry)
                        
                        # Save to SQLite if a positive EV bet is identified
                        if eval_data.get("recommended_bet", "").lower() != "no value":
                            if save_value_bet(bet_entry):
                                new_saved_count += 1
                except Exception as e:
                    st.error(f"Error evaluating {home} vs {away}: {e}")

            status.update(label=f"Scan Complete! Logged {new_saved_count} new value bets.", state="complete")

        if results:
            st.subheader("Current Scan Results")
            st.dataframe(pd.DataFrame(results), use_container_width=True)

# ---------------------------------------------------------
# TAB 2: HISTORICAL BET DATABASE & ANALYTICS
# ---------------------------------------------------------
with tab_history:
    st.subheader("📚 Saved Value Bets Log")
    df_history = load_historical_bets()
    
    if not df_history.empty:
        col1, col2 = st.columns(2)
        col1.metric("Total Saved Bets", len(df_history))
        pending_count = len(df_history[df_history["status"] == "Pending"])
        col2.metric("Pending Bets", pending_count)
        
        st.dataframe(
            df_history,
            column_config={
                "timestamp": "Date Identified",
                "match_name": "Match",
                "recommended_bet": "Selection",
                "market_odds": st.column_config.NumberColumn("Market Odds", format="%.2f"),
                "fair_odds": st.column_config.NumberColumn("Fair Odds", format="%.2f"),
                "expected_value": "Expected Value",
                "status": "Bet Status"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No value bets saved yet. Run a live scan to automatically populate your database.")