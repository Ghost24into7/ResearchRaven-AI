"""Main Flask application for the ResearchRaven-AI.

This module sets up the Flask server, defines routes for the web interface,
and integrates with the research agent and database utilities. API keys are
loaded from a .env file for secure configuration. Supports streaming progress
updates via Server-Sent Events (SSE) for real-time UI animations.
"""

from flask import Flask, render_template, request, Response, jsonify
from research_agent import ResearchAgent
from db_utils import init_db, save_report, get_history
from dotenv import load_dotenv
import os
import logging
from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime

# Configure logging for better debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize research agent (lazy-loaded with API keys)
agent = None

def get_agent():
    """Initialize or retrieve the ResearchAgent singleton.

    Returns:
        ResearchAgent: The initialized agent with API keys from .env.
    Raises:
        ValueError: If API keys are missing in .env file.
    """
    global agent
    if agent is None:
        gemini_key = os.getenv('GEMINI_API_KEY')
        tavily_key = os.getenv('TAVILY_API_KEY')
        if not gemini_key or not tavily_key:
            raise ValueError("GEMINI_API_KEY or TAVILY_API_KEY missing in .env file")
        agent = ResearchAgent(gemini_key, tavily_key)
    return agent

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect('research.db')
    try:
        yield conn
    finally:
        conn.close()

@app.route('/')
def index():
    """Render the main dashboard page.

    Returns:
        Flask response: The rendered index.html template.
    """
    return render_template('index.html')

@app.route('/research', methods=['POST'])
def research():
    """Handle research query and stream progress updates via SSE.

    Expects a JSON payload with a 'query' field. Streams progress messages
    for real-time UI updates, generates the report, and saves it to the database.

    Returns:
        Streaming response: SSE events with progress and final report.
    """
    data = request.json
    query = data.get('query')

    if not query:
        logger.warning("Received empty query in /research endpoint")
        return jsonify({'error': 'Missing query'}), 400

    def generate_events():
        try:
            agent = get_agent()
            report = None
            for progress in agent.generate_report_stream(query):
                if progress['type'] == 'progress':
                    yield f"data: {json.dumps(progress)}\n\n"
                elif progress['type'] == 'report':
                    report = progress['report']
                    yield f"data: {json.dumps(progress)}\n\n"
            
            if report:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO reports (query, report, timestamp) VALUES (?, ?, ?)",
                              (query, report, datetime.now().isoformat()))
                    conn.commit()
                logger.info(f"Generated and saved report for query: {query}")
        except Exception as e:
            error_msg = {'type': 'error', 'message': str(e)}
            logger.error(f"Error in /research endpoint: {str(e)}")
            yield f"data: {json.dumps(error_msg)}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/research-stream', methods=['GET'])
def research_stream():
    """Stream research progress for a query via SSE (GET endpoint for EventSource).

    Expects a 'query' parameter in the URL. Streams progress messages
    and saves the report to the database.

    Returns:
        Streaming response: SSE events with progress and final report.
    """
    query = request.args.get('query')

    if not query:
        logger.warning("Received empty query in /research-stream endpoint")
        return jsonify({'error': 'Missing query'}), 400

    def generate_events():
        try:
            agent = get_agent()
            report = None
            for progress in agent.generate_report_stream(query):
                if progress['type'] == 'progress':
                    yield f"data: {json.dumps(progress)}\n\n"
                elif progress['type'] == 'report':
                    report = progress['report']
                    yield f"data: {json.dumps(progress)}\n\n"
            
            if report:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT INTO reports (query, report, timestamp) VALUES (?, ?, ?)",
                              (query, report, datetime.now().isoformat()))
                    conn.commit()
                logger.info(f"Generated and saved report for query: {query}")
        except Exception as e:
            error_msg = {'type': 'error', 'message': str(e)}
            logger.error(f"Error in /research-stream endpoint: {str(e)}")
            yield f"data: {json.dumps(error_msg)}\n\n"

    return Response(generate_events(), mimetype='text/event-stream')

@app.route('/history', methods=['GET'])
def history():
    """Retrieve and return the search history.

    Returns:
        JSON response: List of past queries and reports or error message.
    """
    try:
        history_list = get_history()
        logger.info("Retrieved search history")
        return jsonify({'history': history_list})
    except Exception as e:
        logger.error(f"Error in /history endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    logger.info("Starting Flask application")
    app.run(debug=True, host='0.0.0.0', port=5000)