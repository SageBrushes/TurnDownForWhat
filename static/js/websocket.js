/**
 * WebSocket Client for Sonos TTS Control Center
 * Handles real-time updates from the backend
 */

class WebSocketClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.messageHandlers = new Map();
        this.connectionStatus = 'disconnected';
    }

    /**
     * Connect to the WebSocket server
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('[WebSocket] Connecting to:', wsUrl);
        this.updateConnectionStatus('connecting');

        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('[WebSocket] Connection error:', error);
            this.handleReconnect();
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('[WebSocket] Connected successfully');
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            this.updateConnectionStatus('connected');
            this.triggerHandler('connection', { status: 'connected' });
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                console.log('[WebSocket] Received message:', message);
                this.handleMessage(message);
            } catch (error) {
                console.error('[WebSocket] Failed to parse message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('[WebSocket] Error:', error);
            this.updateConnectionStatus('error');
        };

        this.ws.onclose = (event) => {
            console.log('[WebSocket] Connection closed:', event.code, event.reason);
            this.updateConnectionStatus('disconnected');
            this.triggerHandler('connection', { status: 'disconnected' });

            // Attempt to reconnect if not a clean close
            if (!event.wasClean) {
                this.handleReconnect();
            }
        };
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(message) {
        const { type, data } = message;

        switch (type) {
            case 'speaker_update':
                this.triggerHandler('speaker_update', data);
                break;

            case 'fade_progress':
                this.triggerHandler('fade_progress', data);
                break;

            case 'tts_started':
                this.triggerHandler('tts_started', data);
                break;

            case 'tts_completed':
                this.triggerHandler('tts_completed', data);
                break;

            case 'error':
                this.triggerHandler('error', data);
                break;

            default:
                console.warn('[WebSocket] Unknown message type:', type);
        }
    }

    /**
     * Register a message handler
     * @param {string} type - Message type to handle
     * @param {Function} handler - Handler function
     */
    on(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
    }

    /**
     * Unregister a message handler
     * @param {string} type - Message type
     * @param {Function} handler - Handler function to remove
     */
    off(type, handler) {
        if (!this.messageHandlers.has(type)) return;

        const handlers = this.messageHandlers.get(type);
        const index = handlers.indexOf(handler);
        if (index > -1) {
            handlers.splice(index, 1);
        }
    }

    /**
     * Trigger all handlers for a message type
     */
    triggerHandler(type, data) {
        if (!this.messageHandlers.has(type)) return;

        const handlers = this.messageHandlers.get(type);
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`[WebSocket] Handler error for ${type}:`, error);
            }
        });
    }

    /**
     * Send a message to the server
     * @param {Object} message - Message to send
     */
    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('[WebSocket] Cannot send message - not connected');
        }
    }

    /**
     * Handle reconnection logic
     */
    handleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[WebSocket] Max reconnection attempts reached');
            this.updateConnectionStatus('failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.updateConnectionStatus('reconnecting');

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(status) {
        this.connectionStatus = status;

        const indicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        if (!indicator || !statusText) return;

        switch (status) {
            case 'connected':
                indicator.className = 'w-3 h-3 rounded-full bg-green-500';
                statusText.textContent = 'Connected';
                break;

            case 'connecting':
            case 'reconnecting':
                indicator.className = 'w-3 h-3 rounded-full bg-yellow-500 animate-pulse';
                statusText.textContent = status === 'connecting' ? 'Connecting...' : 'Reconnecting...';
                break;

            case 'disconnected':
                indicator.className = 'w-3 h-3 rounded-full bg-gray-400';
                statusText.textContent = 'Disconnected';
                break;

            case 'error':
            case 'failed':
                indicator.className = 'w-3 h-3 rounded-full bg-red-500';
                statusText.textContent = 'Connection Failed';
                break;
        }
    }

    /**
     * Close the WebSocket connection
     */
    close() {
        if (this.ws) {
            this.ws.close(1000, 'Client closed connection');
            this.ws = null;
        }
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Export singleton instance
const wsClient = new WebSocketClient();

// Auto-connect on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        wsClient.connect();
    });
} else {
    wsClient.connect();
}
