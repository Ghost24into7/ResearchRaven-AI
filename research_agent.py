"""ResearchAgent class for handling web search, content extraction, summarization, and report generation.

This module encapsulates the core logic for searching sources, extracting relevant content,
summarizing it, and generating structured reports using Gemini and Tavily APIs. Supports
streaming progress updates for real-time UI feedback. If a source fails, it automatically
searches for and uses a replacement source to ensure at least 3 viable sources.
"""

import google.generativeai as genai
from tavily import TavilyClient
import trafilatura
from readability.readability import Document
import requests
from pypdf import PdfReader
from io import BytesIO
import logging
import json
from typing import Dict, Any, Generator, List

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
        self.target_sources = 3  # Target number of viable sources
        logger.info("ResearchAgent initialized")

    def _yield_progress(self, message: str, details: Dict[str, Any] = None) -> Generator[Dict[str, Any], None, None]:
        """Yield a progress event."""
        yield {'type': 'progress', 'message': message, 'details': details or {}}

    def _find_replacement_url(self, original_query: str, failed_url: str) -> str | None:
        """Search for a replacement URL if the original fails.

        Args:
            original_query (str): The original user query.
            failed_url (str): The failed URL for context.

        Returns:
            str | None: A replacement URL or None if no replacement found.
        """
        try:
            # Craft a more specific search query to find an alternative
            replacement_query = f"{original_query} -site:{failed_url.split('/')[2]}"
            search_response = self.tavily.search(query=replacement_query, max_results=2)
            replacements = [result['url'] for result in search_response['results'] if result['url'] != failed_url]
            if replacements:
                logger.debug(f"Found replacement for {failed_url}: {replacements[0]}")
                return replacements[0]
        except Exception as e:
            logger.warning(f"Failed to find replacement for {failed_url}: {str(e)}")
        return None

    def extract_relevant_content(self, url: str, query: str, original_query: str = None) -> tuple[str | None, bool]:
        """Extract relevant content from a URL using trafilatura or readability for HTML, or pypdf for PDFs.

        If extraction fails, attempts to find and use a replacement URL.

        Args:
            url (str): URL of the content to extract.
            query (str): User query for relevance filtering.
            original_query (str): Original user query for replacement search.

        Returns:
            tuple[str | None, bool]: (relevant_text, was_replaced) where was_replaced is True if a replacement was used.
        """
        was_replaced = False
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            if url.lower().endswith('.pdf'):
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                pdf = PdfReader(BytesIO(resp.content))
                text = ''
                for page in pdf.pages:
                    text += page.extract_text() + '\n'
            else:
                # Use requests instead of trafilatura.fetch_url to support headers
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                text = trafilatura.extract(resp.text)
                if not text:
                    doc = Document(resp.text)
                    text = doc.summary()
                if not text:
                    raise ValueError("No content extracted from HTML")

            # Limit text to avoid exceeding Gemini free-tier token limits
            if len(text) > 50000:
                text = text[:50000]
            extract_prompt = f"Extract only the most relevant information to the query '{query}' from this text. Be concise and include key points only, nothing extra or irrelevant:"
            response = self.model.generate_content(extract_prompt + "\n\n" + text)
            logger.debug(f"Extracted relevant content from {url}")
            return response.text, was_replaced
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 404]:
                logger.warning(f"HTTP error {e.response.status_code} for {url}. Attempting replacement...")
                replacement = self._find_replacement_url(original_query or query, url)
                if replacement:
                    logger.info(f"Using replacement URL for {url}: {replacement}")
                    return self.extract_relevant_content(replacement, query, original_query), True
                else:
                    logger.warning(f"No replacement found for {url}")
                    return None, False
            else:
                logger.warning(f"HTTP error extracting content from {url}: {str(e)}")
                return None, False
        except Exception as e:
            logger.warning(f"Error extracting content from {url}: {str(e)}")
            replacement = self._find_replacement_url(original_query or query, url)
            if replacement:
                logger.info(f"Using replacement URL for {url}: {replacement}")
                return self.extract_relevant_content(replacement, query, original_query), True
            else:
                logger.warning(f"No replacement found for {url}")
                return None, False

    def search_sources(self, query: str, max_results: int = 5) -> List[str]:
        """Search for relevant sources using Tavily API.

        Args:
            query (str): User query to search.
            max_results (int): Maximum number of results to return (default: 5).

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

    def generate_report_stream(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """Generate a structured report with streaming progress updates.

        Ensures at least self.target_sources viable sources by replacing failures.
        Tailors the final report specifically to the user's query.

        Args:
            query (str): User query to generate report for.

        Yields:
            Dict[str, Any]: Progress or report events.
        """
        yield from self._yield_progress("🔍 Searching for relevant sources...")
        
        candidate_urls = self.search_sources(query, max_results=5)
        if not candidate_urls:
            yield from self._yield_progress("⚠️ No sources found. Generating report with limited data...")
            overall_prompt = f"Tailor a short, structured report to directly answer the user's query: '{query}'. Use bullet points for key findings. Note limited information. Format in Markdown:"
            response = self.model.generate_content(overall_prompt)
            yield {'type': 'report', 'report': response.text}
            return

        yield from self._yield_progress("✅ Sources found. Now extracting content...", {'urls': candidate_urls[:3]})

        extracts = []
        processed_count = 0
        for url in candidate_urls:
            if len(extracts) >= self.target_sources:
                break
            yield from self._yield_progress(f"📄 Extracting from source {len(extracts) + 1}: {url}")
            content, replaced = self.extract_relevant_content(url, query, query)
            if content:
                extracts.append({'url': url if not replaced else f"Replacement for original: {url}", 'content': content})
                yield from self._yield_progress(f"✅ Extracted from {url}" + (" (replacement used)" if replaced else ""))
            processed_count += 1

        # Try additional candidates if needed
        while len(extracts) < self.target_sources and processed_count < len(candidate_urls):
            remaining_url = candidate_urls[processed_count]
            yield from self._yield_progress(f"📄 Trying additional source {len(extracts) + 1}/{self.target_sources}: {remaining_url}")
            content, replaced = self.extract_relevant_content(remaining_url, query, query)
            if content:
                extracts.append({'url': remaining_url if not replaced else f"Replacement for original: {remaining_url}", 'content': content})
                yield from self._yield_progress(f"✅ Extracted from {remaining_url}" + (" (replacement used)" if replaced else ""))
            processed_count += 1

        if not extracts:
            yield from self._yield_progress("⚠️ No valid content extracted. Generating report with limited information...")
            overall_prompt = f"Tailor a short, structured report to directly answer the user's query: '{query}'. Use bullet points for key findings and note that no sources were successfully extracted. Format in Markdown:"
            response = self.model.generate_content(overall_prompt)
            yield {'type': 'report', 'report': response.text}
            return

        yield from self._yield_progress("📝 Summarizing extracted content...")

        summaries = []
        for ext in extracts:
            yield from self._yield_progress(f"📝 Summarizing {ext['url']}...")
            summary = self.summarize_content(ext['content'], query)
            if summary:
                summaries.append({'url': ext['url'], 'summary': summary})
                yield from self._yield_progress(f"✅ Summarized {ext['url']}")

        yield from self._yield_progress("✨ Generating your personalized report...")

        # Tailored prompt to directly answer the user's query
        overall_prompt = f"Tailor a short, structured report to directly answer the user's query: '{query}'. Focus on the most relevant key findings from these source summaries. Use bullet points for insights, explanations, and recommendations specific to this question. Include source links at the end. Format in Markdown for better readability:"
        for sumry in summaries:
            overall_prompt += f"\n\nSource: {sumry['url']}\nSummary: {sumry['summary']}"

        response = self.model.generate_content(overall_prompt)
        report = response.text
        logger.info(f"Generated tailored report for query: {query}")
        
        yield {'type': 'report', 'report': report}

    def generate_report(self, query: str) -> str:
        """Legacy synchronous method for generating reports (non-streaming)."""
        for event in self.generate_report_stream(query):
            if event['type'] == 'report':
                return event['report']
        raise Exception("Failed to generate report")