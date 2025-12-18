/**
 * Main Application Logic for Sonos TTS Control Center
 * Handles speaker management, TTS generation, and UI updates
 */

class SonosApp {
    constructor() {
        this.speakers = new Map();
        this.voices = [];
        this.isLoadingSpeakers = false;
        this.isTTSGenerating = false;
        this.volumeDebounceTimers = new Map();
        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('[App] Initializing Sonos Control Center');

        // Setup event listeners
        this.setupEventListeners();

        // Setup WebSocket handlers
        this.setupWebSocketHandlers();

        // Load initial data
        await Promise.all([
            this.loadSpeakers(),
            this.loadVoices()
        ]);

        console.log('[App] Initialization complete');
    }

    /**
     * Setup DOM event listeners
     */
    setupEventListeners() {
        // TTS Form
        const ttsForm = document.getElementById('tts-form');
        const ttsText = document.getElementById('tts-text');
        const charCount = document.getElementById('char-count');

        if (ttsForm) {
            ttsForm.addEventListener('submit', (e) => this.handleTTSSubmit(e));
        }

        if (ttsText && charCount) {
            ttsText.addEventListener('input', (e) => {
                charCount.textContent = e.target.value.length;
            });
        }

        // Master Controls
        const fadeAllBtn = document.getElementById('fade-all-btn');
        const stopAllBtn = document.getElementById('stop-all-btn');
        const refreshBtn = document.getElementById('refresh-speakers-btn');

        if (fadeAllBtn) {
            fadeAllBtn.addEventListener('click', () => this.handleFadeAll());
        }

        if (stopAllBtn) {
            stopAllBtn.addEventListener('click', () => this.handleStopAll());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadSpeakers());
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupWebSocketHandlers() {
        // Connection status
        wsClient.on('connection', (data) => {
            console.log('[App] WebSocket connection status:', data.status);
            if (data.status === 'connected') {
                // Refresh speakers when reconnected
                this.loadSpeakers();
            }
        });

        // Speaker updates
        wsClient.on('speaker_update', (data) => {
            console.log('[App] Speaker update received:', data);
            this.updateSpeakerUI(data);
        });

        // Fade progress
        wsClient.on('fade_progress', (data) => {
            console.log('[App] Fade progress:', data);
            this.updateFadeProgress(data);
        });

        // TTS events
        wsClient.on('tts_started', (data) => {
            console.log('[App] TTS started:', data);
            this.showSuccessToast('TTS generation started');
        });

        wsClient.on('tts_completed', (data) => {
            console.log('[App] TTS completed:', data);
            this.showSuccessToast('TTS playback completed');
        });

        // Errors
        wsClient.on('error', (data) => {
            console.error('[App] WebSocket error:', data);
            this.showErrorToast('Error', data.message || 'An error occurred');
        });
    }

    /**
     * Load speakers from the API
     */
    async loadSpeakers() {
        if (this.isLoadingSpeakers) {
            console.log('[App] Already loading speakers, skipping');
            return;
        }

        this.isLoadingSpeakers = true;
        console.log('[App] Loading speakers...');

        try {
            const response = await fetch('/api/speakers');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('[App] Speakers loaded:', data);

            // Update speakers map
            this.speakers.clear();
            // Handle both array and object with speakers property
            const speakersArray = Array.isArray(data) ? data : (data.speakers || []);
            speakersArray.forEach(speaker => {
                this.speakers.set(speaker.ip, speaker);
            });

            // Render speakers
            this.renderSpeakers();

            // Update speaker select dropdown
            this.updateSpeakerSelect();

        } catch (error) {
            console.error('[App] Failed to load speakers:', error);
            this.showErrorToast('Failed to Load Speakers', error.message);
        } finally {
            this.isLoadingSpeakers = false;
        }
    }

    /**
     * Load available TTS voices
     */
    async loadVoices() {
        console.log('[App] Loading voices...');

        try {
            const response = await fetch('/api/tts/voices');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('[App] Voices loaded:', data);

            // Handle both array and object with voices property
            this.voices = Array.isArray(data) ? data : (data.voices || []);
            this.updateVoiceSelect();

        } catch (error) {
            console.error('[App] Failed to load voices:', error);
            this.showErrorToast('Failed to Load Voices', error.message);
        }
    }

    /**
     * Render speakers in the grid
     */
    renderSpeakers() {
        const grid = document.getElementById('speakers-grid');
        if (!grid) return;

        // Clear existing content
        grid.innerHTML = '';

        if (this.speakers.size === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <p class="text-gray-500">No speakers found</p>
                    <button onclick="app.loadSpeakers()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                        Retry
                    </button>
                </div>
            `;
            return;
        }

        // Render each speaker
        this.speakers.forEach(speaker => {
            const card = this.createSpeakerCard(speaker);
            grid.appendChild(card);
        });
    }

    /**
     * Create a speaker card element
     */
    createSpeakerCard(speaker) {
        const template = document.getElementById('speaker-card-template');
        const card = template.content.cloneNode(true).querySelector('.speaker-card');

        // Set speaker IP as data attribute
        card.setAttribute('data-speaker-ip', speaker.ip);

        // Populate card data
        card.querySelector('.speaker-name').textContent = speaker.name || 'Unknown Speaker';
        card.querySelector('.speaker-ip').textContent = speaker.ip;

        // Set status emoji
        const statusEmoji = this.getStatusEmoji(speaker.state);
        card.querySelector('.speaker-status').textContent = statusEmoji;
        card.querySelector('.speaker-status').setAttribute('title', speaker.state || 'Unknown');

        // Set volume
        const volumeSlider = card.querySelector('.speaker-volume-slider');
        const volumeValue = card.querySelector('.speaker-volume-value');
        const volume = speaker.volume || 0;
        volumeSlider.value = volume;
        volumeValue.textContent = `${volume}%`;

        // Set track info
        const trackInfo = speaker.track_info || speaker.current_track || 'Nothing playing';
        card.querySelector('.speaker-track').textContent = trackInfo;

        // Setup volume slider handler
        volumeSlider.addEventListener('input', (e) => {
            const newVolume = parseInt(e.target.value);
            volumeValue.textContent = `${newVolume}%`;
            this.handleVolumeChange(speaker.ip, newVolume);
        });

        // Setup control buttons
        card.querySelector('.speaker-play-btn').addEventListener('click', () => {
            this.handlePlaybackControl(speaker.ip, 'play');
        });

        card.querySelector('.speaker-pause-btn').addEventListener('click', () => {
            this.handlePlaybackControl(speaker.ip, 'pause');
        });

        card.querySelector('.speaker-stop-btn').addEventListener('click', () => {
            this.handlePlaybackControl(speaker.ip, 'stop');
        });

        card.querySelector('.speaker-fade-btn').addEventListener('click', () => {
            this.handleFadeSpeaker(speaker.ip);
        });

        card.querySelector('.speaker-tts-btn').addEventListener('click', () => {
            this.handleQuickTTS(speaker.ip);
        });

        return card;
    }

    /**
     * Get status emoji based on playback state
     */
    getStatusEmoji(state) {
        const emojiMap = {
            'PLAYING': '▶️',
            'PAUSED_PLAYBACK': '⏸️',
            'STOPPED': '⏹️',
            'TRANSITIONING': '⏳'
        };
        return emojiMap[state] || '❓';
    }

    /**
     * Update speaker card UI with new data
     */
    updateSpeakerUI(speakerData) {
        const { ip } = speakerData;

        // Update speakers map
        this.speakers.set(ip, speakerData);

        // Find the card in the DOM
        const card = document.querySelector(`[data-speaker-ip="${ip}"]`);
        if (!card) {
            console.warn('[App] Speaker card not found for IP:', ip);
            // Re-render all speakers if card is missing
            this.renderSpeakers();
            return;
        }

        // Update name
        if (speakerData.name) {
            card.querySelector('.speaker-name').textContent = speakerData.name;
        }

        // Update status
        if (speakerData.state) {
            const statusEmoji = this.getStatusEmoji(speakerData.state);
            const statusElement = card.querySelector('.speaker-status');
            statusElement.textContent = statusEmoji;
            statusElement.setAttribute('title', speakerData.state);

            // Add visual indicator for playing state
            if (speakerData.state === 'PLAYING') {
                card.classList.add('speaker-playing');
            } else {
                card.classList.remove('speaker-playing');
            }
        }

        // Update volume
        if (typeof speakerData.volume === 'number') {
            const volumeSlider = card.querySelector('.speaker-volume-slider');
            const volumeValue = card.querySelector('.speaker-volume-value');
            volumeSlider.value = speakerData.volume;
            volumeValue.textContent = `${speakerData.volume}%`;
        }

        // Update track info
        if (speakerData.track_info !== undefined || speakerData.current_track !== undefined) {
            const trackInfo = speakerData.track_info || speakerData.current_track || 'Nothing playing';
            card.querySelector('.speaker-track').textContent = trackInfo;
        }
    }

    /**
     * Update fade progress visualization
     */
    updateFadeProgress(data) {
        const { ip, current_volume, target_volume, progress } = data;
        const card = document.querySelector(`[data-speaker-ip="${ip}"]`);

        if (!card) return;

        const volumeSlider = card.querySelector('.speaker-volume-slider');
        const volumeValue = card.querySelector('.speaker-volume-value');

        if (volumeSlider && volumeValue) {
            volumeSlider.value = current_volume;
            volumeValue.textContent = `${current_volume}%`;

            // Add visual feedback during fade
            volumeSlider.classList.add('fading');
            card.classList.add('speaker-fading');

            // Remove fading class when complete
            if (progress >= 100 || current_volume === target_volume) {
                volumeSlider.classList.remove('fading');
                card.classList.remove('speaker-fading');
            }
        }
    }

    /**
     * Handle volume change with debouncing
     */
    handleVolumeChange(ip, volume) {
        // Clear existing timer for this speaker
        if (this.volumeDebounceTimers.has(ip)) {
            clearTimeout(this.volumeDebounceTimers.get(ip));
        }

        // Set new timer
        const timer = setTimeout(async () => {
            console.log(`[App] Setting volume for ${ip} to ${volume}`);
            try {
                const response = await fetch(`/api/speakers/${ip}/volume`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ volume })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const result = await response.json();
                console.log('[App] Volume set successfully:', result);

            } catch (error) {
                console.error('[App] Failed to set volume:', error);
                this.showErrorToast('Volume Error', error.message);
            } finally {
                this.volumeDebounceTimers.delete(ip);
            }
        }, 300); // 300ms debounce

        this.volumeDebounceTimers.set(ip, timer);
    }

    /**
     * Handle playback controls (play/pause/stop)
     */
    async handlePlaybackControl(ip, action) {
        console.log(`[App] Playback control: ${action} for ${ip}`);

        try {
            const response = await fetch(`/api/speakers/${ip}/${action}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('[App] Playback control successful:', result);
            this.showSuccessToast(`${action.charAt(0).toUpperCase() + action.slice(1)} successful`);

        } catch (error) {
            console.error('[App] Playback control failed:', error);
            this.showErrorToast('Playback Error', error.message);
        }
    }

    /**
     * Handle fade to 0% for a single speaker
     */
    async handleFadeSpeaker(ip) {
        console.log(`[App] Fading speaker ${ip} to 0%`);

        try {
            const response = await fetch(`/api/speakers/${ip}/fade`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    target_volume: 0,
                    duration: 5 // 5 seconds default
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('[App] Fade started:', result);
            this.showSuccessToast('Fade started');

            // Add visual feedback
            const card = document.querySelector(`[data-speaker-ip="${ip}"]`);
            if (card) {
                const slider = card.querySelector('.speaker-volume-slider');
                if (slider) {
                    slider.classList.add('fading');
                    setTimeout(() => slider.classList.remove('fading'), 5000);
                }
            }

        } catch (error) {
            console.error('[App] Fade failed:', error);
            this.showErrorToast('Fade Error', error.message);
        }
    }

    /**
     * Handle quick TTS for a specific speaker
     */
    async handleQuickTTS(ip) {
        const text = prompt('Enter text to speak:');
        if (!text) return;

        console.log(`[App] Quick TTS for ${ip}:`, text);

        try {
            const response = await fetch('/api/tts/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text,
                    speaker_ips: [ip],
                    voice: this.voices[0]?.id || this.voices[0] || undefined
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('[App] Quick TTS successful:', result);
            this.showSuccessToast('TTS generated and playing');

        } catch (error) {
            console.error('[App] Quick TTS failed:', error);
            this.showErrorToast('TTS Error', error.message);
        }
    }

    /**
     * Handle TTS form submission
     */
    async handleTTSSubmit(event) {
        event.preventDefault();

        if (this.isTTSGenerating) {
            console.log('[App] TTS generation already in progress');
            return;
        }

        const form = event.target;
        const formData = new FormData(form);

        const text = formData.get('text');
        const voice = formData.get('voice');
        const speakerSelect = document.getElementById('speaker-select');
        const selectedOptions = Array.from(speakerSelect.selectedOptions);
        const speakers = selectedOptions.map(opt => opt.value).filter(v => v);

        // Validation
        if (!text || !text.trim()) {
            this.showErrorToast('Validation Error', 'Please enter text to speak');
            return;
        }

        if (speakers.length === 0) {
            this.showErrorToast('Validation Error', 'Please select at least one speaker');
            return;
        }

        this.isTTSGenerating = true;
        this.setTTSButtonLoading(true);

        console.log('[App] Generating TTS:', { text, voice, speakers });

        try {
            const response = await fetch('/api/tts/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text.trim(),
                    speaker_ips: speakers,
                    voice: voice || undefined
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('[App] TTS generated successfully:', result);
            this.showSuccessToast('TTS generated and playing on selected speakers');

            // Optionally clear the form
            // form.reset();
            // document.getElementById('char-count').textContent = '0';

        } catch (error) {
            console.error('[App] TTS generation failed:', error);
            this.showErrorToast('TTS Generation Failed', error.message);
        } finally {
            this.isTTSGenerating = false;
            this.setTTSButtonLoading(false);
        }
    }

    /**
     * Set TTS button loading state
     */
    setTTSButtonLoading(loading) {
        const btn = document.getElementById('tts-submit-btn');
        const btnText = document.getElementById('tts-btn-text');
        const btnSpinner = document.getElementById('tts-btn-spinner');

        if (!btn || !btnText || !btnSpinner) return;

        if (loading) {
            btn.disabled = true;
            btnText.textContent = 'Generating...';
            btnSpinner.classList.remove('hidden');
        } else {
            btn.disabled = false;
            btnText.textContent = 'Generate & Play';
            btnSpinner.classList.add('hidden');
        }
    }

    /**
     * Handle fade all speakers to 0%
     */
    async handleFadeAll() {
        if (this.speakers.size === 0) {
            this.showErrorToast('No Speakers', 'No speakers available to fade');
            return;
        }

        console.log('[App] Fading all speakers to 0%');

        const fadePromises = Array.from(this.speakers.keys()).map(ip =>
            this.handleFadeSpeaker(ip)
        );

        try {
            await Promise.all(fadePromises);
            this.showSuccessToast('All speakers fading to 0%');
        } catch (error) {
            console.error('[App] Fade all failed:', error);
            this.showErrorToast('Fade All Error', 'Some speakers failed to fade');
        }
    }

    /**
     * Handle stop all speakers
     */
    async handleStopAll() {
        if (this.speakers.size === 0) {
            this.showErrorToast('No Speakers', 'No speakers available to stop');
            return;
        }

        console.log('[App] Stopping all speakers');

        const stopPromises = Array.from(this.speakers.keys()).map(ip =>
            this.handlePlaybackControl(ip, 'stop')
        );

        try {
            await Promise.all(stopPromises);
            this.showSuccessToast('All speakers stopped');
        } catch (error) {
            console.error('[App] Stop all failed:', error);
            this.showErrorToast('Stop All Error', 'Some speakers failed to stop');
        }
    }

    /**
     * Update speaker select dropdown
     */
    updateSpeakerSelect() {
        const select = document.getElementById('speaker-select');
        if (!select) return;

        // Clear existing options
        select.innerHTML = '';

        if (this.speakers.size === 0) {
            select.innerHTML = '<option value="">No speakers available</option>';
            return;
        }

        // Add speaker options
        this.speakers.forEach((speaker, ip) => {
            const option = document.createElement('option');
            option.value = ip;
            option.textContent = speaker.name || ip;
            select.appendChild(option);
        });
    }

    /**
     * Update voice select dropdown
     */
    updateVoiceSelect() {
        const select = document.getElementById('voice-select');
        if (!select) return;

        // Clear existing options
        select.innerHTML = '';

        if (this.voices.length === 0) {
            select.innerHTML = '<option value="">No voices available</option>';
            return;
        }

        // Add voice options
        this.voices.forEach(voice => {
            const option = document.createElement('option');
            // Handle both {voice_id, name} objects and plain strings
            if (typeof voice === 'object' && (voice.voice_id || voice.id)) {
                option.value = voice.voice_id || voice.id;
                option.textContent = voice.name || voice.voice_id || voice.id;
            } else {
                option.value = voice;
                option.textContent = voice;
            }
            select.appendChild(option);
        });

        // Select first voice by default
        if (this.voices.length > 0) {
            const firstVoice = this.voices[0];
            select.value = typeof firstVoice === 'object' ? (firstVoice.voice_id || firstVoice.id) : firstVoice;
        }
    }

    /**
     * Show error toast notification
     */
    showErrorToast(title, message) {
        const toast = document.getElementById('error-toast');
        const toastTitle = document.getElementById('error-toast-title');
        const toastMessage = document.getElementById('error-toast-message');

        if (!toast || !toastTitle || !toastMessage) return;

        toastTitle.textContent = title;
        toastMessage.textContent = message;
        toast.classList.remove('hidden');

        // Auto-hide after 5 seconds
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 5000);
    }

    /**
     * Show success toast notification
     */
    showSuccessToast(message) {
        const toast = document.getElementById('success-toast');
        const toastMessage = document.getElementById('success-toast-message');

        if (!toast || !toastMessage) return;

        toastMessage.textContent = message;
        toast.classList.remove('hidden');

        // Auto-hide after 3 seconds
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }
}

// Initialize app when DOM is ready
let app;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        app = new SonosApp();
    });
} else {
    app = new SonosApp();
}
