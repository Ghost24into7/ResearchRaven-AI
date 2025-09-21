"""Database utilities for managing research reports in SQLite.

This module provides functions to initialize the database, save reports,
and retrieve search history.
"""

import sqlite3
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

def init_db() -> None:
    """Initialize the SQLite database and create the reports table if it doesn't exist."""
    try:
        conn = sqlite3.connect('research.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS reports
                     (id INTEGER PRIMARY KEY, query TEXT, report TEXT, timestamp TEXT)''')
        conn.commit()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
    finally:
        conn.close()

def save_report(query: str, report: str) -> None:
    """Save a research report to the database.

    Args:
        query (str): The user query.
        report (str): The generated report text.
    """
    try:
        conn = sqlite3.connect('research.db')
        c = conn.cursor()
        c.execute("INSERT INTO reports (query, report, timestamp) VALUES (?, ?, ?)",
                  (query, report, datetime.now().isoformat()))
        conn.commit()
        logger.debug(f"Saved report for query: {query}")
    except Exception as e:
        logger.error(f"Error saving report: {str(e)}")
        raise
    finally:
        conn.close()

def get_history() -> list[dict]:
    """Retrieve all past reports from the database.

    Returns:
        list[dict]: List of dictionaries containing query, report, and timestamp.
    """
    try:
        conn = sqlite3.connect('research.db')
        c = conn.cursor()
        c.execute("SELECT * FROM reports ORDER BY timestamp DESC")
        rows = c.fetchall()
        logger.debug("Retrieved search history")
        return [{'query': row[1], 'report': row[2], 'timestamp': row[3]} for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}")
        raise
    finally:
        conn.close()