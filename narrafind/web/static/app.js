/**
 * NarraFind — Web UI Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // ---------------------------------------------------------------
    // Elements — Search
    // ---------------------------------------------------------------
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const resultsSection = document.getElementById('results-section');
    const resultsGrid = document.getElementById('results-grid');
    const resultsTitle = document.getElementById('results-title');
    const resultsCount = document.getElementById('results-count');
    const headerStats = document.getElementById('header-stats');
    const videoModal = document.getElementById('video-modal');
    const modalClose = document.getElementById('modal-close');
    const modalVideo = document.getElementById('modal-video');
    const modalInfo = document.getElementById('modal-info');

    // ---------------------------------------------------------------
    // Elements — Tabs
    // ---------------------------------------------------------------
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    // ---------------------------------------------------------------
    // Elements — Index
    // ---------------------------------------------------------------
    const methodTabs = document.querySelectorAll('.method-tab');
    const methodPanels = document.querySelectorAll('.index-method');
    const indexPathInput = document.getElementById('index-path-input');
    const indexPathBtn = document.getElementById('index-path-btn');
    const uploadZone = document.getElementById('upload-zone');
    const uploadInput = document.getElementById('upload-input');
    const uploadFileList = document.getElementById('upload-file-list');
    const uploadActions = document.getElementById('upload-actions');
    const uploadStartBtn = document.getElementById('upload-start-btn');
    const indexProgress = document.getElementById('index-progress');
    const progressTitle = document.getElementById('progress-title');
    const progressStatus = document.getElementById('progress-status');
    const progressBar = document.getElementById('progress-bar');
    const progressFile = document.getElementById('progress-file');
    const progressStep = document.getElementById('progress-step');
    const progressLog = document.getElementById('progress-log');
    const progressSummary = document.getElementById('progress-summary');

    let selectedFiles = [];

    // Load stats on page load
    loadStats();

    // ---------------------------------------------------------------
    // Tab switching
    // ---------------------------------------------------------------
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`panel-${tab}`).classList.add('active');
        });
    });

    // Method tab switching (path / upload)
    methodTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const method = tab.dataset.method;
            methodTabs.forEach(t => t.classList.remove('active'));
            methodPanels.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`method-${method}`).classList.add('active');
        });
    });

    // ---------------------------------------------------------------
    // Search events
    // ---------------------------------------------------------------
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    modalClose.addEventListener('click', closeModal);
    videoModal.addEventListener('click', (e) => {
        if (e.target === videoModal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // ---------------------------------------------------------------
    // Index events — Path
    // ---------------------------------------------------------------
    indexPathBtn.addEventListener('click', indexFromPath);
    indexPathInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') indexFromPath();
    });

    // ---------------------------------------------------------------
    // Index events — Upload
    // ---------------------------------------------------------------
    uploadZone.addEventListener('click', () => uploadInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('drag-over');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('drag-over');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });
    uploadInput.addEventListener('change', () => {
        handleFiles(uploadInput.files);
        uploadInput.value = '';
    });
    uploadStartBtn.addEventListener('click', indexFromUpload);

    // ---------------------------------------------------------------
    // Stats
    // ---------------------------------------------------------------
    let currentStats = null;

    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            currentStats = data;

            if (data.total_chunks > 0) {
                headerStats.innerHTML = `
                    <span class="stat-badge" title="Click to view indexed files">
                        📁 <span class="stat-value">${data.unique_source_files}</span> files
                    </span>
                    <span class="stat-badge" title="Click to view indexed files">
                        🎬 <span class="stat-value">${data.visual_chunks}</span> visual
                    </span>
                    <span class="stat-badge" title="Click to view indexed files">
                        🎙️ <span class="stat-value">${data.speech_chunks}</span> speech
                    </span>
                `;
            } else {
                headerStats.innerHTML = `
                    <span class="stat-badge">No videos indexed yet</span>
                `;
            }
        } catch (e) {
            console.error('Failed to load stats:', e);
        }
    }

    // Stats Modal Logic
    const statsModal = document.getElementById('stats-modal');
    const statsModalClose = document.getElementById('stats-modal-close');
    const statsFileList = document.getElementById('stats-file-list');

    headerStats.addEventListener('click', () => {
        renderStatsModal();
        statsModal.style.display = 'flex';
    });

    function renderStatsModal() {
        if (!currentStats || currentStats.unique_source_files === 0) {
            statsModal.style.display = 'none';
            return;
        }
        
        statsFileList.innerHTML = currentStats.source_files.map((file, idx) => {
            const pathParts = file.split('/');
            const filename = pathParts.pop();
            const directory = pathParts.join('/');
            
            return `
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 12px; font-size: 0.85rem; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
                    <div style="flex: 1; min-width: 0;">
                        <div style="color: var(--text-primary); font-weight: 500; word-break: break-all; margin-bottom: 4px;">🎬 ${escapeHtml(filename)}</div>
                        <div style="color: var(--text-muted); font-size: 0.75rem; word-break: break-all;">${escapeHtml(directory)}/</div>
                    </div>
                    <button onclick="window.narrafindDeleteFile('${escapeHtml(file.replace(/'/g, "\\'"))}')" title="Delete this video from index" style="background: none; border: none; color: var(--accent-rose); cursor: pointer; padding: 4px; font-size: 1.1rem; opacity: 0.7; transition: opacity 0.2s;">
                        🗑️
                    </button>
                </div>
            `;
        }).join('');
    }

    window.narrafindDeleteFile = async function(sourceFile) {
        if (!confirm('Are you sure you want to remove this video from the search index?')) {
            return;
        }

        try {
            const res = await fetch('/api/index', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_file: sourceFile }),
            });

            const data = await res.json();
            if (data.error) {
                alert('Delete failed: ' + data.error);
                return;
            }

            // Remove file locally and re-render
            currentStats.source_files = currentStats.source_files.filter(f => f !== sourceFile);
            currentStats.unique_source_files -= 1;
            
            currentStats.total_chunks -= data.removed_chunks;
            // Note: we can't accurately dynamically update visual_chunks vs speech_chunks here 
            // without a full re-fetch, so let's just trigger a full stats reload
            await loadStats();
            renderStatsModal();

            if (currentStats.unique_source_files === 0) {
                statsModal.style.display = 'none';
            }
        } catch (e) {
            alert('Delete failed: ' + e.message);
        }
    };

    statsModalClose.addEventListener('click', () => {
        statsModal.style.display = 'none';
    });

    statsModal.addEventListener('click', (e) => {
        if (e.target === statsModal) {
            statsModal.style.display = 'none';
        }
    });

    // ---------------------------------------------------------------
    // Search
    // ---------------------------------------------------------------
    async function performSearch() {
        const query = searchInput.value.trim();
        if (!query) return;

        const mode = document.querySelector('input[name="mode"]:checked').value;

        searchBtn.disabled = true;
        searchBtn.querySelector('.btn-text').style.display = 'none';
        searchBtn.querySelector('.btn-loader').style.display = 'flex';

        try {
            const res = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, mode, n_results: 10 }),
            });

            const data = await res.json();

            if (data.error) {
                showError(data.error);
                return;
            }

            displayResults(data.results, query, mode);
        } catch (e) {
            showError('Search failed. Make sure the server is running.');
        } finally {
            searchBtn.disabled = false;
            searchBtn.querySelector('.btn-text').style.display = 'inline';
            searchBtn.querySelector('.btn-loader').style.display = 'none';
        }
    }

    // ---------------------------------------------------------------
    // Display Results
    // ---------------------------------------------------------------
    function displayResults(results, query, mode) {
        resultsSection.style.display = 'block';

        if (results.length === 0) {
            resultsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>No results found for "${escapeHtml(query)}"</p>
                    <p style="margin-top:8px;font-size:0.8rem;">Try a different query or search mode</p>
                </div>
            `;
            resultsTitle.textContent = 'No matches';
            resultsCount.textContent = '';
            return;
        }

        resultsTitle.textContent = `Results for "${query}"`;
        resultsCount.textContent = `${results.length} match${results.length > 1 ? 'es' : ''}`;

        resultsGrid.innerHTML = results.map((r, i) => {
            const rankClass = i < 3 ? `rank-${i + 1}` : 'rank-default';
            const scoreClass = r.score >= 0.6 ? 'score-high' : r.score >= 0.4 ? 'score-medium' : 'score-low';
            const badgeClass = r.search_type === 'visual' ? 'badge-visual'
                : r.search_type === 'speech' ? 'badge-speech'
                : 'badge-hybrid';

            let transcriptHtml = '';
            if (r.transcript) {
                const truncated = r.transcript.length > 150
                    ? r.transcript.substring(0, 150) + '...'
                    : r.transcript;
                transcriptHtml = `<div class="result-transcript">💬 "${escapeHtml(truncated)}"</div>`;
            }

            return `
                <div class="result-card" data-index="${i}" onclick="window.narrafindOpenResult(${i})">
                    <div class="result-rank ${rankClass}">#${i + 1}</div>
                    <div class="result-info">
                        <div class="result-filename">${escapeHtml(r.filename)}</div>
                        <div class="result-meta">
                            <span class="result-time">⏱ ${r.start_formatted} — ${r.end_formatted}</span>
                            <span class="result-type-badge ${badgeClass}">${r.search_type || 'unknown'}</span>
                        </div>
                        ${transcriptHtml}
                    </div>
                    <div class="result-score">
                        <div class="score-value ${scoreClass}">${(r.score * 100).toFixed(1)}%</div>
                        <div class="score-label">match</div>
                    </div>
                    <div class="result-play">
                        <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
                    </div>
                </div>
            `;
        }).join('');

        window._narrafindResults = results;
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // ---------------------------------------------------------------
    // Open Result (Video Modal)
    // ---------------------------------------------------------------
    window.narrafindOpenResult = async function(index) {
        const r = window._narrafindResults[index];
        if (!r) return;

        const videoUrl = `/api/video?path=${encodeURIComponent(r.source_file)}`;
        modalVideo.src = videoUrl;

        let infoHtml = `
            <div class="modal-filename">${escapeHtml(r.filename)}</div>
            <div class="modal-details">
                <span>⏱ ${r.start_formatted} — ${r.end_formatted}</span>
                <span>Score: ${(r.score * 100).toFixed(1)}%</span>
                <span>Type: ${r.search_type}</span>
            </div>
        `;

        if (r.transcript) {
            infoHtml += `<div class="modal-transcript">💬 "${escapeHtml(r.transcript)}"</div>`;
        }

        infoHtml += `
            <div class="modal-actions">
                <button class="btn-trim" onclick="window.narrafindTrimClip(${index})">
                    ✂️ Save Clip
                </button>
            </div>
        `;

        modalInfo.innerHTML = infoHtml;
        videoModal.style.display = 'flex';

        modalVideo.addEventListener('loadedmetadata', function onLoaded() {
            modalVideo.currentTime = r.start_time;
            modalVideo.play();
            modalVideo.removeEventListener('loadedmetadata', onLoaded);
            
            // Auto pause playback when reaching the end of the segment
            const timeUpdateHandler = () => {
                if (modalVideo.currentTime >= r.end_time) {
                    modalVideo.pause();
                    modalVideo.removeEventListener('timeupdate', timeUpdateHandler);
                }
            };
            // Clear any previous listener by assigning to a property, or just use addeventlistener
            if (modalVideo._timeUpdateHandler) {
                modalVideo.removeEventListener('timeupdate', modalVideo._timeUpdateHandler);
            }
            modalVideo._timeUpdateHandler = timeUpdateHandler;
            modalVideo.addEventListener('timeupdate', timeUpdateHandler);
        });
    };

    // ---------------------------------------------------------------
    // Trim Clip
    // ---------------------------------------------------------------
    window.narrafindTrimClip = async function(index) {
        const r = window._narrafindResults[index];
        if (!r) return;

        const trimBtn = document.querySelector('.btn-trim');
        if (trimBtn) {
            trimBtn.disabled = true;
            trimBtn.textContent = '⏳ Trimming...';
        }

        try {
            const res = await fetch('/api/trim', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_file: r.source_file,
                    start_time: r.start_time,
                    end_time: r.end_time,
                }),
            });

            const data = await res.json();
            if (data.error) {
                alert('Trim failed: ' + data.error);
                return;
            }

            // Play the trimmed clip
            modalVideo.src = data.clip_url;
            modalVideo.currentTime = 0;
            modalVideo.play();

            // Trigger actual browser download
            const a = document.createElement('a');
            a.href = data.clip_url;
            // Extract filename from URL
            a.download = data.clip_url.split('/').pop() || 'trimmed_clip.mp4';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            if (trimBtn) {
                trimBtn.textContent = '✅ Clip Saved!';
                setTimeout(() => {
                    trimBtn.textContent = '✂️ Save Clip';
                    trimBtn.disabled = false;
                }, 2000);
            }
        } catch (e) {
            alert('Trim failed: ' + e.message);
        } finally {
            if (trimBtn) trimBtn.disabled = false;
        }
    };

    // ---------------------------------------------------------------
    // Modal
    // ---------------------------------------------------------------
    function closeModal() {
        videoModal.style.display = 'none';
        modalVideo.pause();
        modalVideo.src = '';
    }

    // ===============================================================
    // INDEX — Path
    // ===============================================================
    async function indexFromPath() {
        const path = indexPathInput.value.trim();
        if (!path) return;

        const speech = document.getElementById('index-speech').checked;
        const chunkDuration = parseInt(document.getElementById('index-chunk-duration').value);

        setIndexBtnLoading(indexPathBtn, true);

        try {
            const res = await fetch('/api/index/path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path,
                    speech,
                    chunk_duration: chunkDuration,
                }),
            });

            const data = await res.json();
            if (data.error) {
                alert(data.error);
                setIndexBtnLoading(indexPathBtn, false);
                return;
            }

            startProgressPolling(data.job_id, data.filenames);
        } catch (e) {
            alert('Failed to start indexing: ' + e.message);
        } finally {
            setIndexBtnLoading(indexPathBtn, false);
        }
    }

    // ===============================================================
    // INDEX — Upload
    // ===============================================================
    function handleFiles(fileList) {
        for (const file of fileList) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (['mp4', 'mov', 'mkv', 'webm', 'avi'].includes(ext)) {
                if (!selectedFiles.find(f => f.name === file.name)) {
                    selectedFiles.push(file);
                }
            }
        }
        renderFileList();
    }

    function renderFileList() {
        if (selectedFiles.length === 0) {
            uploadFileList.style.display = 'none';
            uploadActions.style.display = 'none';
            return;
        }

        uploadFileList.style.display = 'flex';
        uploadActions.style.display = 'flex';

        uploadFileList.innerHTML = selectedFiles.map((f, i) => `
            <div class="upload-file-item">
                <span>🎬</span>
                <span class="upload-file-name">${escapeHtml(f.name)}</span>
                <span class="upload-file-size">${formatFileSize(f.size)}</span>
                <button class="upload-file-remove" onclick="window.narrafindRemoveFile(${i})">×</button>
            </div>
        `).join('');
    }

    window.narrafindRemoveFile = function(index) {
        selectedFiles.splice(index, 1);
        renderFileList();
    };

    async function indexFromUpload() {
        if (selectedFiles.length === 0) return;

        const speech = document.getElementById('upload-speech').checked;

        setIndexBtnLoading(uploadStartBtn, true);

        const formData = new FormData();
        for (const file of selectedFiles) {
            formData.append('videos', file);
        }
        formData.append('speech', speech ? 'true' : 'false');

        try {
            const res = await fetch('/api/index/upload', {
                method: 'POST',
                body: formData,
            });

            const data = await res.json();
            if (data.error) {
                alert(data.error);
                setIndexBtnLoading(uploadStartBtn, false);
                return;
            }

            selectedFiles = [];
            renderFileList();
            startProgressPolling(data.job_id, data.filenames);
        } catch (e) {
            alert('Upload failed: ' + e.message);
        } finally {
            setIndexBtnLoading(uploadStartBtn, false);
        }
    }

    // ===============================================================
    // Progress Polling
    // ===============================================================
    let pollInterval = null;
    let lastLogCount = 0;

    function startProgressPolling(jobId, filenames) {
        indexProgress.style.display = 'block';
        progressSummary.style.display = 'none';
        progressLog.innerHTML = '';
        progressTitle.textContent = `Indexing ${filenames.length} file${filenames.length > 1 ? 's' : ''}...`;
        progressStatus.textContent = 'Starting';
        progressStatus.className = 'progress-status status-running';
        progressBar.style.width = '0%';
        progressFile.textContent = '';
        progressStep.textContent = '';
        lastLogCount = 0;

        indexProgress.scrollIntoView({ behavior: 'smooth', block: 'start' });

        pollInterval = setInterval(() => pollProgress(jobId), 1000);
    }

    async function pollProgress(jobId) {
        try {
            const res = await fetch(`/api/index/status/${jobId}`);
            const job = await res.json();

            if (job.error && job.status !== 'running' && job.status !== 'done') {
                // Job-level error from API (not found etc.)
                clearInterval(pollInterval);
                return;
            }

            // Update progress bar
            const pct = job.total > 0 ? (job.progress / job.total) * 100 : 0;
            progressBar.style.width = `${Math.min(pct, 100)}%`;

            // Update details
            progressFile.textContent = job.current_file ? `📹 ${job.current_file}` : '';
            progressStep.textContent = job.current_step || '';

            // Update logs (only append new ones)
            if (job.logs && job.logs.length > lastLogCount) {
                const newLogs = job.logs.slice(lastLogCount);
                for (const log of newLogs) {
                    progressLog.innerHTML += escapeHtml(log) + '\n';
                }
                progressLog.scrollTop = progressLog.scrollHeight;
                lastLogCount = job.logs.length;
            }

            // Check completion
            if (job.status === 'done') {
                clearInterval(pollInterval);
                progressBar.style.width = '100%';
                progressTitle.textContent = 'Indexing Complete!';
                progressStatus.textContent = 'Done';
                progressStatus.className = 'progress-status status-done';
                progressFile.textContent = '';
                progressStep.textContent = '';

                // Show summary
                progressSummary.style.display = 'block';
                document.getElementById('summary-visual').textContent = job.visual_chunks;
                document.getElementById('summary-speech').textContent = job.speech_chunks;
                document.getElementById('summary-skipped').textContent = job.skipped_files;

                // Reload stats
                loadStats();
            } else if (job.status === 'error') {
                clearInterval(pollInterval);
                progressTitle.textContent = 'Indexing Failed';
                progressStatus.textContent = 'Error';
                progressStatus.className = 'progress-status status-error';

                if (job.error) {
                    progressLog.innerHTML += `\n❌ ${escapeHtml(job.error)}\n`;
                }
            } else {
                progressStatus.textContent = `${job.progress}/${job.total}`;
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }

    // ---------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------
    function showError(message) {
        resultsSection.style.display = 'block';
        resultsGrid.innerHTML = `<div class="error-message">⚠️ ${escapeHtml(message)}</div>`;
        resultsTitle.textContent = 'Error';
        resultsCount.textContent = '';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    }

    function setIndexBtnLoading(btn, loading) {
        btn.disabled = loading;
        btn.querySelector('.btn-text').style.display = loading ? 'none' : 'inline';
        btn.querySelector('.btn-loader').style.display = loading ? 'flex' : 'none';
    }
});
