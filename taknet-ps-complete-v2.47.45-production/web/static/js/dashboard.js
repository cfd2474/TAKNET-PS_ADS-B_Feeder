// Auto-refresh status every 10 seconds
let autoRefresh = setInterval(updateStatus, 10000);

async function updateNetworkStatus() {
    try {
        const response = await fetch('/api/network-status');
        const data = await response.json();
        
        // Update internet status
        const internetStatus = document.getElementById('internet-status');
        if (internetStatus) {
            const statusDot = internetStatus.querySelector('.status-dot');
            const statusText = internetStatus.querySelector('.status-text');
            
            if (data.internet) {
                statusDot.classList.add('online');
                statusDot.classList.remove('offline');
                statusText.textContent = 'Connected';
                statusText.style.color = '#10b981';
            } else {
                statusDot.classList.add('offline');
                statusDot.classList.remove('online');
                statusText.textContent = 'Disconnected';
                statusText.style.color = '#ef4444';
            }
        }
        
        // Update IP address
        const ipElement = document.getElementById('ip-address');
        if (ipElement) {
            ipElement.textContent = data.ip_address;
        }
        
        // Update hostname
        const hostnameElement = document.getElementById('hostname');
        if (hostnameElement) {
            hostnameElement.textContent = data.hostname;
        }
        
    } catch (error) {
        console.error('Error fetching network status:', error);
    }
}

// Update network status on load and every 10 seconds
updateNetworkStatus();
setInterval(updateNetworkStatus, 10000);

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update container status
        const container = document.getElementById('container-status');
        if (container && data.docker && data.docker.ultrafeeder) {
            const isRunning = data.docker.ultrafeeder.includes('Up');
            container.innerHTML = `
                <div class="status-item">
                    <span class="status-dot ${isRunning ? 'active' : 'inactive'}"></span>
                    <span>ultrafeeder</span>
                    <span class="status-text">${data.docker.ultrafeeder}</span>
                </div>
            `;
        }
        
        // Update feeds (if element exists)
        const feedsContainer = document.getElementById('active-feeds');
        if (feedsContainer && data.feeds && data.feeds.length > 0) {
            feedsContainer.innerHTML = data.feeds.map(feed => `
                <div class="feed-item">
                    <span class="status-dot active"></span>
                    ${feed}
                </div>
            `).join('');
        }
        
    } catch (error) {
        console.error('Failed to update status:', error);
    }
}

async function restartService() {
    if (!confirm('Restart the ultrafeeder service?')) return;
    
    showStatus('Restarting service...', 'info');
    
    try {
        const response = await fetch('/api/service/restart', {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Failed to restart service');
        
        showStatus('✓ Service restarted successfully', 'success');
        
        // Refresh status after a delay
        setTimeout(updateStatus, 3000);
        
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}


function showStatus(message, type) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = type;
    status.style.display = 'block';
    
    setTimeout(() => {
        status.style.display = 'none';
    }, 5000);
}
