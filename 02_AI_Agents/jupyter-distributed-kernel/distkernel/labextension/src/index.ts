/**
 * JupyterLab extension for Distributed Kernel — adds a sidebar panel
 * showing connected workers, their status, and session controls.
 */
import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  ILayoutRestorer,
} from '@jupyterlab/application';

import { ICommandPalette, MainAreaWidget } from '@jupyterlab/apputils';

import { Widget } from '@lumino/widgets';

const PLUGIN_ID = 'jupyter-distributed-kernel:panel';
const COMMAND_OPEN = 'distkernel:open-panel';

/**
 * Worker status panel widget — connects to the gateway WebSocket
 * and displays real-time worker status, session info, and controls.
 */
class DistKernelPanel extends Widget {
  private _ws: WebSocket | null = null;
  private _gatewayUrl: string;
  private _workers: any[] = [];
  private _reconnectTimer: number | null = null;

  constructor(gatewayUrl: string = 'ws://localhost:8555') {
    super();
    this._gatewayUrl = gatewayUrl;
    this.id = 'distkernel-panel';
    this.title.label = 'Distributed Workers';
    this.title.closable = true;
    this.addClass('dk-panel');

    this._render();
    this._connect();
  }

  dispose(): void {
    if (this._ws) {
      this._ws.close();
    }
    if (this._reconnectTimer) {
      window.clearTimeout(this._reconnectTimer);
    }
    super.dispose();
  }

  private _connect(): void {
    try {
      this._ws = new WebSocket(this._gatewayUrl);

      this._ws.onopen = () => {
        console.log('[DistKernel] Connected to gateway');
        // Request worker list
        this._ws?.send(JSON.stringify({
          type: 'worker.list.request',
          ts: Date.now() / 1000,
          id: this._uid(),
        }));
        this._render();
      };

      this._ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data);
          this._handleMessage(msg);
        } catch (e) {
          console.warn('[DistKernel] Invalid message', e);
        }
      };

      this._ws.onclose = () => {
        console.log('[DistKernel] Disconnected from gateway');
        this._ws = null;
        this._render();
        // Reconnect after delay
        this._reconnectTimer = window.setTimeout(() => this._connect(), 5000);
      };

      this._ws.onerror = (err) => {
        console.warn('[DistKernel] WebSocket error', err);
      };
    } catch (e) {
      console.error('[DistKernel] Connection failed', e);
      this._reconnectTimer = window.setTimeout(() => this._connect(), 5000);
    }
  }

  private _handleMessage(msg: any): void {
    if (msg.type === 'worker.list') {
      this._workers = msg.workers || [];
      this._render();
    } else if (msg.type === 'worker.status') {
      // Single worker update
      this._render();
    }
  }

  private _render(): void {
    const connected = this._ws?.readyState === WebSocket.OPEN;
    const workerCount = this._workers.length;
    const busyCount = this._workers.filter((w: any) => w.status === 'busy').length;
    const totalCpu = this._workers.reduce((s: number, w: any) =>
      s + (w.capabilities?.cpu_count || 0), 0);
    const totalMem = this._workers.reduce((s: number, w: any) =>
      s + (w.capabilities?.memory_mb || 0), 0);

    this.node.innerHTML = `
      <div class="dk-container">
        <div class="dk-header">
          <h2>🖥 Distributed Kernel</h2>
          <div class="dk-status ${connected ? 'dk-connected' : 'dk-disconnected'}">
            ${connected ? '● Connected' : '○ Disconnected'}
          </div>
        </div>

        <div class="dk-summary">
          <div class="dk-stat">
            <span class="dk-stat-value">${workerCount}</span>
            <span class="dk-stat-label">Workers</span>
          </div>
          <div class="dk-stat">
            <span class="dk-stat-value">${busyCount}</span>
            <span class="dk-stat-label">Busy</span>
          </div>
          <div class="dk-stat">
            <span class="dk-stat-value">${totalCpu}</span>
            <span class="dk-stat-label">Total CPUs</span>
          </div>
          <div class="dk-stat">
            <span class="dk-stat-value">${this._formatMem(totalMem)}</span>
            <span class="dk-stat-label">Total RAM</span>
          </div>
        </div>

        <div class="dk-section">
          <h3>Connected Workers</h3>
          ${workerCount === 0 ? `
            <div class="dk-empty">
              <p>No workers connected.</p>
              <p class="dk-hint">Start a worker with:</p>
              <code>distkernel-worker --gateway ${this._gatewayUrl}</code>
            </div>
          ` : `
            <div class="dk-worker-list">
              ${this._workers.map((w: any) => this._renderWorker(w)).join('')}
            </div>
          `}
        </div>

        <div class="dk-section">
          <h3>Gateway</h3>
          <div class="dk-gateway-info">
            <span class="dk-label">URL:</span>
            <code>${this._gatewayUrl}</code>
          </div>
        </div>

        ${!connected ? `
          <div class="dk-section">
            <h3>Setup Instructions</h3>
            <ol class="dk-instructions">
              <li>Start the gateway:
                <code>distkernel-gateway --port 8555</code>
              </li>
              <li>Connect workers from participant devices:
                <code>distkernel-worker --gateway ws://HOST:8555</code>
              </li>
              <li>Select <strong>"Distributed Kernel"</strong> when creating a notebook</li>
            </ol>
          </div>
        ` : ''}
      </div>

      <style>
        .dk-container {
          padding: 12px;
          font-family: var(--jp-ui-font-family);
          font-size: var(--jp-ui-font-size1);
          color: var(--jp-ui-font-color0);
          overflow-y: auto;
          height: 100%;
        }
        .dk-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--jp-border-color1);
        }
        .dk-header h2 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
        }
        .dk-status {
          font-size: 12px;
          padding: 2px 8px;
          border-radius: 10px;
        }
        .dk-connected {
          background: var(--jp-success-color2, #d4edda);
          color: var(--jp-success-color0, #155724);
        }
        .dk-disconnected {
          background: var(--jp-error-color2, #f8d7da);
          color: var(--jp-error-color0, #721c24);
        }
        .dk-summary {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
          margin-bottom: 16px;
        }
        .dk-stat {
          text-align: center;
          padding: 8px;
          background: var(--jp-layout-color1);
          border-radius: 6px;
          border: 1px solid var(--jp-border-color2);
        }
        .dk-stat-value {
          display: block;
          font-size: 20px;
          font-weight: 700;
          color: var(--jp-brand-color1);
        }
        .dk-stat-label {
          display: block;
          font-size: 10px;
          color: var(--jp-ui-font-color2);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .dk-section {
          margin-bottom: 16px;
        }
        .dk-section h3 {
          font-size: 13px;
          font-weight: 600;
          margin: 0 0 8px 0;
          color: var(--jp-ui-font-color1);
        }
        .dk-worker-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .dk-worker {
          padding: 8px 10px;
          background: var(--jp-layout-color1);
          border: 1px solid var(--jp-border-color2);
          border-radius: 6px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .dk-worker-name {
          font-weight: 600;
          font-size: 13px;
        }
        .dk-worker-meta {
          font-size: 11px;
          color: var(--jp-ui-font-color2);
        }
        .dk-worker-status {
          font-size: 11px;
          padding: 1px 6px;
          border-radius: 8px;
        }
        .dk-worker-idle { background: #e8f5e9; color: #2e7d32; }
        .dk-worker-busy { background: #fff3e0; color: #e65100; }
        .dk-worker-offline { background: #fbe9e7; color: #bf360c; }
        .dk-empty {
          padding: 16px;
          text-align: center;
          background: var(--jp-layout-color1);
          border-radius: 6px;
          border: 1px dashed var(--jp-border-color2);
        }
        .dk-empty p { margin: 4px 0; }
        .dk-hint { color: var(--jp-ui-font-color2); font-size: 12px; }
        .dk-empty code, .dk-gateway-info code, .dk-instructions code {
          background: var(--jp-layout-color2);
          padding: 2px 6px;
          border-radius: 3px;
          font-size: 11px;
          word-break: break-all;
        }
        .dk-gateway-info {
          font-size: 12px;
        }
        .dk-label {
          color: var(--jp-ui-font-color2);
          margin-right: 4px;
        }
        .dk-instructions {
          padding-left: 20px;
          font-size: 12px;
        }
        .dk-instructions li {
          margin-bottom: 8px;
        }
        .dk-instructions code {
          display: block;
          margin-top: 4px;
        }
      </style>
    `;
  }

  private _renderWorker(w: any): string {
    const caps = w.capabilities || {};
    const statusClass = w.status === 'busy' ? 'dk-worker-busy' :
                        w.status === 'offline' ? 'dk-worker-offline' : 'dk-worker-idle';
    return `
      <div class="dk-worker">
        <div>
          <div class="dk-worker-name">${this._esc(w.name || w.worker_id)}</div>
          <div class="dk-worker-meta">
            ${caps.platform || '?'} · ${caps.cpu_count || '?'} CPU ·
            ${this._formatMem(caps.memory_mb || 0)} RAM
            ${caps.gpu ? ' · GPU' : ''}
            ${w.total_executed ? ` · ${w.total_executed} cells run` : ''}
          </div>
        </div>
        <div>
          <span class="dk-worker-status ${statusClass}">
            ${w.status || 'unknown'}
            ${w.running_cells > 0 ? ` (${w.running_cells})` : ''}
          </span>
        </div>
      </div>
    `;
  }

  private _formatMem(mb: number): string {
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)}GB`;
    return `${mb}MB`;
  }

  private _esc(s: string): string {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  private _uid(): string {
    return Math.random().toString(36).substring(2, 10);
  }
}


/**
 * JupyterLab plugin activation
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [],
  optional: [ICommandPalette, ILayoutRestorer],
  activate: (
    app: JupyterFrontEnd,
    palette: ICommandPalette | null,
    restorer: ILayoutRestorer | null,
  ) => {
    console.log('[DistKernel] Extension activated');

    let widget: MainAreaWidget<DistKernelPanel> | null = null;

    app.commands.addCommand(COMMAND_OPEN, {
      label: 'Distributed Workers Panel',
      caption: 'Show connected distributed compute workers',
      execute: () => {
        if (!widget || widget.isDisposed) {
          const gatewayUrl = (window as any).__DISTKERNEL_GATEWAY_URL__ || 'ws://localhost:8555';
          const panel = new DistKernelPanel(gatewayUrl);
          widget = new MainAreaWidget({ content: panel });
          widget.id = 'distkernel-main-widget';
          widget.title.label = 'Distributed Workers';
          widget.title.closable = true;
        }
        if (!widget.isAttached) {
          app.shell.add(widget, 'right');
        }
        app.shell.activateById(widget.id);
      },
    });

    if (palette) {
      palette.addItem({
        command: COMMAND_OPEN,
        category: 'Distributed Kernel',
      });
    }

    // Auto-open on startup
    app.restored.then(() => {
      app.commands.execute(COMMAND_OPEN);
    });
  },
};

export default plugin;
