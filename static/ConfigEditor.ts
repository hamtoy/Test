/**
 * Configuration Editor - UI for editing application settings
 */

interface ConfigData {
    llm_model: string;
    temperature: number;
    max_tokens: number;
    log_level: string;
    output_dir: string;
    enable_cache: boolean;
    cache_ttl: number;
}

class ConfigEditor {
    private container: HTMLElement;
    private formData: Partial<ConfigData> = {};
    private isLoading = false;

    constructor(containerId: string) {
        const element = document.getElementById(containerId);
        if (!element) {
            throw new Error(`Container element not found: ${containerId}`);
        }
        this.container = element;
        this.init();
    }

    private async init(): Promise<void> {
        this.render();
        await this.loadConfig();
    }

    private render(): void {
        this.container.innerHTML = `
      <div class="config-editor">
        <h2>Configuration Settings</h2>
        <form id="config-form" class="config-form">
          <div class="form-group">
            <label for="llm_model">LLM Model</label>
            <input type="text" id="llm_model" name="llm_model" placeholder="gemini-1.5-flash">
          </div>
          
          <div class="form-group">
            <label for="temperature">Temperature (0.0 - 2.0)</label>
            <input type="number" id="temperature" name="temperature" min="0" max="2" step="0.1" value="0.7">
          </div>
          
          <div class="form-group">
            <label for="max_tokens">Max Tokens</label>
            <input type="number" id="max_tokens" name="max_tokens" min="1" value="4096">
          </div>
          
          <div class="form-group">
            <label for="log_level">Log Level</label>
            <select id="log_level" name="log_level">
              <option value="DEBUG">DEBUG</option>
              <option value="INFO" selected>INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="output_dir">Output Directory</label>
            <input type="text" id="output_dir" name="output_dir" value="output">
          </div>
          
          <div class="form-group">
            <label for="enable_cache">
              <input type="checkbox" id="enable_cache" name="enable_cache" checked>
              Enable Cache
            </label>
          </div>
          
          <div class="form-group">
            <label for="cache_ttl">Cache TTL (seconds)</label>
            <input type="number" id="cache_ttl" name="cache_ttl" min="0" value="3600">
          </div>
          
          <div class="form-actions">
            <button type="submit" class="btn-primary" id="save-btn">Save Configuration</button>
            <button type="button" class="btn-secondary" id="reload-btn">Reload</button>
          </div>
          
          <div id="status-message" class="status-message"></div>
        </form>
      </div>
    `;

        this.attachEventListeners();
    }

    private attachEventListeners(): void {
        const form = document.getElementById('config-form');
        const reloadBtn = document.getElementById('reload-btn');

        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveConfig();
        });

        reloadBtn?.addEventListener('click', async () => {
            await this.loadConfig();
        });
    }

    private async loadConfig(): Promise<void> {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showStatus('Loading configuration...', 'info');

        try {
            const response = await fetch('/api/config');
            if (!response.ok) {
                throw new Error(`Failed to load config: ${response.statusText}`);
            }

            const data: ConfigData = await response.json();
            this.formData = data;
            this.populateForm(data);
            this.showStatus('Configuration loaded successfully', 'success');
        } catch (error) {
            console.error('Failed to load config:', error);
            this.showStatus(`Error: ${error}`, 'error');
        } finally {
            this.isLoading = false;
        }
    }

    private populateForm(data: ConfigData): void {
        const setValue = (id: string, value: unknown) => {
            const el = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
            if (!el) return;

            if (el.type === 'checkbox') {
                (el as HTMLInputElement).checked = Boolean(value);
            } else {
                el.value = String(value);
            }
        };

        setValue('llm_model', data.llm_model);
        setValue('temperature', data.temperature);
        setValue('max_tokens', data.max_tokens);
        setValue('log_level', data.log_level);
        setValue('output_dir', data.output_dir);
        setValue('enable_cache', data.enable_cache);
        setValue('cache_ttl', data.cache_ttl);
    }

    private getFormData(): Partial<ConfigData> {
        const getValue = (id: string): string | number | boolean | undefined => {
            const el = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
            if (!el) return undefined;

            if (el.type === 'checkbox') {
                return (el as HTMLInputElement).checked;
            }
            if (el.type === 'number') {
                return parseFloat(el.value);
            }
            return el.value;
        };

        return {
            llm_model: getValue('llm_model') as string,
            temperature: getValue('temperature') as number,
            max_tokens: getValue('max_tokens') as number,
            log_level: getValue('log_level') as string,
            output_dir: getValue('output_dir') as string,
            enable_cache: getValue('enable_cache') as boolean,
            cache_ttl: getValue('cache_ttl') as number,
        };
    }

    private async saveConfig(): Promise<void> {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showStatus('Saving configuration...', 'info');

        try {
            const data = this.getFormData();
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to save config');
            }

            const updatedData: ConfigData = await response.json();
            this.formData = updatedData;
            this.populateForm(updatedData);
            this.showStatus('Configuration saved successfully!', 'success');
        } catch (error) {
            console.error('Failed to save config:', error);
            this.showStatus(`Error: ${error}`, 'error');
        } finally {
            this.isLoading = false;
        }
    }

    private showStatus(message: string, type: 'info' | 'success' | 'error'): void {
        const statusEl = document.getElementById('status-message');
        if (!statusEl) return;

        statusEl.textContent = message;
        statusEl.className = `status-message status-${type}`;

        if (type !== 'info') {
            setTimeout(() => {
                statusEl.textContent = '';
                statusEl.className = 'status-message';
            }, 3000);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('config-editor-container');
    if (container) {
        new ConfigEditor('config-editor-container');
    }
});

export { ConfigEditor, ConfigData };
