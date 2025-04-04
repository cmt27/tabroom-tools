import sqlite3
import pandas as pd
import io
from config.config import CONFIG
from utils.logger import logger

# Use the database file from configuration
DB_FILE = CONFIG.get("DB_FILE", "judge_data.db")

def get_connection():
    """
    Establish and return a connection to the SQLite database.
    """
    conn = sqlite3.connect(DB_FILE)
    return conn

def create_table():
    """
    Create the judge_records table if it does not exist.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS judge_records (
            JudgeID TEXT,
            JudgeName TEXT,
            Tournament TEXT,
            Lv TEXT,
            Date TEXT,
            Ev TEXT,
            Rd TEXT,
            Aff TEXT,
            Neg TEXT,
            Vote TEXT,
            Result TEXT,
            PRIMARY KEY (JudgeID, Tournament, Date, Rd)
        )
    """)
    conn.commit()
    conn.close()

def count_records() -> int:
    """
    Return the number of records in the judge_records table.
    """
    create_table()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM judge_records")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def refresh_judge_data(df: pd.DataFrame):
    """
    Perform a full refresh: delete all existing judge records and insert new data.
    df: DataFrame with columns [JudgeID, JudgeName, Tournament, Lv, Date, Ev, Rd, Aff, Neg, Vote, Result]
    """
    create_table()
    # Drop duplicates based on the composite key: JudgeID, Tournament, Date, Rd.
    df_unique = df.drop_duplicates(subset=["JudgeID", "Tournament", "Date", "Rd"])
    
    # Log record count before deletion
    pre_count = count_records()
    logger.debug(f"Number of records before refresh: {pre_count}")
    
    conn = get_connection()
    cursor = conn.cursor()
    # Delete all existing records
    cursor.execute("DELETE FROM judge_records")
    conn.commit()
    
    # Insert new data row-by-row
    for index, row in df_unique.iterrows():
        cursor.execute("""
            INSERT INTO judge_records (JudgeID, JudgeName, Tournament, Lv, Date, Ev, Rd, Aff, Neg, Vote, Result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("JudgeID", ""),
            row.get("JudgeName", ""),
            row.get("Tournament", ""),
            row.get("Lv", ""),
            row.get("Date", ""),
            row.get("Ev", ""),
            row.get("Rd", ""),
            row.get("Aff", ""),
            row.get("Neg", ""),
            row.get("Vote", ""),
            row.get("Result", "")
        ))
    conn.commit()
    conn.close()
    
    # Log record count after insertion
    post_count = count_records()
    logger.debug(f"Number of records after refresh: {post_count}")

def export_judge_data_csv() -> str:
    """
    Export the entire judge_records table as a CSV string.
    """
    create_table()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM judge_records", conn)
    conn.close()
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()

def search_judge_data(judge_name: str) -> pd.DataFrame:
    """
    Search for judge records by JudgeName.
    """
    create_table()
    conn = get_connection()
    query = "SELECT * FROM judge_records WHERE JudgeName LIKE ?"
    df = pd.read_sql_query(query, conn, params=(f"%{judge_name}%",))
    conn.close()
    return df