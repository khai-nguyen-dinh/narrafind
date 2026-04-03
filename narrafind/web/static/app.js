/**
 * NarraFind — Web UI Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
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

    // Load stats on page load
    loadStats();

    // Event listeners
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
    // Stats
    // ---------------------------------------------------------------
    async function loadStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();

            if (data.total_chunks > 0) {
                headerStats.innerHTML = `
                    <span class="stat-badge">
                        📁 <span class="stat-value">${data.unique_source_files}</span> files
                    </span>
                    <span class="stat-badge">
                        🎬 <span class="stat-value">${data.visual_chunks}</span> visual
                    </span>
                    <span class="stat-badge">
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

    // ---------------------------------------------------------------
    // Search
    // ---------------------------------------------------------------
    async function performSearch() {
        const query = searchInput.value.trim();
        if (!query) return;

        const mode = document.querySelector('input[name="mode"]:checked').value;

        // UI: loading state
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
            console.error(e);
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

        // Store results for later use
        window._narrafindResults = results;

        // Smooth scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // ---------------------------------------------------------------
    // Open Result (Video Modal)
    // ---------------------------------------------------------------
    window.narrafindOpenResult = async function(index) {
        const r = window._narrafindResults[index];
        if (!r) return;

        // Set video source — play from the source file at the right timestamp
        const videoUrl = `/api/video?path=${encodeURIComponent(r.source_file)}`;
        modalVideo.src = videoUrl;
        modalVideo.currentTime = r.start_time;

        // Build modal info
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

        // Auto-play from start time
        modalVideo.addEventListener('loadedmetadata', function onLoaded() {
            modalVideo.currentTime = r.start_time;
            modalVideo.play();
            modalVideo.removeEventListener('loadedmetadata', onLoaded);
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
            if (trimBtn) {
                trimBtn.disabled = false;
            }
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
});
