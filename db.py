import sqlite3
from datetime import datetime
import pandas as pd

DB_FILE = "value_bets.db"

def init_db():
    """Creates the bets table if it does not already exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS value_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            match_name TEXT NOT NULL,
            recommended_bet TEXT NOT NULL,
            market_odds REAL,
            fair_odds REAL,
            expected_value TEXT,
            confidence TEXT,
            reasoning TEXT,
            status TEXT DEFAULT 'Pending',
            result_profit REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def save_value_bet(bet_data):
    """Inserts an identified value bet into SQLite, preventing duplicate entries for the same match/bet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if this exact bet was already logged today
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT id FROM value_bets 
        WHERE match_name = ? AND recommended_bet = ? AND timestamp LIKE ?
    """, (bet_data["Match"], bet_data["Recommended Bet"], f"{today}%"))
    
    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO value_bets (
                timestamp, match_name, recommended_bet, market_odds, 
                fair_odds, expected_value, confidence, reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            bet_data["Match"],
            bet_data["Recommended Bet"],
            bet_data.get("Market Odds"),
            bet_data.get("Model Fair Odds"),
            bet_data.get("Expected Value"),
            bet_data.get("Confidence"),
            bet_data.get("Reasoning")
        ))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def load_historical_bets():
    """Retrieves all logged value bets as a pandas DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM value_bets ORDER BY id DESC", conn)
    conn.close()
    return df