// Offline mode detection
let isOnline = true; // Will be checked on page load

// Check internet connectivity
async function checkInternetConnection() {
    try {
        const response = await fetch('/api/network-status', {
            method: 'GET',
            cache: 'no-cache'
        });
        const data = await response.json();
        return data.internet || false;
    } catch (error) {
        console.error('Failed to check internet:', error);
        return false;
    }
}

// Initialize offline mode detection
async function initializeOfflineMode() {
    isOnline = await checkInternetConnection();
    console.log('Internet connection status:', isOnline ? 'ONLINE' : 'OFFLINE');
    
    if (!isOnline) {
        // Show offline warning
        const warningEl = document.getElementById('offlineWarning');
        if (warningEl) {
            warningEl.style.display = 'block';
        }
        
        // Change Step 1 button to "Save & Start" instead of "Next"
        const step1Button = document.querySelector('#step1 .btn-primary');
        if (step1Button) {
            step1Button.textContent = 'Save & Start 🚀';
            step1Button.onclick = function() {
                // Validate Step 1 first
                const lat = document.getElementById('lat').value.trim();
                const lon = document.getElementById('lon').value.trim();
                const alt = document.getElementById('alt').value.trim();
                const tz = document.getElementById('tz').value;
                const siteName = document.getElementById('site_name').value.trim();
                
                if (!lat || !lon || !alt || !tz) {
                    showStatus('Please fill in all required location fields', 'error');
                    return;
                }
                
                if (!siteName) {
                    showStatus('Please enter a feeder name', 'error');
                    return;
                }
                
                // Validate formats
                const latPattern = /^-?\d+\.\d+$/;
                const lonPattern = /^-?\d+\.\d+$/;
                const altPattern = /^\d+$/;
                
                if (!latPattern.test(lat)) {
                    showStatus('Latitude must be in decimal format (e.g., 33.55390)', 'error');
                    return;
                }
                
                if (!lonPattern.test(lon)) {
                    showStatus('Longitude must be in decimal format (e.g., -117.21390)', 'error');
                    return;
                }
                
                if (!altPattern.test(alt)) {
                    showStatus('Altitude must be a whole number (e.g., 304)', 'error');
                    return;
                }
                
                // Validation passed - go directly to save (skip Tailscale and aggregators)
                saveAndStart();
            };
        }
        
        console.log('Offline mode: Steps 2 and 3 will be skipped');
    }
}

// Setup wizard navigation
function nextStep(step) {
    console.log("=== nextStep called, step:", step);
    
    // No validation needed here anymore - we validate in saveAndStart() instead
    // Old logic validated location BEFORE showing step2, but now step2 IS the location form (empty!)
    
    // Navigation approved - show next step
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    document.getElementById('step' + step).classList.add('active');
}

function prevStep(step) {
    nextStep(step);
}

// Get zip code from coordinates using reverse geocoding
async function getZipCodeFromCoords(lat, lon) {
    try {
        // Use Nominatim (OpenStreetMap) reverse geocoding - free, no API key needed
        const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`,
            {
                headers: {
                    'User-Agent': 'TAKNET-PS-ADSB-Feeder/2.1'
                }
            }
        );
        
        if (!response.ok) throw new Error('Geocoding failed');
        
        const data = await response.json();
        
        // Try to extract postal code from address
        if (data.address) {
            return data.address.postcode || data.address.postal_code || null;
        }
        
        return null;
    } catch (error) {
        console.error('Failed to get zip code:', error);
        return null;
    }
}

// Install Tailscale with auth key
async function installTailscale(authKey) {
    try {
        const response = await fetch('/api/tailscale/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auth_key: authKey })
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('Failed to install Tailscale:', error);
        return { success: false, message: 'Failed to communicate with server' };
    }
}

// Save configuration and start service
async function saveAndStart() {
    const lat = document.getElementById('lat').value;
    const lon = document.getElementById('lon').value;
    const alt = document.getElementById('alt').value;
    const tz = document.getElementById('tz').value;
    const siteName = document.getElementById('site_name').value.trim();
    const userZipCode = document.getElementById('zip_code').value.trim();
    
    console.log('=== saveAndStart called - validating Location fields ===');
    
    // Validate required fields
    if (!lat || !lon || !alt) {
        showStatus('Please enter latitude, longitude, and altitude', 'error');
        // Stay on current page (Location = step2)
        return;
    }
    
    // Validate coordinate format
    const latPattern = /^-?\d+\.\d+$/;
    const lonPattern = /^-?\d+\.\d+$/;
    
    if (!latPattern.test(lat)) {
        showStatus('Latitude must be in decimal format (e.g., 33.55390)', 'error');
        // Stay on current page (Location = step2)
        return;
    }
    
    if (!lonPattern.test(lon)) {
        showStatus('Longitude must be in decimal format (e.g., -117.21390)', 'error');
        // Stay on current page (Location = step2)
        return;
    }
    
    if (!tz) {
        showStatus('Please select a timezone', 'error');
        // Stay on current page (Location = step2)
        return;
    }
    
    if (!siteName) {
        showStatus('Please enter a feeder name', 'error');
        // Stay on current page (Location = step2)
        return;
    }
    
    console.log('✅ Validation passed - processing configuration...');
    
    let finalSiteName;
    let zipCode;
    
    if (userZipCode) {
        // User provided zip code - use it directly
        zipCode = userZipCode;
        finalSiteName = `${zipCode}-${siteName}`;
        showStatus(`Using your zip code: ${zipCode}. Processing configuration...`, 'success');
    } else {
        // No user zip code - estimate from coordinates
        showStatus('Looking up location information...', 'info');
        zipCode = await getZipCodeFromCoords(lat, lon);
        
        if (zipCode) {
            finalSiteName = `${zipCode}-${siteName}`;
            showStatus(`Location found: ${zipCode}. Processing configuration...`, 'success');
        } else {
            // If zip code lookup fails, use default prefix
            finalSiteName = `00000-${siteName}`;
            showStatus('Could not determine zip code, using default. Processing configuration...', 'info');
        }
    }

    console.log("Zip code processing complete. finalSiteName:", finalSiteName);
    
    // Tailscale is configured in Settings, not in setup wizard
    // Always disabled during initial setup
    const tailscaleEnabled = false;
    const tailscaleKey = '';
    console.log("Initial setup: Tailscale will be disabled (can enable in Settings)");
    
    const config = {
        // Location settings
        FEEDER_LAT: lat,
        FEEDER_LONG: lon,
        FEEDER_ALT_M: alt,
        FEEDER_TZ: tz,
        MLAT_SITE_NAME: finalSiteName,
        ZIP_CODE: userZipCode || zipCode || '',
        
        // Tailscale settings (disabled by default, configured in Settings)
        TAILSCALE_ENABLED: 'false',
        TAILSCALE_AUTH_KEY: ''
        
        // TAKNET-PS Server is hardcoded - DO NOT send these parameters
        // TAKNET_PS_ENABLED, TAKNET_PS_SERVER_HOST_*, TAKNET_PS_SERVER_PORT will use defaults from env-template
        
        // Note: Aggregators (FR24, Airplanes.Live, adsb.fi, adsb.lol) are configured on the Feeds page
        // They are not part of the wizard anymore
    };
    
    console.log("Config object built:", config);
    
    console.log("Config object built:", config);
    
    showStatus('Saving configuration...', 'info');
    console.log("Showing status overlay...");
    showStatusOverlay('Saving Configuration...', 'Building docker-compose and updating services');
    console.log("Status overlay shown, starting fetch...");
    
    try {
        // Save config
        console.log("Fetching /api/config...");
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) throw new Error('Failed to save configuration');
        
        showSuccessOverlay('Configuration Saved!', 'Starting services...');
        
        // Brief delay to show success message
        setTimeout(() => {
            window.location.href = '/loading';
        }, 1500);
        
    } catch (error) {
        hideStatusOverlay();
        showStatus('Error: ' + error.message, 'error');
    }
}

function showStatus(message, type) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = type;
    status.style.display = 'block';
}

// Status overlay functions
function showStatusOverlay(message, detail) {
    let overlay = document.getElementById('status-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'status-overlay';
        overlay.className = 'status-overlay';
        overlay.innerHTML = `
            <div class="status-content">
                <div class="spinner"></div>
                <h2 id="overlay-message">${message}</h2>
                <p id="overlay-detail">${detail || 'Please wait...'}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    } else {
        document.getElementById('overlay-message').textContent = message;
        document.getElementById('overlay-detail').textContent = detail || 'Please wait...';
        overlay.style.display = 'flex';
    }
}

function hideStatusOverlay() {
    const overlay = document.getElementById('status-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

function showSuccessOverlay(message, detail) {
    let overlay = document.getElementById('status-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'status-overlay';
        overlay.className = 'status-overlay';
        document.body.appendChild(overlay);
    }
    
    overlay.innerHTML = `
        <div class="status-content success">
            <div style="font-size: 60px; color: #10b981; margin-bottom: 20px;">✓</div>
            <h2>${message}</h2>
            <p>${detail || ''}</p>
        </div>
    `;
    overlay.style.display = 'flex';
}

// Enable/disable Connect Tailscale button based on key input
function checkTailscaleKey() {
    const keyInput = document.getElementById('tailscale_key');
    const connectBtn = document.getElementById('connect-tailscale-btn');
    
    if (keyInput && connectBtn) {
        const key = keyInput.value.trim();
        // Enable button if key looks valid (starts with tskey- and is reasonably long)
        const isValidFormat = key.startsWith('tskey-') && key.length > 20;
        connectBtn.disabled = !isValidFormat;
    }
}

// Connect Tailscale with auth key
async function connectTailscale() {
    const keyInput = document.getElementById('tailscale_key');
    const authKey = keyInput.value.trim();
    
    console.log('=== connectTailscale called ===');
    
    if (!authKey) {
        showStatus('Please enter a Tailscale auth key', 'error');
        return;
    }
    
    console.log('Auth key provided, showing modal...');
    
    // Show progress modal
    document.getElementById('tailscaleProgressModal').style.display = 'block';
    document.getElementById('progress-status-text').textContent = 'Starting Tailscale installation...';
    document.getElementById('progress-details').innerHTML = '<div>[' + new Date().toLocaleTimeString() + '] Initializing...</div>';
    
    try {
        console.log('Calling /api/tailscale/install...');
        
        // Start installation
        const response = await fetch('/api/tailscale/install', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                auth_key: authKey
            })
        });
        
        const result = await response.json();
        console.log('Install API response:', result);
        
        if (!response.ok) {
            throw new Error(result.message || 'Failed to start Tailscale installation');
        }
        
        console.log('Saving config...');
        
        // Save the key to config immediately
        await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                TAILSCALE_ENABLED: 'true',
                TAILSCALE_AUTH_KEY: authKey
            })
        });
        
        console.log('Config saved, starting progress polling...');
        
        // Start polling for progress
        pollTailscaleProgress();
        
    } catch (error) {
        console.error('Failed to connect Tailscale:', error);
        document.getElementById('progress-status-text').textContent = 'Error: ' + error.message;
        document.getElementById('progress-status-text').style.color = '#ef4444';
        document.getElementById('progress-modal-buttons').style.display = 'block';
        
        const buttonsDiv = document.getElementById('progress-modal-buttons');
        buttonsDiv.innerHTML = `
            <button class="btn" onclick="closeProgressModal()">Close</button>
            <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue Anyway →</button>
        `;
    }
}

// Skip Tailscale and go to Location step
function skipTailscale() {
    console.log('=== skipTailscale called - going to step2 (Location)');
    // Save that Tailscale is disabled
    fetch('/api/config/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            TAILSCALE_ENABLED: 'false'
        })
    }).then(() => {
        console.log('Tailscale disabled saved, navigating to step2');
        nextStep(2); // Go to Location step (step2)
    }).catch(error => {
        console.error('Failed to save Tailscale disabled:', error);
        console.log('Navigating to step2 anyway');
        nextStep(2); // Go anyway to Location step (step2)
    });
}

// Poll Tailscale installation progress
let progressPollInterval = null;

async function pollTailscaleProgress() {
    let attempts = 0;
    const maxAttempts = 120; // 120 seconds timeout (increased from 60)
    
    progressPollInterval = setInterval(async () => {
        attempts++;
        console.log(`[Tailscale Poll] Attempt ${attempts}/${maxAttempts}`);
        
        try {
            const response = await fetch('/api/tailscale/progress');
            const data = await response.json();
            
            console.log('[Tailscale Poll] Progress data:', data);
            
            updateTailscaleProgressUI(data);
            
            // Check if complete or failed
            if (data.status === 'completed' || data.status === 'failed' || attempts >= maxAttempts) {
                clearInterval(progressPollInterval);
                progressPollInterval = null;
                
                if (data.status === 'completed') {
                    console.log('[Tailscale Poll] ✓ Completed! User must click Continue button.');
                    // Success - show Continue button (no auto-proceed)
                    // User must manually click to continue
                } else if (data.status === 'failed') {
                    console.error('[Tailscale Poll] ✗ Failed:', data.message);
                    // Failed - show close button with option to continue anyway
                    document.getElementById('progress-modal-buttons').style.display = 'block';
                    
                    // Add "Continue Anyway" button
                    const buttonsDiv = document.getElementById('progress-modal-buttons');
                    buttonsDiv.innerHTML = `
                        <button class="btn" onclick="closeProgressModal()">Close</button>
                        <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue to Location →</button>
                    `;
                } else {
                    console.warn('[Tailscale Poll] ⏱ Timeout after', maxAttempts, 'seconds');
                    // Timeout - show option to continue anyway
                    document.getElementById('progress-status-text').textContent = 'Connection taking longer than expected...';
                    document.getElementById('progress-status-text').style.color = '#f59e0b';
                    document.getElementById('progress-modal-buttons').style.display = 'block';
                    
                    const buttonsDiv = document.getElementById('progress-modal-buttons');
                    buttonsDiv.innerHTML = `
                        <button class="btn" onclick="closeProgressModal()">Stay Here</button>
                        <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue Anyway →</button>
                    `;
                }
            }
        } catch (error) {
            console.error('[Tailscale Poll] Error:', error);
            
            if (attempts >= maxAttempts) {
                clearInterval(progressPollInterval);
                progressPollInterval = null;
                document.getElementById('progress-status-text').textContent = 'Connection timeout - check status in Settings';
                document.getElementById('progress-status-text').style.color = '#f59e0b';
                document.getElementById('progress-modal-buttons').style.display = 'block';
                
                const buttonsDiv = document.getElementById('progress-modal-buttons');
                buttonsDiv.innerHTML = `
                    <button class="btn" onclick="closeProgressModal()">Close</button>
                    <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue to Location →</button>
                `;
            }
        }
    }, 1000); // Poll every 1 second
}

// Update Tailscale progress UI
function updateTailscaleProgressUI(data) {
    const statusText = document.getElementById('progress-status-text');
    const overallPercent = document.getElementById('overall-percent');
    const overallProgress = document.getElementById('overall-progress');
    const currentLabel = document.getElementById('current-process-label');
    const currentPercent = document.getElementById('current-percent');
    const currentProgress = document.getElementById('current-progress');
    const progressDetails = document.getElementById('progress-details');
    
    let overallValue = 0;
    let currentValue = 0;
    let currentLabelText = '';
    let currentPercentText = '';
    
    // Helper function to format bytes
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 10) / 10 + ' ' + sizes[i];
    }
    
    // Calculate overall and current progress based on phase
    if (data.status === 'downloading') {
        // Download phase: 0-40% overall
        const downloadProgress = data.download_progress || 0;
        overallValue = Math.floor(downloadProgress * 0.40);  // 0-40%
        currentValue = downloadProgress;
        currentLabelText = 'Downloading Tailscale';
        
        // Show file size if available
        if (data.download_bytes && data.total_bytes) {
            const downloaded = formatBytes(data.download_bytes);
            const total = formatBytes(data.total_bytes);
            currentPercentText = `${downloaded} / ${total}`;
        } else {
            currentPercentText = `${downloadProgress}%`;
        }
        
        statusText.textContent = 'Downloading Tailscale...';
        statusText.style.color = '#374151';
        
    } else if (data.status === 'installing') {
        // Install phase: 40-75% overall
        const installProgress = data.install_progress || 0;
        overallValue = 40 + Math.floor(installProgress * 0.35);  // 40-75%
        currentValue = installProgress;
        currentLabelText = 'Installing';
        currentPercentText = ''; // Don't show percentage for time-based progress
        statusText.textContent = 'Installing Tailscale...';
        statusText.style.color = '#374151';
        
    } else if (data.status === 'registering') {
        // Register phase: 75-100% overall
        const registerProgress = data.register_progress || 0;
        overallValue = 75 + Math.floor(registerProgress * 0.25);  // 75-100%
        currentValue = registerProgress;
        currentLabelText = 'Registering to Tailscale network';
        currentPercentText = ''; // Don't show percentage for time-based progress
        statusText.textContent = 'Registering to Tailscale network...';
        statusText.style.color = '#374151';
        
    } else if (data.status === 'completed') {
        // Completed: 100% everything
        overallValue = 100;
        currentValue = 100;
        currentLabelText = 'Complete';
        currentPercentText = '100%';
        statusText.textContent = '✓ Tailscale connected successfully!';
        statusText.style.color = '#10b981';
        
        // Show Continue button (user must click - no auto-proceed)
        const buttonsDiv = document.getElementById('progress-modal-buttons');
        buttonsDiv.style.display = 'block';
        buttonsDiv.innerHTML = `
            <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue to Location →</button>
        `;
        
    } else if (data.status === 'failed') {
        // Failed: show error
        statusText.textContent = '✗ Connection Failed';
        statusText.style.color = '#ef4444';
        
        // Show error details
        progressDetails.style.display = 'block';
        const errorMessage = data.message || data.error || 'Unknown error occurred';
        progressDetails.innerHTML = `<strong>Error:</strong> ${errorMessage}`;
        
        // Show buttons
        const buttonsDiv = document.getElementById('progress-modal-buttons');
        buttonsDiv.style.display = 'block';
        buttonsDiv.innerHTML = `
            <button class="btn" onclick="closeProgressModal()">Close</button>
            <button class="btn btn-primary" onclick="closeProgressModal(); nextStep(2);">Continue to Location →</button>
        `;
        
        return; // Don't update progress bars on failure
    }
    
    // Update UI elements
    overallPercent.textContent = `${overallValue}%`;
    overallProgress.style.width = `${overallValue}%`;
    currentLabel.textContent = currentLabelText;
    currentPercent.textContent = currentPercentText;
    currentProgress.style.width = `${currentValue}%`;
    
    // Hide error details on normal progress
    progressDetails.style.display = 'none';
}

// Close progress modal
function closeProgressModal() {
    document.getElementById('tailscaleProgressModal').style.display = 'none';
    
    // Reset UI
    document.getElementById('progress-status-text').textContent = 'Initializing...';
    document.getElementById('progress-status-text').style.color = '#374151';
    document.getElementById('overall-percent').textContent = '0%';
    document.getElementById('overall-progress').style.width = '0%';
    document.getElementById('current-process-label').textContent = 'Initializing...';
    document.getElementById('current-percent').textContent = '0%';
    document.getElementById('current-progress').style.width = '0%';
    document.getElementById('progress-details').innerHTML = '';
    document.getElementById('progress-details').style.display = 'none';
    document.getElementById('progress-modal-buttons').style.display = 'none';
    
    // Clear polling interval if still running
    if (progressPollInterval) {
        clearInterval(progressPollInterval);
        progressPollInterval = null;
    }
}

// Initialize Tailscale key checking
document.addEventListener('DOMContentLoaded', function() {
    const keyInput = document.getElementById('tailscale_key');
    if (keyInput) {
        keyInput.addEventListener('input', checkTailscaleKey);
        // Check on page load in case value is pre-filled
        checkTailscaleKey();
    }
});
