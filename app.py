"""Main Flask application for the Research AI Dashboard.

This module sets up the Flask server, defines routes for the web interface,
and integrates with the research agent and database utilities. It loads API
keys from a .env file for secure configuration.
"""

from flask import Flask, render_template, request, jsonify
from research_agent import ResearchAgent
from db_utils import init_db, save_report, get_history
from dotenv import load_dotenv
import os
import logging

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

@app.route('/')
def index():
    """Render the main dashboard page.

    Returns:
        Flask response: The rendered index.html template.
    """
    return render_template('index.html')

@app.route('/research', methods=['POST'])
def research():
    """Handle research query and generate a report.

    Expects a JSON payload with a 'query' field. Uses the ResearchAgent to
    generate a report and saves it to the database.

    Returns:
        JSON response: Report content or error message.
    """
    data = request.json
    query = data.get('query')

    if not query:
        logger.warning("Received empty query in /research endpoint")
        return jsonify({'error': 'Missing query'}), 400

    try:
        agent = get_agent()
        report = agent.generate_report(query)
        save_report(query, report)
        logger.info(f"Generated report for query: {query}")
        return jsonify({'report': report})
    except Exception as e:
        logger.error(f"Error in /research endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

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