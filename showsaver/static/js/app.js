const form = document.getElementById('textForm');
const textInput = document.getElementById('textInput');
const clearBtn = document.getElementById('clearBtn');
const panelQueueList = document.getElementById('panelQueueList');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');
const activityToggle = document.getElementById('activity-toggle');
const activityPanel = document.getElementById('activity-panel');
const activityOverlay = document.getElementById('activity-overlay');
const activityClose = document.getElementById('activity-close');
const activityBadge = document.getElementById('activity-badge');
const progressRingFill = document.getElementById('progress-ring-fill');
const RING_CIRCUMFERENCE = 106.8;

function openPanel() {
    activityPanel.classList.add('open');
    activityOverlay.classList.add('visible');
}

function closePanel() {
    activityPanel.classList.remove('open');
    activityOverlay.classList.remove('visible');
}

activityToggle.addEventListener('click', () => activityPanel.classList.contains('open') ? closePanel() : openPanel());
activityClose.addEventListener('click', closePanel);
activityOverlay.addEventListener('click', closePanel);

let connectionLost = false;
let prevDownloadingIds = new Set();
let pendingJob = null;
const connectionToast = document.getElementById('connectionError');

function formatStepType(stepType) {
    const labels = {
        'video': 'Downloading video',
        'audio': 'Downloading audio',
        'video+audio': 'Downloading'
    };
    return labels[stepType] || 'Downloading';
}

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let v = bytes;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatSpeed(bytesPerSec) {
    const s = formatBytes(bytesPerSec);
    return s ? `${s}/s` : '';
}

function formatEta(etaSeconds) {
    if (!etaSeconds) return '';
    const remaining = Math.max(0, Math.round(etaSeconds));
    if (remaining <= 0) return '';
    const h = Math.floor(remaining / 3600);
    const m = Math.floor((remaining % 3600) / 60);
    const s = remaining % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

// Poll for queue status
async function updateQueueStatus() {
    try {
        const response = await fetch('/queue');
        const data = await response.json();

        if (connectionLost) {
            connectionLost = false;
            connectionToast.classList.remove('show');
        }

        if (data.success) {
            const allItems = [
                ...data.downloading.map(d => ({...d, displayStatus: 'downloading'})),
                ...data.queued.map(q => ({...q, displayStatus: 'queued'})),
                ...[...data.completed].reverse().map(c => ({...c, displayStatus: 'completed'}))
            ];

            if (pendingJob) {
                if (pendingJob.id === null) {
                    // Still waiting for server response — always show pending
                    allItems.unshift({ ...pendingJob, displayStatus: 'pending', status: 'pending' });
                } else {
                    const knownIds = new Set([
                        ...data.downloading.map(d => d.id),
                        ...data.queued.map(q => q.id),
                        ...data.completed.map(c => c.id)
                    ]);
                    if (knownIds.has(pendingJob.id)) {
                        pendingJob = null;
                    } else {
                        allItems.unshift({ ...pendingJob, displayStatus: 'pending', status: 'pending' });
                    }
                }
            }

            clearHistoryBtn.style.display = data.completed.length > 0 ? 'block' : 'none';

            panelQueueList.innerHTML = allItems.map(item => `
                <div class="queue-item ${item.displayStatus}">
                    <div class="queue-item-header">
                        <div class="queue-item-url" title="${item.url}">${item.url}</div>
                        <div class="queue-item-status ${item.displayStatus}">${item.status}</div>
                    </div>
                    ${item.displayStatus === 'downloading' ? `
                        <div class="queue-item-step">
                            Step ${item.step || 1}/${item.total_steps || 1}: ${formatStepType(item.step_type)}
                        </div>
                        <div class="queue-item-progress">
                            <div class="queue-item-progress-bar" style="width: ${item.progress || 0}%"></div>
                        </div>
                        <div class="queue-item-stats">
                            ${[
                                formatSpeed(item.speed_bytes),
                                formatBytes(item.total_bytes),
                                formatEta(item.eta) ? `ETA ${formatEta(item.eta)}` : ''
                            ].filter(Boolean).join(' • ')}
                        </div>
                    ` : ''}
                </div>
            `).join('');

            const activeCount = data.downloading.length + data.queued.length;
            if (activeCount > 0) {
                activityBadge.textContent = activeCount;
                activityBadge.classList.remove('hidden');
            } else {
                activityBadge.classList.add('hidden');
            }

            if (data.downloading.length > 0) {
                const avg = data.downloading.reduce((sum, d) => sum + (d.progress || 0), 0) / data.downloading.length;
                progressRingFill.style.strokeDashoffset = RING_CIRCUMFERENCE * (1 - avg / 100);
            } else {
                progressRingFill.style.strokeDashoffset = RING_CIRCUMFERENCE;
            }

            const currentIds = new Set(data.downloading.map(d => d.id));
            if ([...currentIds].some(id => !prevDownloadingIds.has(id))) {
                openPanel();
            }
            prevDownloadingIds = currentIds;
        }
    } catch (error) {
        console.error('Failed to update queue status:', error);
        if (!connectionLost) {
            connectionLost = true;
            connectionToast.classList.add('show');
        }
    }
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = form.querySelector('.submit-btn');
    const text = textInput.value.trim();

    if (!text) return;

    // Show loading state
    submitBtn.disabled = true;
    submitBtn.classList.add('loading');

    // Open panel immediately with a pending entry before the server responds
    pendingJob = { id: null, url: text };
    openPanel();

    try {
        const response = await fetch('/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (data.success) {
            pendingJob = { id: data.job_id, url: text };
            textInput.value = '';
        } else {
            pendingJob = null;
        }

    } catch (error) {
        pendingJob = null;
    } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
    }
});

clearHistoryBtn.addEventListener('click', async () => {
    await fetch('/history', { method: 'DELETE' });
    updateQueueStatus();
});

clearBtn.addEventListener('click', () => {
    textInput.value = '';
    textInput.focus();
});

// Update queue status every 1 second
setInterval(updateQueueStatus, 1000);
updateQueueStatus(); // Initial load

// Dropout New Releases Panel
const releasesGrid = document.getElementById('releasesGrid');
const refreshReleasesBtn = document.getElementById('refreshReleases');

function formatDuration(seconds) {
    if (!seconds) return '';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
        return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function renderReleases(videos) {
    if (!videos || videos.length === 0) {
        releasesGrid.innerHTML = '<div class="empty-releases">No releases available</div>';
        return;
    }

    // Placeholder thumbnail: dark background with TV/monitor icon
    const placeholderThumb = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 180'%3E%3Crect fill='%232a2a2a' width='320' height='180'/%3E%3Crect x='100' y='45' width='120' height='75' rx='4' fill='none' stroke='%23555' stroke-width='4'/%3E%3Crect x='110' y='55' width='100' height='55' fill='%23333'/%3E%3Crect x='140' y='120' width='40' height='8' fill='%23555'/%3E%3Crect x='130' y='128' width='60' height='6' rx='2' fill='%23555'/%3E%3C/svg%3E";

    releasesGrid.innerHTML = videos.map(video => `
        <div class="release-card" data-url="${video.url}" title="Click to queue download">
            <div class="release-thumbnail">
                <img src="${video.thumbnail || placeholderThumb}" alt="${video.title || 'Video'}" loading="lazy">
                ${video.duration ? `<span class="release-duration">${formatDuration(video.duration)}</span>` : ''}
            </div>
            <div class="release-info">
                <div class="release-show">${video.show_name || ''}</div>
                <div class="release-title">${video.title || (video.url.includes('videos/') ? video.url.split('videos/').pop() : video.url)}</div>
            </div>
        </div>
    `).join('');

    // Add click handlers to cards
    releasesGrid.querySelectorAll('.release-card').forEach(card => {
        card.addEventListener('click', () => queueRelease(card.dataset.url));
    });
}

async function fetchNewReleases() {
    releasesGrid.innerHTML = '<div class="loading-releases">Loading releases...</div>';
    refreshReleasesBtn.classList.add('spinning');

    try {
        const response = await fetch('/dropout/new-releases');
        const data = await response.json();

        if (data.success) {
            const limitedVideos = data.videos.slice(0, 9);
            renderReleases(limitedVideos);
            startReleasesPolling(limitedVideos);
        } else {
            releasesGrid.innerHTML = `<div class="error-releases">Failed to load releases</div>`;
        }
    } catch (error) {
        console.error('Failed to fetch releases:', error);
        releasesGrid.innerHTML = `<div class="error-releases">Failed to load releases</div>`;
    } finally {
        refreshReleasesBtn.classList.remove('spinning');
    }
}

let releasesPollTimer = null;
const RELEASES_POLL_INTERVAL_MS = 2000;
const RELEASES_POLL_MAX = 30;

function allCardsSettled(videos) {
    // A card is settled once we have a show_name OR yt-dlp has been tried
    // (metadata_fetched_at set) — empty show_name after a fetch attempt won't
    // self-heal until METADATA_CACHE_TTL elapses, so polling further is wasted.
    return videos.every(v => (v.show_name && v.show_name.length > 0) || v.metadata_fetched_at);
}

function startReleasesPolling(initialVideos) {
    if (releasesPollTimer) {
        clearInterval(releasesPollTimer);
        releasesPollTimer = null;
    }
    if (allCardsSettled(initialVideos)) return;

    let polls = 0;
    releasesPollTimer = setInterval(async () => {
        polls += 1;
        try {
            const response = await fetch('/dropout/new-releases');
            const data = await response.json();
            if (!data.success) return;

            const videos = data.videos.slice(0, 9);
            videos.forEach(v => updateReleaseCard(v.url, v));

            if (allCardsSettled(videos) || polls >= RELEASES_POLL_MAX) {
                clearInterval(releasesPollTimer);
                releasesPollTimer = null;
            }
        } catch (err) {
            console.error('Releases poll failed:', err);
        }
    }, RELEASES_POLL_INTERVAL_MS);
}

function updateReleaseCard(url, info) {
    const card = releasesGrid.querySelector(`[data-url="${url}"]`);
    if (!card) return;

    // Update thumbnail
    const img = card.querySelector('.release-thumbnail img');
    if (img && info.thumbnail) {
        img.src = info.thumbnail;
    }

    // Update show name
    const showName = card.querySelector('.release-show');
    if (showName && info.show_name) {
        showName.textContent = info.show_name;
    }

    // Update title
    const title = card.querySelector('.release-title');
    if (title && info.title) {
        title.textContent = info.title;
    }

    // Update duration
    const thumbnailDiv = card.querySelector('.release-thumbnail');
    if (info.duration && thumbnailDiv) {
        let durationSpan = thumbnailDiv.querySelector('.release-duration');
        if (!durationSpan) {
            durationSpan = document.createElement('span');
            durationSpan.className = 'release-duration';
            thumbnailDiv.appendChild(durationSpan);
        }
        durationSpan.textContent = formatDuration(info.duration);
    }

    // Mark card as loaded
    card.classList.add('details-loaded');
}

async function queueRelease(url) {
    try {
        const response = await fetch('/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: url })
        });

        const data = await response.json();

    } catch (error) {
        console.error('Failed to queue new release:', error);
    }
}

// Event listeners for releases panel
refreshReleasesBtn.addEventListener('click', fetchNewReleases);

// Load releases on page load
fetchNewReleases();
