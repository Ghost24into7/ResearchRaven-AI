/**
 * Client-side JavaScript for the Research AI Dashboard.
 * Handles user interactions, API calls, and dynamic content updates.
 */
document.addEventListener('DOMContentLoaded', function() {
    const startResearchBtn = document.getElementById('start-research');
    const queryInput = document.getElementById('query');
    const geminiKeyInput = document.getElementById('gemini_api_key');
    const tavilyKeyInput = document.getElementById('tavily_api_key');
    const researchResult = document.getElementById('research-result');
    const researchSpinner = document.getElementById('research-spinner');
    const historyList = document.getElementById('history-list');
    const historyTabBtn = document.getElementById('history-tab');

    /**
     * Handle research button click to initiate a new research query.
     */
    startResearchBtn.addEventListener('click', function() {
        const query = queryInput.value.trim();
        const gemini_api_key = geminiKeyInput.value.trim();
        const tavily_api_key = tavilyKeyInput.value.trim();

        if (!query || !gemini_api_key || !tavily_api_key) {
            alert('Please enter a query and both API keys.');
            return;
        }

        researchResult.innerHTML = '';
        researchSpinner.style.display = 'block';

        fetch('/research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, gemini_api_key, tavily_api_key })
        })
        .then(response => response.json())
        .then(data => {
            researchSpinner.style.display = 'none';
            if (data.error) {
                researchResult.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            } else {
                researchResult.innerHTML = `<div class="alert alert-success"><pre>${data.report}</pre></div>`;
            }
        })
        .catch(error => {
            researchSpinner.style.display = 'none';
            researchResult.innerHTML = `<div class="alert alert-danger">Error: ${error}</div>`;
        });
    });

    /**
     * Load and display search history from the server.
     */
    function loadHistory() {
        fetch('/history')
        .then(response => response.json())
        .then(data => {
            historyList.innerHTML = '';
            if (data.error) {
                historyList.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            } else if (data.history.length === 0) {
                historyList.innerHTML = '<div class="alert alert-info">No history yet. Perform a research query to start.</div>';
            } else {
                data.history.forEach(item => {
                    const accordionItem = `
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${item.timestamp.replace(/[:.-]/g, '')}">
                                    Query: ${item.query} (Timestamp: ${item.timestamp})
                                </button>
                            </h2>
                            <div id="collapse${item.timestamp.replace(/[:.-]/g, '')}" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <pre>${item.report}</pre>
                                </div>
                            </div>
                        </div>
                    `;
                    historyList.innerHTML += accordionItem;
                });
            }
        })
        .catch(error => {
            historyList.innerHTML = `<div class="alert alert-danger">Error loading history: ${error}</div>`;
        });
    }

    /**
     * Load history when the History tab is shown.
     */
    historyTabBtn.addEventListener('shown.bs.tab', loadHistory);
});