/**
 * Transcription Tool - Client-side JavaScript
 */

// Theme Management
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.classList.contains('dark');

    if (isDark) {
        html.classList.remove('dark');
        html.classList.add('light');
        localStorage.setItem('theme', 'light');
    } else {
        html.classList.remove('light');
        html.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }
}

// Listen for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
        if (e.matches) {
            document.documentElement.classList.remove('light');
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
            document.documentElement.classList.add('light');
        }
    }
});

// DOM Elements
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const selectedFile = document.getElementById('selected-file');
const uploadBtn = document.getElementById('upload-btn');

// File Upload Handling
if (uploadArea && fileInput) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('dragover');
        });
    });

    uploadArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        if (file) {
            selectedFile.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
            selectedFile.classList.remove('hidden');
            selectedFile.classList.add('show');
            uploadBtn.disabled = false;
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// --- Job-based Upload Flow ---

// Active SSE connection
let activeEventSource = null;

// Step ordering for progress indicators
const STEP_ORDER = ['queued', 'loading_model', 'converting', 'transcribing'];

/**
 * Submit the upload form, get a job_id back, then connect to SSE for progress.
 */
async function submitUpload(event) {
    event.preventDefault();

    const form = document.getElementById('upload-form');
    const formData = new FormData(form);

    // Show progress section, hide results
    const progressSection = document.getElementById('progress-section');
    const resultsContainer = document.getElementById('results-container');
    progressSection.classList.remove('hidden');
    resultsContainer.innerHTML = '';

    // Disable upload button while processing
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) uploadBtn.disabled = true;

    // Reset progress UI
    resetProgressUI();
    updateProgress(5, 'Uploading file...', 'queued');

    // Scroll to progress section
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Upload failed (${response.status})`);
        }

        const data = await response.json();
        const jobId = data.job_id;

        // Connect to SSE for progress
        connectToJobStream(jobId);

    } catch (err) {
        console.error('Upload failed:', err);
        showToast(err.message || 'Upload failed', 'error');
        progressSection.classList.add('hidden');
        if (uploadBtn) uploadBtn.disabled = false;
    }
}

/**
 * Connect to the SSE endpoint and stream progress updates.
 */
function connectToJobStream(jobId) {
    // Close any existing connection
    if (activeEventSource) {
        activeEventSource.close();
    }

    const eventSource = new EventSource(`/api/jobs/${jobId}/stream`);
    activeEventSource = eventSource;

    eventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data, jobId);
    });

    eventSource.addEventListener('ping', () => {
        // Keepalive, nothing to do
    });

    eventSource.onerror = (err) => {
        console.error('SSE connection error:', err);
        eventSource.close();
        activeEventSource = null;

        // Check if the job completed while we were disconnected
        fetchJobStatus(jobId).then(data => {
            if (data && data.status === 'completed') {
                handleProgressUpdate(data, jobId);
            } else if (data && data.status === 'failed') {
                handleProgressUpdate(data, jobId);
            }
        });
    };
}

/**
 * Handle a progress update from the SSE stream.
 */
function handleProgressUpdate(data, jobId) {
    const { status, progress, message } = data;

    updateProgress(progress, message, status);

    if (status === 'completed') {
        // Close SSE
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        // Fetch the transcription result HTML
        fetchTranscriptionResult(jobId);

    } else if (status === 'failed') {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }
        showToast(data.error || 'Transcription failed', 'error');

        // Hide progress and re-enable upload
        setTimeout(() => {
            document.getElementById('progress-section').classList.add('hidden');
            const uploadBtn = document.getElementById('upload-btn');
            if (uploadBtn) uploadBtn.disabled = false;
        }, 2000);
    }
}

/**
 * Update the progress UI elements.
 */
function updateProgress(percent, message, status) {
    const progressBar = document.getElementById('progress-bar');
    const progressMessage = document.getElementById('progress-message');
    const progressPercent = document.getElementById('progress-percent');
    const progressTitle = document.getElementById('progress-title');

    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressMessage) progressMessage.textContent = message;
    if (progressPercent) progressPercent.textContent = `${percent}%`;

    // Update title based on status
    const titles = {
        'queued': 'Queued...',
        'loading_model': 'Loading AI Model...',
        'converting': 'Converting Audio...',
        'transcribing': 'Transcribing...',
        'completed': 'Complete!',
        'failed': 'Failed',
    };
    if (progressTitle && titles[status]) {
        progressTitle.textContent = titles[status];
    }

    // Update step indicators
    updateStepIndicators(status);
}

/**
 * Update step indicator circles to show completed/active/pending state.
 */
function updateStepIndicators(currentStatus) {
    const currentIndex = STEP_ORDER.indexOf(currentStatus);

    STEP_ORDER.forEach((step, index) => {
        const el = document.getElementById(`step-${step}`);
        if (!el) return;
        const circle = el.querySelector('div');
        const svg = el.querySelector('svg');

        if (index < currentIndex) {
            // Completed step
            circle.className = 'w-8 h-8 rounded-full bg-primary flex items-center justify-center transition-colors';
            svg.className.baseVal = 'w-4 h-4 text-white';
        } else if (index === currentIndex) {
            // Active step
            circle.className = 'w-8 h-8 rounded-full bg-primary/20 ring-2 ring-primary flex items-center justify-center transition-colors';
            svg.className.baseVal = 'w-4 h-4 text-primary';
        } else {
            // Pending step
            circle.className = 'w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-800 flex items-center justify-center transition-colors';
            svg.className.baseVal = 'w-4 h-4 text-gray-400';
        }
    });

    // If completed, mark all as done
    if (currentStatus === 'completed') {
        STEP_ORDER.forEach((step) => {
            const el = document.getElementById(`step-${step}`);
            if (!el) return;
            const circle = el.querySelector('div');
            const svg = el.querySelector('svg');
            circle.className = 'w-8 h-8 rounded-full bg-primary flex items-center justify-center transition-colors';
            svg.className.baseVal = 'w-4 h-4 text-white';
        });
    }
}

/**
 * Reset the progress UI to initial state.
 */
function resetProgressUI() {
    STEP_ORDER.forEach((step) => {
        const el = document.getElementById(`step-${step}`);
        if (!el) return;
        const circle = el.querySelector('div');
        const svg = el.querySelector('svg');
        circle.className = 'w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-800 flex items-center justify-center transition-colors';
        svg.className.baseVal = 'w-4 h-4 text-gray-400';
    });
}

/**
 * Fetch the job status via REST (fallback when SSE disconnects).
 */
async function fetchJobStatus(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        if (response.ok) {
            return await response.json();
        }
    } catch (err) {
        console.error('Failed to fetch job status:', err);
    }
    return null;
}

/**
 * Fetch the completed transcription result as HTML and insert it.
 */
async function fetchTranscriptionResult(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/result?include_timestamps=true`);
        if (!response.ok) throw new Error('Failed to fetch transcription result');

        const html = await response.text();

        // Hide progress, show results
        setTimeout(() => {
            const progressSection = document.getElementById('progress-section');
            progressSection.classList.add('hidden');

            const resultsContainer = document.getElementById('results-container');
            resultsContainer.innerHTML = html;

            // Re-enable upload button
            const uploadBtn = document.getElementById('upload-btn');
            if (uploadBtn) uploadBtn.disabled = false;

            // Process any htmx content in the inserted HTML
            if (window.htmx) {
                htmx.process(resultsContainer);
            }

            // Scroll to results
            const resultsSection = document.getElementById('results-section');
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // Refresh uploads size
            htmx.trigger('#uploads-size', 'load');

            showToast('Transcription complete!', 'success');
        }, 500);

    } catch (err) {
        console.error('Failed to fetch transcription result:', err);
        showToast('Transcription completed but failed to load results', 'error');
        document.getElementById('progress-section').classList.add('hidden');
        const uploadBtn = document.getElementById('upload-btn');
        if (uploadBtn) uploadBtn.disabled = false;
    }
}

// --- Clipboard & Toast ---

/**
 * Copy transcription text to clipboard
 */
function copyTranscription() {
    const transcriptionEl = document.getElementById('transcription-text');
    if (!transcriptionEl) return;

    const text = transcriptionEl.innerText;
    copyToClipboard(text, 'Transcription copied to clipboard!');
}

/**
 * Copy summary text to clipboard
 */
function copySummary() {
    const summaryEl = document.getElementById('summary-text');
    if (!summaryEl) return;

    const text = summaryEl.innerText;
    copyToClipboard(text, 'Summary copied to clipboard!');
}

/**
 * Copy meeting minutes to clipboard
 */
function copyMinutes() {
    const minutesEl = document.getElementById('minutes-text');
    if (!minutesEl) return;

    const text = minutesEl.innerText;
    copyToClipboard(text, 'Meeting minutes copied to clipboard!');
}

/**
 * Copy text to clipboard and show toast
 */
async function copyToClipboard(text, message) {
    try {
        await navigator.clipboard.writeText(text);
        showToast(message, 'success');
    } catch (err) {
        console.error('Failed to copy:', err);
        showToast('Failed to copy to clipboard', 'error');
    }
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'success') {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// HTMX event listeners (for summarize/meeting-minutes that still use HTMX)
document.body.addEventListener('htmx:responseError', (event) => {
    const errorMessage = event.detail.xhr.responseText || 'An error occurred';
    try {
        const errorData = JSON.parse(errorMessage);
        showToast(errorData.detail || 'An error occurred', 'error');
    } catch {
        showToast('An error occurred', 'error');
    }
});

/**
 * End the current session and clean up all files
 */
async function endSession() {
    if (!confirm('End your session? This will delete all uploaded files and transcriptions.')) {
        return;
    }

    // Close any active SSE connection
    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
    }

    try {
        const response = await fetch('/api/session/end', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            const resultsContainer = document.getElementById('results-container');
            if (resultsContainer) {
                resultsContainer.innerHTML = '';
            }

            const progressSection = document.getElementById('progress-section');
            if (progressSection) {
                progressSection.classList.add('hidden');
            }

            const fileInput = document.getElementById('file-input');
            if (fileInput) {
                fileInput.value = '';
            }

            const selectedFile = document.getElementById('selected-file');
            if (selectedFile) {
                selectedFile.classList.add('hidden');
                selectedFile.classList.remove('show');
            }

            const uploadBtn = document.getElementById('upload-btn');
            if (uploadBtn) {
                uploadBtn.disabled = true;
            }

            htmx.trigger('#uploads-size', 'load');

            const message = data.files_deleted > 0
                ? `Session ended. ${data.files_deleted} file(s) cleaned up.`
                : 'Session ended.';
            showToast(message, 'success');
        } else {
            showToast('Failed to end session', 'error');
        }
    } catch (err) {
        console.error('Failed to end session:', err);
        showToast('Failed to end session', 'error');
    }
}
