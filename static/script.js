// static/script.js

document.addEventListener('DOMContentLoaded', function() {
    // Copy link functionality
    initializeCopyButtons();

    // File upload form enhancements
    initializeFileUpload();

    // Toast notifications for user feedback
    initializeToasts();

    // File deletion functionality
    initializeDeleteButtons();

    // Auto-scroll to upload section
    checkScrollToUpload();
});

function initializeCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-link');

    copyButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('data-target');
            const inputField = document.getElementById(targetId);

            if (!inputField) {
                showToast('Error: Could not find link to copy', 'error');
                return;
            }

            const link = inputField.value;

            // Select the text in the input field
            inputField.select();
            inputField.setSelectionRange(0, 99999); // For mobile devices

            // Try to copy using modern Clipboard API
            navigator.clipboard.writeText(link).then(() => {
                // Visual feedback
                this.innerHTML = '<i class="bi bi-check"></i>';
                this.classList.remove('btn-outline-primary', 'btn-outline-secondary');
                this.classList.add('btn-success');

                // Show success toast
                showToast('Link copied to clipboard!', 'success');

                // Revert button after 2 seconds
                setTimeout(() => {
                    this.innerHTML = '<i class="bi bi-clipboard"></i>';
                    this.classList.remove('btn-success');
                    this.classList.add('btn-outline-primary');
                }, 2000);

            }).catch(err => {
                // Fallback for older browsers
                try {
                    document.execCommand('copy');
                    showToast('Link copied to clipboard!', 'success');
                } catch (fallbackErr) {
                    console.error('Failed to copy: ', err);
                    showToast('Failed to copy link. Please try again.', 'error');
                }
            });
        });
    });
}

function initializeFileUpload() {
    const fileInput = document.getElementById('file');
    const uploadForm = document.getElementById('uploadForm');
    const typeFile = document.getElementById('typeFile');
    const typeFolder = document.getElementById('typeFolder');
    const inputLabel = document.querySelector('label[for="file"]');
    const progressContainer = document.getElementById('compressionProgress');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');

    if (!fileInput || !uploadForm) return;

    // Toggle between File and Folder mode
    const updateMode = () => {
        if (typeFolder.checked) {
            fileInput.setAttribute('webkitdirectory', '');
            fileInput.setAttribute('directory', '');
            fileInput.multiple = true;
            inputLabel.textContent = 'Choose folder';
        } else {
            fileInput.removeAttribute('webkitdirectory');
            fileInput.removeAttribute('directory');
            fileInput.multiple = false;
            inputLabel.textContent = 'Choose file';
        }
        fileInput.value = ''; // Clear selection
    };

    if (typeFile) typeFile.addEventListener('change', updateMode);
    if (typeFolder) typeFolder.addEventListener('change', updateMode);

    // Form submission
    uploadForm.addEventListener('submit', async function(e) {
        if (typeFolder && typeFolder.checked && fileInput.files.length > 0) {
            e.preventDefault(); // Stop normal submission
            
            const files = fileInput.files;
            if (files.length === 0) return;

            const submitButton = this.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="bi bi-clock-history spin"></i> Zipping...';
            
            progressContainer.classList.remove('d-none');
            
            try {
                const zip = new JSZip();
                const folderName = files[0].webkitRelativePath.split('/')[0] || 'folder';
                
                // Add files to zip
                for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    const path = file.webkitRelativePath || file.name;
                    zip.file(path, file);
                    
                    // Update progress
                    const percent = Math.round((i / files.length) * 100);
                    progressBar.style.width = percent + '%';
                    progressText.textContent = `Compressing: ${path.substring(0, 30)}...`;
                }

                progressText.textContent = 'Generating zip file (please wait)...';
                progressBar.classList.add('bg-success');
                
                const content = await zip.generateAsync({type: "blob"}, (metadata) => {
                    if (metadata.percent) {
                        progressBar.style.width = metadata.percent + '%';
                    }
                });

                // Create a new FormData and append the zip
                const formData = new FormData();
                formData.append('file', content, `${folderName}.zip`);
                
                // Add CSRF token
                const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
                if (csrfToken) formData.append('csrf_token', csrfToken);

                progressText.textContent = 'Uploading zip...';
                progressBar.classList.remove('bg-success');
                progressBar.classList.add('bg-primary');

                // Perform the upload via fetch
                const response = await fetch(uploadForm.action, {
                    method: 'POST',
                    body: formData
                });

                if (response.redirected) {
                    window.location.href = response.url;
                } else if (response.ok) {
                    window.location.reload();
                } else {
                    const error = await response.text();
                    showToast('Upload failed: ' + (error || 'Server error'), 'error');
                    resetUploadUI(submitButton, progressContainer);
                }

            } catch (err) {
                console.error('Zipping error:', err);
                showToast('Error compressing folder: ' + err.message, 'error');
                resetUploadUI(submitButton, progressContainer);
            }
        } else {
            // Normal file upload
            const submitButton = this.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Uploading...';
                submitButton.disabled = true;
            }
        }
    });
}

function resetUploadUI(button, progress) {
    button.disabled = false;
    button.innerHTML = '<i class="bi bi-upload me-2"></i>Upload';
    progress.classList.add('d-none');
}


function initializeToasts() {
    // Create toast container if it doesn't exist
    if (!document.getElementById('toast-container')) {
        const toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
}

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;

    const toastId = 'toast-' + Date.now();
    const bgColor = type === 'success' ? 'bg-success' :
                   type === 'error' ? 'bg-danger' :
                   type === 'warning' ? 'bg-warning' : 'bg-info';

    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgColor} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${type === 'success' ? 'bi-check-circle' :
                               type === 'error' ? 'bi-exclamation-circle' :
                               type === 'warning' ? 'bi-exclamation-triangle' : 'bi-info-circle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 3000
    });

    toast.show();

    // Remove toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// Utility function for spinning icons
document.addEventListener('DOMContentLoaded', function() {
    // Add spin animation to Bootstrap icons
    const style = document.createElement('style');
    style.textContent = `
        .bi.spin {
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        /* Smooth transitions for buttons */
        .btn {
            transition: all 0.15s ease-in-out;
        }

        /* Toast animations */
        .toast-container {
            z-index: 9999;
        }
    `;
    document.head.appendChild(style);
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K to focus on search (if you add search later)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) {
            searchInput.focus();
        }
    }
});

// Handle page visibility changes (for better UX)
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        // Page became visible again, you could refresh data here
        console.log('Page is visible');
    }
});

// Auto-scroll to upload section if URL has #upload hash
function checkScrollToUpload() {
    if (window.location.hash === '#upload') {
        const uploadSection = document.getElementById('upload');
        if (uploadSection) {
            // Smooth scroll to upload section
            uploadSection.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });

            // Optional: highlight the section temporarily
            uploadSection.style.transition = 'all 0.5s ease';
            uploadSection.style.boxShadow = '0 0 20px rgba(0, 123, 255, 0.5)';

            setTimeout(() => {
                uploadSection.style.boxShadow = '';
            }, 2000);
        }
    }
}

// File deletion functionality with CSRF protection
function initializeDeleteButtons() {
    const deleteButtons = document.querySelectorAll('.delete-file');

    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const fileId = this.getAttribute('data-file-id');
            const filename = this.getAttribute('data-filename');

            // Confirmation dialog
            if (confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
                deleteFile(fileId);
            }
        });
    });
}

function deleteFile(fileId) {
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

    if (!csrfToken) {
        showToast('Security token missing. Please refresh the page.', 'error');
        return;
    }

    // Show loading state
    const deleteButton = document.querySelector(`.delete-file[data-file-id="${fileId}"]`);
    if (deleteButton) {
        deleteButton.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i>';
        deleteButton.disabled = true;
    }

    // Send delete request with CSRF token
    fetch(`/delete/${fileId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken  // Add CSRF token to headers
        },
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        } else if (response.ok) {
            return response.json();
        } else {
            throw new Error('Server error: ' + response.status);
        }
    })
    .then(data => {
        if (data && data.error) {
            showToast('Error deleting file: ' + data.error, 'error');
            resetDeleteButton(deleteButton);
        }
    })
    .catch(error => {
        console.error('Delete error:', error);
        showToast('Error deleting file. Please try again.', 'error');
        resetDeleteButton(deleteButton);
    });
}

function resetDeleteButton(button) {
    if (button) {
        button.innerHTML = '<i class="bi bi-trash"></i>';
        button.disabled = false;
    }
}

// Also check when URL changes for scrolling
window.addEventListener('hashchange', checkScrollToUpload);
