/**
 * Advanced Client-side JavaScript for the Research AI Dashboard.
 * Handles user interactions, SSE streaming for progress animations, Markdown rendering,
 * and dynamic content updates.
 */
document.addEventListener('DOMContentLoaded', function() {
    const startResearchBtn = document.getElementById('start-research');
    const queryInput = document.getElementById('query');
    const researchResult = document.getElementById('research-result');
    const progressContainer = document.getElementById('progress-container');
    const historyList = document.getElementById('history-list');
    const historyTabBtn = document.getElementById('history-tab');
    const progressSteps = document.querySelectorAll('.progress-step');
    const stepMessages = {
        1: document.getElementById('step-message-1'),
        2: document.getElementById('step-message-2'),
        3: document.getElementById('step-message-3'),
        4: document.getElementById('step-message-4')
    };
    let eventSource = null;

    /**
     * Update progress step visually.
     */
    function updateProgressStep(stepNum, message = '', isComplete = false) {
        const step = document.getElementById(`progress-step-${stepNum}`);
        if (step) {
            step.classList.remove('active', 'complete');
            if (isComplete) {
                step.classList.add('complete');
            } else {
                step.classList.add('active');
            }
            if (stepMessages[stepNum]) {
                stepMessages[stepNum].textContent = message;
            }
            // Animate active line
            const lines = document.querySelectorAll('.progress-line');
            lines.forEach((line, index) => {
                if (index < stepNum - 1) {
                    line.classList.add('active');
                }
            });
        }
    }

    /**
     * Animate fade in/out for current message.
     */
    function animateMessage(element, message) {
        element.classList.add('fade-in-out');
        element.textContent = message;
        setTimeout(() => element.classList.remove('fade-in-out'), 600);
    }

    /**
     * Handle research button click to initiate SSE streaming.
     */
    startResearchBtn.addEventListener('click', function() {
        const query = queryInput.value.trim();

        if (!query) {
            alert('Please enter a research query.');
            return;
        }

        // Clear previous results
        researchResult.innerHTML = '';
        progressContainer.classList.remove('d-none');
        progressSteps.forEach(step => step.classList.remove('active', 'complete'));
        document.querySelectorAll('.progress-line').forEach(line => line.classList.remove('active'));

        // Reset steps
        updateProgressStep(1, '🔍 Discovering relevant links...', false);

        // Close previous EventSource if exists
        if (eventSource) {
            eventSource.close();
        }

        // Use EventSource for streaming
        eventSource = new EventSource(`/research-stream?query=${encodeURIComponent(query)}`);

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                handleProgressEvent(data);
            } catch (e) {
                console.error('Parse error:', e);
                researchResult.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Error: Failed to parse server response</div>`;
            }
        };

        eventSource.onerror = function() {
            eventSource.close();
            progressContainer.classList.add('d-none');
            researchResult.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Error: Connection to server lost</div>`;
        };
    });

    /**
     * Handle incoming progress or report events from stream.
     */
    function handleProgressEvent(data) {
        if (data.type === 'progress') {
            const { message, details } = data;
            console.log('Progress:', message);

            // Update step based on message keywords
            if (message.includes('Searching')) {
                updateProgressStep(1, message);
            } else if (message.includes('Extracting') || message.includes('Extracted') || message.includes('Skipped')) {
                updateProgressStep(2, message);
                if (details.urls) {
                    details.urls.forEach((url, index) => {
                        setTimeout(() => animateMessage(stepMessages[2], `📄 Processing ${index + 1}/${details.urls.length}: ${url}`), index * 1000);
                    });
                }
            } else if (message.includes('Summarizing') || message.includes('Summarized')) {
                updateProgressStep(3, message);
            } else if (message.includes('Generating')) {
                updateProgressStep(4, message);
            }
        } else if (data.type === 'report') {
            eventSource.close();
            progressContainer.classList.add('d-none');
            updateProgressStep(4, '✨ Report generated successfully!', true);
            const reportHtml = marked.parse(data.report); // Render Markdown
            researchResult.innerHTML = `
                <div class="alert alert-success">
                    <h5 class="alert-heading mb-3"><i class="fas fa-check-circle me-2"></i>Research Complete!</h5>
                    <div class="mb-3">Your personalized report is ready. Here's what we found:</div>
                    <div class="report-content">${reportHtml}</div>
                </div>
            `;
        } else if (data.type === 'error') {
            eventSource.close();
            progressContainer.classList.add('d-none');
            researchResult.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Error: ${data.message}</div>`;
        }
    }

    /**
     * Load and display search history from the server.
     */
    function loadHistory() {
        fetch('/history')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('history-list');
            container.innerHTML = '';
            if (data.error) {
                container.innerHTML = `<div class="col-12"><div class="alert alert-danger">${data.error}</div></div>`;
            } else if (data.history.length === 0) {
                container.innerHTML = `<div class="col-12"><div class="alert alert-info">No history yet. Perform a research query to start.</div></div>`;
            } else {
                data.history.forEach((item, index) => {
                    const reportHtml = marked.parse(item.report); // Render Markdown
                    const col = document.createElement('div');
                    col.className = 'col-12';
                    col.innerHTML = `
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${index}">
                                    <i class="fas fa-question-circle me-2"></i>Query: ${item.query}
                                    <span class="ms-auto text-muted small">(${new Date(item.timestamp).toLocaleString()})</span>
                                </button>
                            </h2>
                            <div id="collapse${index}" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <div class="report-content">${reportHtml}</div>
                                </div>
                            </div>
                        </div>
                    `;
                    container.appendChild(col);
                });
            }
        })
        .catch(error => {
            document.getElementById('history-list').innerHTML = `<div class="col-12"><div class="alert alert-danger">Error loading history: ${error}</div></div>`;
        });
    }

    /**
     * Load history when the History tab is shown.
     */
    historyTabBtn.addEventListener('shown.bs.tab', loadHistory);
});