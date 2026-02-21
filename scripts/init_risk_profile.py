
import sqlite3
import json
import datetime

DB_PATH = "data/stock_analyzer.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_risk_profile_table():
    conn = get_connection()
    try:
        # Create table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_risk_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                risk_tolerance_level TEXT,
                total_score INTEGER,
                answer_set TEXT,
                drawdown_emphasis TEXT,
                warning_verbosity TEXT,
                color_intensity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if empty, if so insert default
        row = conn.execute("SELECT count(*) FROM user_risk_profiles").fetchone()
        if row and row[0] == 0:
            print("Inserting default BALANCED profile...")
            # Default: Balanced (Score 5)
            # answers: dummy
            default_answers = {"q1": "unknown"}
            conn.execute("""
                INSERT INTO user_risk_profiles (
                    risk_tolerance_level, total_score, answer_set,
                    drawdown_emphasis, warning_verbosity, color_intensity
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "BALANCED", 5, json.dumps(default_answers),
                "MEDIUM", "STANDARD", "NORMAL"
            ))
            conn.commit()
            print("Default profile created.")
        else:  
            print("Table exists and is not empty.")
            
    except Exception as e:
        print(f"Error initializing table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_risk_profile_table()
