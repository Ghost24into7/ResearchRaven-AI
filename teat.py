import streamlit as st
import sqlite3
from datetime import datetime
import google.generativeai as genai
from tavily import TavilyClient
import trafilatura
from readability.readability import Document  # Correct import for readability-lxml
import requests
from pypdf import PdfReader
from io import BytesIO

# Initialize database
def init_db():
    conn = sqlite3.connect('research.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY, query TEXT, report TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

st.title("Research AI Agent")

# API keys input in sidebar
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
tavily_api_key = st.sidebar.text_input("Tavily API Key", type="password")

if not gemini_api_key or not tavily_api_key:
    st.warning("Please enter your Gemini and Tavily API keys in the sidebar to proceed.")
else:
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')  # Suitable for free tier
        tavily = TavilyClient(api_key=tavily_api_key)
        conn = init_db()
        
        # Use tabs for Research and History
        tabs = st.tabs(["Research", "History"])
        
        with tabs[0]:
            query = st.text_input("Enter your research query")
            if st.button("Start Research"):
                if query:
                    with st.spinner("Researching..."):
                        try:
                            # Step 1: Use Tavily to find 2-3 useful sources
                            search_response = tavily.search(query=query, max_results=3)
                            urls = [result['url'] for result in search_response['results']]
                            
                            extracts = []
                            for url in urls:
                                try:
                                    if url.lower().endswith('.pdf'):
                                        # Handle PDF
                                        resp = requests.get(url, timeout=10)
                                        resp.raise_for_status()
                                        pdf = PdfReader(BytesIO(resp.content))
                                        text = ''
                                        for page in pdf.pages:
                                            text += page.extract_text() + '\n'
                                    else:
                                        # Handle HTML
                                        downloaded = trafilatura.fetch_url(url)
                                        if downloaded:
                                            text = trafilatura.extract(downloaded)
                                            if not text:
                                                # Fallback to readability-lxml
                                                resp = requests.get(url, timeout=10)
                                                resp.raise_for_status()
                                                doc = Document(resp.text)
                                                text = doc.summary()
                                        else:
                                            st.warning(f"Could not fetch content from {url}. Skipping.")
                                            continue
                                    
                                    # Advanced strategy: Use LLM to extract only relevant info
                                    if len(text) > 50000:  # Limit to avoid token overload
                                        text = text[:50000]
                                    extract_prompt = f"Extract only the most relevant information to the query '{query}' from this text. Be concise and include key points only, nothing extra or irrelevant:"
                                    response = model.generate_content(extract_prompt + "\n\n" + text)
                                    relevant_text = response.text
                                    
                                    extracts.append({'url': url, 'content': relevant_text})
                                except requests.exceptions.RequestException as e:
                                    st.warning(f"Error fetching {url} (possibly blocked): {str(e)}. Skipping.")
                                except Exception as e:
                                    st.warning(f"Unexpected error with {url}: {str(e)}. Skipping.")
                            
                            if not extracts:
                                st.error("No valid sources could be extracted. Please try a different query.")
                            else:
                                # Step 2: Summarize the extracted content using LLM
                                summaries = []
                                for ext in extracts:
                                    try:
                                        summary_prompt = f"Summarize this relevant content for the query '{query}' in a few key points:"
                                        response = model.generate_content(summary_prompt + "\n\n" + ext['content'])
                                        summaries.append({'url': ext['url'], 'summary': response.text})
                                    except Exception as e:
                                        st.warning(f"Error summarizing {ext['url']}: {str(e)}")
                                
                                # Step 3: Create overall structured report
                                overall_prompt = f"Create a short, structured report for the query '{query}' based on these source summaries. Use bullet points for key findings and include source links at the end:"
                                for sum in summaries:
                                    overall_prompt += f"\n\nSource: {sum['url']}\nSummary: {sum['summary']}"
                                
                                response = model.generate_content(overall_prompt)
                                report = response.text
                                
                                # Save to database
                                c = conn.cursor()
                                c.execute("INSERT INTO reports (query, report, timestamp) VALUES (?, ?, ?)",
                                          (query, report, datetime.now().isoformat()))
                                conn.commit()
                                
                                st.success("Research complete! Report generated and saved.")
                                st.markdown(report)
                        except Exception as e:
                            st.error(f"An error occurred during research: {str(e)}")
                else:
                    st.warning("Please enter a query.")
        
        with tabs[1]:
            st.header("Search History")
            c = conn.cursor()
            c.execute("SELECT * FROM reports ORDER BY timestamp DESC")
            rows = c.fetchall()
            if not rows:
                st.info("No history yet. Perform a research query to start.")
            for row in rows:
                with st.expander(f"Query: {row[1]} (Timestamp: {row[3]})"):
                    st.markdown(row[2])
        
        conn.close()
    except Exception as e:
        st.error(f"Failed to initialize the agent: {str(e)}. Check your API keys and dependencies.")
