/**
 * Transcription Tool - Client-side JavaScript
 */

// DOM Elements
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const selectedFile = document.getElementById('selected-file');
const uploadBtn = document.getElementById('upload-btn');

// File Upload Handling
if (uploadArea && fileInput) {
    // Drag and drop events
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

    // Handle file drop
    uploadArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    // Handle file selection
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    function handleFileSelect(file) {
        if (file) {
            selectedFile.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
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
 * @param {string} text - Text to copy
 * @param {string} message - Toast message to show
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
 * @param {string} message - Message to display
 * @param {string} type - Toast type (success, error)
 */
function showToast(message, type = 'success') {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Show toast
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    
    // Hide and remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// HTMX event listeners
document.body.addEventListener('htmx:afterRequest', (event) => {
    // Scroll to results after upload
    if (event.detail.pathInfo.requestPath === '/api/upload') {
        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
});

document.body.addEventListener('htmx:responseError', (event) => {
    const errorMessage = event.detail.xhr.responseText || 'An error occurred';
    try {
        const errorData = JSON.parse(errorMessage);
        showToast(errorData.detail || 'An error occurred', 'error');
    } catch {
        showToast('An error occurred', 'error');
    }
});
