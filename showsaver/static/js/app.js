const form = document.getElementById('textForm');
const textInput = document.getElementById('textInput');
const clearBtn = document.getElementById('clearBtn');
const responseDiv = document.getElementById('response');
const responseTitle = document.getElementById('responseTitle');
const responseText = document.getElementById('responseText');
const statsDiv = document.getElementById('stats');
const statValue1 = document.getElementById('statValue1');
const statLabel1 = document.getElementById('statLabel1');
const statValue2 = document.getElementById('statValue2');
const statLabel2 = document.getElementById('statLabel2');
const queueStatus = document.getElementById('queueStatus');
const queueList = document.getElementById('queueList');

let activeJobId = null;
let statusInterval = null;

function formatStepType(stepType) {
    const labels = {
        'video': 'Downloading video',
        'audio': 'Downloading audio',
        'video+audio': 'Downloading'
    };
    return labels[stepType] || 'Downloading';
}

// Poll for queue status
async function updateQueueStatus() {
    try {
        const response = await fetch('/queue');
        const data = await response.json();

        if (data.success) {
            const allItems = [
                ...data.downloading.map(d => ({...d, displayStatus: 'downloading'})),
                ...data.queued.map(q => ({...q, displayStatus: 'queued'})),
                ...data.completed.slice(-3).reverse().map(c => ({...c, displayStatus: 'completed'}))
            ];

            if (allItems.length > 0) {
                queueStatus.style.display = 'block';
                queueList.innerHTML = allItems.map(item => `
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
                        ` : ''}
                    </div>
                `).join('');
            } else {
                queueStatus.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to update queue status:', error);
    }
}

// Poll for specific job status
async function pollJobStatus(jobId) {
    if (!jobId) return;

    try {
        const response = await fetch(`/status/${jobId}`);
        const data = await response.json();

        if (data.success) {
            const status = data.status;

            // Update stats
            statValue1.textContent = status.status.toUpperCase();
            statLabel1.textContent = 'Status';

            if (status.status === 'queued') {
                statValue2.textContent = '⏳';
                statLabel2.textContent = 'In Queue';
            } else if (status.status === 'downloading') {
                const stepInfo = status.total_steps > 1
                    ? `Step ${status.step}/${status.total_steps}`
                    : 'Progress';
                statValue2.textContent = `${status.progress || 0}%`;
                statLabel2.textContent = stepInfo;
            } else if (status.status === 'completed') {
                statValue2.textContent = '✓';
                statLabel2.textContent = 'Done';
                clearInterval(statusInterval);
                responseDiv.className = 'response show success';
                responseTitle.textContent = '✓ Download Complete!';
                responseText.textContent = `File saved: ${status.filename || 'download'}`;
            } else if (status.status === 'failed') {
                statValue2.textContent = '✗';
                statLabel2.textContent = 'Failed';
                clearInterval(statusInterval);
                responseDiv.className = 'response show error';
                responseTitle.textContent = '✗ Download Failed';
                responseText.textContent = status.error || 'Unknown error occurred';
            }
        }
    } catch (error) {
        console.error('Failed to poll job status:', error);
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
            // Show success response
            responseDiv.className = 'response show success';
            responseTitle.textContent = '✓ Queued Successfully!';
            responseText.textContent = data.message;
            statsDiv.style.display = 'flex';

            // Update stats
            statValue1.textContent = 'QUEUED';
            statLabel1.textContent = 'Status';
            statValue2.textContent = data.queue_position || '-';
            statLabel2.textContent = 'Queue Position';

            // Start polling for this job
            activeJobId = data.job_id;
            if (statusInterval) clearInterval(statusInterval);
            statusInterval = setInterval(() => pollJobStatus(activeJobId), 1000);

            // Clear input
            textInput.value = '';
        } else {
            responseDiv.className = 'response show error';
            responseTitle.textContent = '✗ Error';
            responseText.textContent = data.message;
            statsDiv.style.display = 'none';
        }

    } catch (error) {
        responseDiv.className = 'response show error';
        responseTitle.textContent = '✗ Error';
        responseText.textContent = 'Failed to connect to the server. Please try again.';
        statsDiv.style.display = 'none';
    } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
    }
});

clearBtn.addEventListener('click', () => {
    textInput.value = '';
    responseDiv.classList.remove('show');
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
    activeJobId = null;
    textInput.focus();
});

// Update queue status every 2 seconds
setInterval(updateQueueStatus, 2000);
updateQueueStatus(); // Initial load

// Add subtle interaction feedback
textInput.addEventListener('input', () => {
    if (responseDiv.classList.contains('show')) {
        responseDiv.classList.remove('show');
    }
});

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
            // Async fetch details for each video
            fetchAllEpisodeDetails(limitedVideos);
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

function fetchAllEpisodeDetails(videos) {
    videos.forEach(video => {
        if (!video.title || !video.thumbnail) {
            fetchEpisodeInfo(video.url);
        }
    });
}

async function fetchEpisodeInfo(url) {
    try {
        const response = await fetch(`/dropout/info?episode=${encodeURIComponent(url)}`);
        const data = await response.json();

        if (data.success) {
            updateReleaseCard(url, data.info);
        }
    } catch (error) {
        console.error(`Failed to fetch info for ${url}:`, error);
    }
}

function updateReleaseCard(url, info) {
    const card = releasesGrid.querySelector(`[data-url="${url}"]`);
    if (!card) return;

    // Update thumbnail
    const img = card.querySelector('.release-thumbnail img');
    if (img && info.thumbnail) {
        img.src = info.thumbnail;
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
