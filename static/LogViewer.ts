/**
 * Log Viewer - Real-time log streaming via WebSocket
 */

interface LogMessage {
    type: 'initial' | 'update' | 'error';
    lines?: string[];
    total_lines?: number;
    message?: string;
}

class LogViewer {
    private container: HTMLElement;
    private logContainer: HTMLElement | null = null;
    private ws: WebSocket | null = null;
    private lines: string[] = [];
    private maxLines = 1000;
    private autoScroll = true;
    private isConnected = false;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;

    constructor(containerId: string, maxLines = 1000) {
        const element = document.getElementById(containerId);
        if (!element) {
            throw new Error(`Container element not found: ${containerId}`);
        }
        this.container = element;
        this.maxLines = maxLines;
        this.init();
    }

    private init(): void {
        this.render();
        this.connect();
    }

    private render(): void {
        this.container.innerHTML = `
      <div class="log-viewer">
        <div class="log-header">
          <h2>Application Logs</h2>
          <div class="log-controls">
            <label class="auto-scroll-label">
              <input type="checkbox" id="auto-scroll" checked>
              Auto-scroll
            </label>
            <button id="clear-logs" class="btn-secondary">Clear</button>
            <button id="reconnect" class="btn-primary" disabled>Reconnect</button>
            <span id="connection-status" class="status-indicator status-disconnected">Disconnected</span>
          </div>
        </div>
        <div id="log-content" class="log-content"></div>
        <div class="log-footer">
          <span id="line-count">0 lines</span>
        </div>
      </div>
    `;

        this.logContainer = document.getElementById('log-content');
        this.attachEventListeners();
    }

    private attachEventListeners(): void {
        const autoScrollCheckbox = document.getElementById('auto-scroll') as HTMLInputElement;
        const clearBtn = document.getElementById('clear-logs');
        const reconnectBtn = document.getElementById('reconnect');

        autoScrollCheckbox?.addEventListener('change', () => {
            this.autoScroll = autoScrollCheckbox.checked;
        });

        clearBtn?.addEventListener('click', () => {
            this.clearLogs();
        });

        reconnectBtn?.addEventListener('click', () => {
            this.connect();
        });

        // Handle scroll to detect manual scrolling
        this.logContainer?.addEventListener('scroll', () => {
            const { scrollTop, scrollHeight, clientHeight } = this.logContainer!;
            const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

            if (!isAtBottom && this.autoScroll) {
                // User scrolled up, disable auto-scroll
                this.autoScroll = false;
                (document.getElementById('auto-scroll') as HTMLInputElement).checked = false;
            }
        });
    }

    private connect(): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws/logs`;

        this.updateConnectionStatus('connecting');

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
                console.log('WebSocket connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data: LogMessage = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error');
            };

            this.ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                console.log('WebSocket disconnected');
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus('error');
        }
    }

    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

        console.log(`Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    private handleMessage(data: LogMessage): void {
        switch (data.type) {
            case 'initial':
                if (data.lines) {
                    this.lines = data.lines;
                    this.renderLogs();
                }
                break;
            case 'update':
                if (data.lines) {
                    this.addLines(data.lines);
                }
                break;
            case 'error':
                console.error('Log streaming error:', data.message);
                this.addLines([`[ERROR] ${data.message}`]);
                break;
        }
    }

    private addLines(newLines: string[]): void {
        this.lines.push(...newLines);

        // Trim to max lines
        if (this.lines.length > this.maxLines) {
            this.lines = this.lines.slice(-this.maxLines);
        }

        this.appendLogs(newLines);
    }

    private renderLogs(): void {
        if (!this.logContainer) return;

        const fragment = document.createDocumentFragment();
        for (const line of this.lines) {
            const lineEl = this.createLineElement(line);
            fragment.appendChild(lineEl);
        }

        this.logContainer.innerHTML = '';
        this.logContainer.appendChild(fragment);
        this.updateLineCount();
        this.scrollToBottom();
    }

    private appendLogs(newLines: string[]): void {
        if (!this.logContainer) return;

        const fragment = document.createDocumentFragment();
        for (const line of newLines) {
            const lineEl = this.createLineElement(line);
            fragment.appendChild(lineEl);
        }

        this.logContainer.appendChild(fragment);

        // Remove excess lines from DOM
        while (this.logContainer.children.length > this.maxLines) {
            this.logContainer.removeChild(this.logContainer.firstChild!);
        }

        this.updateLineCount();
        this.scrollToBottom();
    }

    private createLineElement(line: string): HTMLDivElement {
        const lineEl = document.createElement('div');
        lineEl.className = 'log-line';

        // Apply styling based on log level
        if (line.includes('ERROR') || line.includes('[ERROR]')) {
            lineEl.classList.add('log-error');
        } else if (line.includes('WARNING') || line.includes('[WARNING]')) {
            lineEl.classList.add('log-warning');
        } else if (line.includes('DEBUG') || line.includes('[DEBUG]')) {
            lineEl.classList.add('log-debug');
        }

        lineEl.textContent = line;
        return lineEl;
    }

    private clearLogs(): void {
        this.lines = [];
        if (this.logContainer) {
            this.logContainer.innerHTML = '';
        }
        this.updateLineCount();
    }

    private scrollToBottom(): void {
        if (this.autoScroll && this.logContainer) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }

    private updateLineCount(): void {
        const countEl = document.getElementById('line-count');
        if (countEl) {
            countEl.textContent = `${this.lines.length} lines`;
        }
    }

    private updateConnectionStatus(status: 'connecting' | 'connected' | 'disconnected' | 'error'): void {
        const statusEl = document.getElementById('connection-status');
        const reconnectBtn = document.getElementById('reconnect') as HTMLButtonElement;

        if (statusEl) {
            statusEl.className = `status-indicator status-${status}`;
            statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }

        if (reconnectBtn) {
            reconnectBtn.disabled = status === 'connecting' || status === 'connected';
        }
    }

    public disconnect(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('log-viewer-container');
    if (container) {
        new LogViewer('log-viewer-container');
    }
});

export { LogViewer, LogMessage };
