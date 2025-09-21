"""ResearchAgent class for handling web search, content extraction, summarization, and report generation.

This module encapsulates the core logic for searching sources, extracting relevant content,
summarizing it, and generating structured reports using Gemini and Tavily APIs.
"""

import google.generativeai as genai
from tavily import TavilyClient
import trafilatura
from readability.readability import Document
import requests
from pypdf import PdfReader
from io import BytesIO
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ResearchAgent:
    def __init__(self, gemini_api_key: str, tavily_api_key: str):
        """Initialize the ResearchAgent with API keys.

        Args:
            gemini_api_key (str): API key for Gemini LLM.
            tavily_api_key (str): API key for Tavily search.
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.tavily = TavilyClient(api_key=tavily_api_key)
        logger.info("ResearchAgent initialized")

    def extract_relevant_content(self, url: str, query: str) -> str | None:
        """Extract relevant content from a URL using trafilatura or readability for HTML, or pypdf for PDFs.

        Uses the LLM to filter only relevant information to avoid token overload.

        Args:
            url (str): URL of the content to extract.
            query (str): User query for relevance filtering.

        Returns:
            str | None: Relevant extracted text or None if extraction fails.
        """
        try:
            if url.lower().endswith('.pdf'):
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                pdf = PdfReader(BytesIO(resp.content))
                text = ''
                for page in pdf.pages:
                    text += page.extract_text() + '\n'
            else:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    text = trafilatura.extract(downloaded)
                    if not text:
                        resp = requests.get(url, timeout=10)
                        resp.raise_for_status()
                        doc = Document(resp.text)
                        text = doc.summary()
                else:
                    logger.warning(f"Failed to fetch {url}")
                    return None

            # Limit text to avoid exceeding Gemini free-tier token limits
            if len(text) > 50000:
                text = text[:50000]
            extract_prompt = f"Extract only the most relevant information to the query '{query}' from this text. Be concise and include key points only, nothing extra or irrelevant:"
            response = self.model.generate_content(extract_prompt + "\n\n" + text)
            logger.debug(f"Extracted relevant content from {url}")
            return response.text
        except Exception as e:
            logger.warning(f"Error extracting content from {url}: {str(e)}")
            return None

    def search_sources(self, query: str, max_results: int = 3) -> list[str]:
        """Search for relevant sources using Tavily API.

        Args:
            query (str): User query to search.
            max_results (int): Maximum number of results to return (default: 3).

        Returns:
            list[str]: List of URLs from search results.
        """
        try:
            search_response = self.tavily.search(query=query, max_results=max_results)
            urls = [result['url'] for result in search_response['results']]
            logger.debug(f"Found {len(urls)} sources for query: {query}")
            return urls
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return []

    def summarize_content(self, content: str, query: str) -> str | None:
        """Summarize content using the Gemini LLM.

        Args:
            content (str): Content to summarize.
            query (str): User query for context.

        Returns:
            str | None: Summary text or None if summarization fails.
        """
        try:
            summary_prompt = f"Summarize this relevant content for the query '{query}' in a few key points:"
            response = self.model.generate_content(summary_prompt + "\n\n" + content)
            logger.debug("Generated summary")
            return response.text
        except Exception as e:
            logger.warning(f"Error summarizing content: {str(e)}")
            return None

    def generate_report(self, query: str) -> str:
        """Generate a structured report for the query based on search and summaries.

        Args:
            query (str): User query to generate report for.

        Returns:
            str: Structured report text.

        Raises:
            Exception: If no valid sources are extracted.
        """
        urls = self.search_sources(query)
        extracts = []
        for url in urls:
            content = self.extract_relevant_content(url, query)
            if content:
                extracts.append({'url': url, 'content': content})

        if not extracts:
            raise Exception("No valid sources could be extracted")

        summaries = []
        for ext in extracts:
            summary = self.summarize_content(ext['content'], query)
            if summary:
                summaries.append({'url': ext['url'], 'summary': summary})

        overall_prompt = f"Create a short, structured report for the query '{query}' based on these source summaries. Use bullet points for key findings and include source links at the end:"
        for sumry in summaries:
            overall_prompt += f"\n\nSource: {sumry['url']}\nSummary: {sumry['summary']}"

        response = self.model.generate_content(overall_prompt)
        logger.info(f"Generated report for query: {query}")
        return response.text