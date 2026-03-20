// Dashboard bootstrap + polling optimized for fewer, parallel requests.
const DASHBOARD_DEBUG = false;
let dashboardPollInterval = null;
let lastUpdateTime = new Date();
let pollInFlight = false;

function debugLog(...args) {
    if (DASHBOARD_DEBUG) {
        console.log('[dashboard]', ...args);
    }
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const resp = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(id);
        return resp;
    } catch (e) {
        clearTimeout(id);
        throw e;
    }
}

// Bootstrap runs SDR scan + docker/TAKNET checks; slow on Pi or via tunnel — allow long wait
const BOOTSTRAP_FETCH_MS = 90000;

async function fetchBootstrap() {
    const t0 = performance.now();
    const attempt = async () => {
        const resp = await fetchWithTimeout('/api/dashboard/bootstrap', {}, BOOTSTRAP_FETCH_MS);
        if (!resp.ok) {
            throw new Error(`bootstrap ${resp.status}`);
        }
        return resp.json();
    };
    try {
        const data = await attempt();
        debugLog(`bootstrap fetched in ${(performance.now() - t0).toFixed(0)}ms`);
        return data;
    } catch (e) {
        const aborted = e && (e.name === 'AbortError' || e.message === 'signal is aborted without reason');
        if (aborted) {
            debugLog('bootstrap timed out, retrying once…');
            try {
                const data = await attempt();
                debugLog(`bootstrap OK after retry in ${(performance.now() - t0).toFixed(0)}ms`);
                return data;
            } catch (e2) {
                console.warn('Dashboard bootstrap failed after retry (slow link or feeder busy). Refresh the page.');
                return null;
            }
        }
        console.error('Error fetching dashboard bootstrap:', e);
        return null;
    }
}

function renderNetworkStatus(networkStatus) {
    if (!networkStatus) return;
    const internetStatus = document.getElementById('internet-status');
    if (internetStatus) {
        const statusDot = internetStatus.querySelector('.status-dot');
        const statusText = internetStatus.querySelector('.status-text');
        if (networkStatus.internet) {
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
}

function renderCoreStatus(status) {
    if (!status || !status.docker) return;
    const ultrafeeder = status.docker.ultrafeeder;
    if (!ultrafeeder) return;
    const isRunning = ultrafeeder.includes('Up');

    const container = document.getElementById('container-status');
    if (container) {
        container.innerHTML = `
            <div class="status-item">
                <span class="status-dot ${isRunning ? 'active' : 'inactive'}"></span>
                <span>ultrafeeder</span>
                <span class="status-text">${ultrafeeder}</span>
            </div>
        `;
    }

    const floating = document.getElementById('floating-container-status');
    if (floating) {
        floating.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="status-dot ${isRunning ? 'active' : 'inactive'}"></span>
                <span style="font-weight: 600; font-size: 0.9em;">ultrafeeder</span>
            </div>
        `;
    }
}

function renderFeeds(status) {
    if (!status || !status.feeds) return;
    const feedsContainer = document.getElementById('active-feeds');
    if (feedsContainer && status.feeds.length > 0) {
        feedsContainer.innerHTML = status.feeds
            .map(
                (feed) => `
                <div class="feed-item">
                    <span class="status-dot active"></span>
                    ${feed}
                </div>`
            )
            .join('');
    }
}

async function restartService() {
    if (!confirm('Restart the ultrafeeder service?')) return;

    showStatus('Restarting service...', 'info');

    try {
        const response = await fetch('/api/service/restart', {
            method: 'POST',
        });

        if (!response.ok) throw new Error('Failed to restart service');

        showStatus('✓ Service restarted successfully', 'success');

        // Refresh status after a short delay using the new bootstrap path
        setTimeout(pollDashboard, 3000);
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}

function showStatus(message, type) {
    const status = document.getElementById('status');
    if (!status) return;
    status.textContent = message;
    status.className = type;
    status.style.display = 'block';

    setTimeout(() => {
        status.style.display = 'none';
    }, 5000);
}

function updateLastUpdateTime() {
    const now = new Date();
    const seconds = Math.floor((now - lastUpdateTime) / 1000);
    let timeText;
    if (seconds < 60) {
        timeText = `${seconds}s ago`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        timeText = `${minutes}m ago`;
    } else {
        const hours = Math.floor(seconds / 3600);
        timeText = `${hours}h ago`;
    }
    const el = document.getElementById('updateTime');
    if (el) {
        el.textContent = timeText;
    }
}

function applyTaknetStats(taknetStats) {
    try {
        if (!taknetStats || !taknetStats.success) return;
        const taknetCheck = document.getElementById('taknet-check');
        const taknetDataCol = document.getElementById('taknet-data');
        const taknetMlatCol = document.getElementById('taknet-mlat');

        if (taknetCheck) {
            if (!taknetStats.data_feed_active) {
                taknetCheck.setAttribute('data-status', 'down');
            } else if (taknetStats.mlat_enabled && !taknetStats.mlat_active) {
                taknetCheck.setAttribute('data-status', 'mlat-down');
            } else {
                taknetCheck.setAttribute('data-status', 'good');
            }
        }

        if (taknetDataCol) {
            taknetDataCol.textContent = taknetStats.data_feed_active ? '+' : '-';
        }

        if (taknetMlatCol) {
            if (taknetStats.mlat_enabled) {
                taknetMlatCol.textContent = taknetStats.mlat_active ? '+' : '-';
            } else {
                taknetMlatCol.textContent = '-';
            }
        }
    } catch (e) {
        console.error('Error applying TAKNET-PS stats:', e);
    }
}

function applyServiceStates(serviceStates) {
    if (!serviceStates) return;

    // PiAware
    if (serviceStates.piaware) {
        const piawareState = serviceStates.piaware;
        const piawareCheck = document.getElementById('piaware-check');
        if (piawareCheck) {
            switch (piawareState) {
                case 'running': {
                    piawareCheck.setAttribute('data-status', 'good');
                    const piawareData = document.getElementById('piaware-data');
                    const piawareMlat = document.getElementById('piaware-mlat');
                    if (piawareData) piawareData.textContent = '+';
                    if (piawareMlat) piawareMlat.textContent = '+';
                    break;
                }
                case 'downloading':
                case 'starting':
                    piawareCheck.setAttribute('data-status', 'unknown');
                    break;
                case 'stopped':
                case 'not_installed': {
                    piawareCheck.setAttribute('data-status', 'down');
                    const piawareDataStopped = document.getElementById('piaware-data');
                    const piawareMlatStopped = document.getElementById('piaware-mlat');
                    if (piawareDataStopped) piawareDataStopped.textContent = '.';
                    if (piawareMlatStopped) piawareMlatStopped.textContent = '.';
                    break;
                }
            }
        }
    }

    // FR24
    if (serviceStates.fr24) {
        const fr24State = serviceStates.fr24;
        const fr24Check = document.getElementById('fr24-check');
        if (fr24Check) {
            switch (fr24State) {
                case 'running': {
                    fr24Check.setAttribute('data-status', 'good');
                    const fr24Data = document.getElementById('fr24-data');
                    const fr24Mlat = document.getElementById('fr24-mlat');
                    if (fr24Data) fr24Data.textContent = '+';
                    if (fr24Mlat) fr24Mlat.textContent = '+';
                    break;
                }
                case 'downloading':
                case 'starting':
                    fr24Check.setAttribute('data-status', 'unknown');
                    break;
                case 'stopped':
                case 'not_installed': {
                    fr24Check.setAttribute('data-status', 'down');
                    const fr24DataStopped = document.getElementById('fr24-data');
                    const fr24MlatStopped = document.getElementById('fr24-mlat');
                    if (fr24DataStopped) fr24DataStopped.textContent = '.';
                    if (fr24MlatStopped) fr24MlatStopped.textContent = '.';
                    break;
                }
            }
        }
    }
}

function applyPowerStatus(powerStatus) {
    if (!powerStatus) return;
    try {
        const banner = document.getElementById('power-warning-banner');
        const icon = document.getElementById('power-warning-icon');
        const title = document.getElementById('power-warning-title');
        const message = document.getElementById('power-warning-message');
        if (!banner || !icon || !title || !message) return;

        if (powerStatus.current_issue) {
            banner.style.display = 'block';
            banner.style.background = '#fee2e2';
            banner.style.borderLeft = '4px solid #dc2626';
            icon.textContent = '⚠️';
            title.style.color = '#991b1b';
            title.textContent = 'Under-voltage / CPU Throttling Detected';
            message.style.color = '#7f1d1d';
            message.textContent = 'SDR performance possibly degraded. Use proper power supply (minimum 2.5A).';
        } else if (powerStatus.past_issue) {
            banner.style.display = 'block';
            banner.style.background = '#fef3c7';
            banner.style.borderLeft = '4px solid #f59e0b';
            icon.textContent = 'ℹ️';
            title.style.color = '#92400e';
            title.textContent = 'Previous Under-voltage/Throttling Detected';
            message.style.color = '#78350f';
            message.textContent = 'Check power supply is providing minimum 2.5A.';
        } else {
            banner.style.display = 'none';
        }
    } catch (e) {
        console.error('Error applying power status:', e);
    }
}

function renderConnectionQualityInModal(networkQuality) {
    const body = document.getElementById('connection-quality-modal-body');
    if (!body) return;
    if (!networkQuality || !networkQuality.success) {
        body.innerHTML =
            '<p style="margin:0;color:#6b7280;">Could not measure connection quality. Try again.</p>';
        return;
    }
    const styles = {
        good: { bg: '#d1fae5', color: '#065f46', icon: '🟢', label: 'Good' },
        moderate: { bg: '#fef3c7', color: '#92400e', icon: '🟡', label: 'Moderate' },
        poor: { bg: '#fee2e2', color: '#991b1b', icon: '🔴', label: 'Poor' },
        unknown: { bg: '#f3f4f6', color: '#6b7280', icon: '❓', label: 'Unknown' },
    };
    const s = styles[networkQuality.quality] || styles.unknown;
    const rtt =
        networkQuality.avg_rtt_ms !== null && networkQuality.avg_rtt_ms !== undefined
            ? `${networkQuality.avg_rtt_ms} ms average RTT`
            : 'RTT not available';
    const loss = `${networkQuality.packet_loss ?? '—'}% packet loss`;
    body.innerHTML = `
        <div style="display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;font-weight:600;background:${s.bg};color:${s.color};margin-bottom:16px;">
            ${s.icon} ${s.label}
        </div>
        <p style="margin:0 0 8px 0;"><strong>Latency:</strong> ${rtt}</p>
        <p style="margin:0 0 16px 0;"><strong>Packet loss:</strong> ${loss}</p>
        <p style="margin:0;font-size:0.85em;color:#9ca3af;">Based on ping to 8.8.8.8 (may take ~20 seconds).</p>
    `;
}

function closeConnectionQualityModal() {
    const modal = document.getElementById('connection-quality-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
    }
}

function openConnectionQualityModal() {
    const modal = document.getElementById('connection-quality-modal');
    const body = document.getElementById('connection-quality-modal-body');
    const btn = document.getElementById('btn-connection-quality');
    if (!modal || !body) return;
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    body.innerHTML =
        '<p style="margin:0;color:#6b7280;">Running ping test… This usually takes about 20 seconds.</p>';
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Testing…';
    }
    fetchWithTimeout('/api/network-quality', {}, 30000)
        .then((resp) => {
            if (!resp.ok) throw new Error(String(resp.status));
            return resp.json();
        })
        .then((data) => renderConnectionQualityInModal(data))
        .catch(() => {
            body.innerHTML =
                '<p style="margin:0;color:#dc2626;">Request failed or timed out. Check network and try again.</p>';
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '📶 Measure connection quality';
            }
        });
}

function wireConnectionQualityModal() {
    const btn = document.getElementById('btn-connection-quality');
    const modal = document.getElementById('connection-quality-modal');
    const closeBtn = document.getElementById('connection-quality-modal-close');
    const panel = document.getElementById('connection-quality-modal-panel');
    if (btn) btn.addEventListener('click', () => openConnectionQualityModal());
    if (closeBtn) closeBtn.addEventListener('click', closeConnectionQualityModal);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeConnectionQualityModal();
        });
    }
    if (panel) {
        panel.addEventListener('click', (e) => e.stopPropagation());
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
            closeConnectionQualityModal();
        }
    });
}

function applySdrStatus(sdrStatus) {
    const tbody = document.getElementById('sdr-table-body');
    if (!tbody || !sdrStatus) return;
    try {
        if (sdrStatus.success && sdrStatus.devices && sdrStatus.devices.length > 0) {
            tbody.innerHTML = sdrStatus.devices
                .map(
                    (d, i) => `
                <tr style="background: ${i % 2 === 0 ? '#fff' : '#fafafa'};">
                    <td style="padding: 6px 12px; color: #374151; font-family: monospace;">${d.index}</td>
                    <td style="padding: 6px 12px; color: #374151;">${d.type}</td>
                    <td style="padding: 6px 12px; font-family: monospace; color: #374151;">${d.serial}</td>
                    <td style="padding: 6px 12px; color: #374151;">${d.use_for}</td>
                    <td style="padding: 6px 12px; color: #374151;">${d.gain}</td>
                    <td style="padding: 6px 12px; color: ${d.biastee ? '#059669' : '#6b7280'};">${d.biastee ? 'On' : 'Off'}</td>
                </tr>`
                )
                .join('');
        } else {
            tbody.innerHTML =
                '<tr><td colspan="6" style="padding: 8px 12px; color: #9ca3af; font-style: italic;">No SDR devices detected</td></tr>';
        }
    } catch (e) {
        tbody.innerHTML =
            '<tr><td colspan="6" style="padding: 8px 12px; color: #ef4444; font-style: italic;">Error detecting SDR devices</td></tr>';
    }
}

function applyBootstrap(data) {
    if (!data) return;
    renderNetworkStatus(data.network_status);
    renderCoreStatus(data.status);
    renderFeeds(data.status);
    applyServiceStates(data.status ? data.status.service_states : null);
    applyTaknetStats(data.taknet_stats);
    applyPowerStatus(data.power_status);
    applySdrStatus(data.sdr_status);
    lastUpdateTime = new Date();
}

async function pollDashboard() {
    if (pollInFlight) {
        debugLog('poll skipped (in flight)');
        return;
    }
    pollInFlight = true;
    const data = await fetchBootstrap();
    applyBootstrap(data);
    pollInFlight = false;
}

function initPolling() {
    if (!dashboardPollInterval) {
        dashboardPollInterval = setInterval(pollDashboard, 15000);
    }
    setInterval(updateLastUpdateTime, 1000);
}

async function initDashboard() {
    const t0 = performance.now();
    const bootstrap = await fetchBootstrap();
    applyBootstrap(bootstrap);
    const t1 = performance.now();
    debugLog(`initial render completed in ${(t1 - t0).toFixed(0)}ms`);
    initPolling();
    wireConnectionQualityModal();
    initMobileFeederPolling();
}

/** Mobile feeder mode card: poll /api/mobile/status when #mobile-feeder-card exists */
function initMobileFeederPolling() {
    const card = document.getElementById('mobile-feeder-card');
    if (!card) return;

    const elMotion = document.getElementById('mobile-in-motion');
    const elMlat = document.getElementById('mobile-mlat-status');
    const elSpeed = document.getElementById('mobile-speed-hint');
    if (!elMotion || !elMlat) return;

    async function poll() {
        try {
            const resp = await fetchWithTimeout('/api/mobile/status', {}, 6000);
            if (!resp.ok) return;
            const data = await resp.json();
            if (!data.success || !data.mobile_mode_enabled) return;

            if (data.in_motion_unknown) {
                elMotion.textContent = 'Unknown';
                elMotion.style.color = '#6b7280';
            } else if (data.in_motion) {
                elMotion.textContent = 'Yes';
                elMotion.style.color = '#d97706';
            } else {
                elMotion.textContent = 'No';
                elMotion.style.color = '#059669';
            }

            if (data.mlat_paused) {
                elMlat.innerHTML = '<span style="color: #dc2626;">Paused</span>';
            } else {
                elMlat.innerHTML = '<span style="color: #059669;">On</span>';
            }

            if (elSpeed && data.speed_mps != null && !data.in_motion_unknown) {
                elSpeed.textContent = `GPS speed: ${data.speed_mps} m/s`;
                elSpeed.style.display = 'block';
            } else if (elSpeed) {
                elSpeed.style.display = 'none';
            }
        } catch (e) {
            debugLog('mobile status poll failed', e);
        }
    }

    poll();
    setInterval(poll, 5000);
}

window.initDashboard = initDashboard;
