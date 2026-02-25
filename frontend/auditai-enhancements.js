/**
 * AuditAI Suite — Integration Enhancement Layer v1.0
 * ─────────────────────────────────────────────────────
 * Drop-in enhancement. Add ONE line to app.html just before </body>:
 *   <script src="auditai-enhancements.js"></script>
 *
 * What this adds (without touching any existing code):
 *   1.  DEMO / LIVE mode banner (sticky top)
 *   2.  Pre-run data validation gate (schema · nulls · hash · duplicates)
 *   3.  Evidence drill-down on every finding row (source rows + detection logic)
 *   4.  ✅ / ❌ verdict buttons per finding + local precision tracking
 *   5.  "AI Precision Score" KPI tile injected into the existing KPI bar
 *   6.  Cross-agent corroboration badges on findings confirmed by 2+ agents
 *
 * Persistence: IndexedDB (AuditAI_DB) stores verdicts across sessions.
 * No server required. Works 100% client-side on GitHub Pages.
 */

(function () {
  'use strict';

  // ─────────────────────────────────────────────────────────────────────────
  // 0.  GLOBAL STATE
  // ─────────────────────────────────────────────────────────────────────────
  const AuditState = {
    mode: 'DEMO',          // 'DEMO' | 'LIVE'
    source: null,          // e.g. 'CSV Upload — access_data.csv'
    fileHash: null,
    rowCount: null,
    agentType: null,
    validationResult: null,
    findings: [],           // populated by interceptor
    agentRunCounts: {},     // track how many agents have flagged each entity
    sessionStartTime: Date.now()
  };

  // ─────────────────────────────────────────────────────────────────────────
  // 1.  INDEXEDDB — verdict persistence
  // ─────────────────────────────────────────────────────────────────────────
  let db = null;

  function initDB() {
    return new Promise((resolve) => {
      const req = indexedDB.open('AuditAI_DB', 2);
      req.onupgradeneeded = (e) => {
        const d = e.target.result;
        if (!d.objectStoreNames.contains('verdicts')) {
          const store = d.createObjectStore('verdicts', { keyPath: 'finding_id' });
          store.createIndex('verdict', 'verdict', { unique: false });
        }
        if (!d.objectStoreNames.contains('sessions')) {
          d.createObjectStore('sessions', { keyPath: 'id', autoIncrement: true });
        }
      };
      req.onsuccess = (e) => { db = e.target.result; resolve(db); };
      req.onerror = () => resolve(null);
    });
  }

  function dbSet(storeName, record) {
    if (!db) return Promise.resolve();
    return new Promise((resolve) => {
      const tx = db.transaction(storeName, 'readwrite');
      tx.objectStore(storeName).put(record);
      tx.oncomplete = resolve;
      tx.onerror = resolve;
    });
  }

  function dbGetAll(storeName) {
    if (!db) return Promise.resolve([]);
    return new Promise((resolve) => {
      const tx = db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => resolve([]);
    });
  }

  function dbGet(storeName, key) {
    if (!db) return Promise.resolve(null);
    return new Promise((resolve) => {
      const tx = db.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => resolve(null);
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 2.  SHA-256 HASH (WebCrypto)
  // ─────────────────────────────────────────────────────────────────────────
  async function sha256(text) {
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
      return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
    } catch {
      // fallback: simple hash
      let h = 0;
      for (let i = 0; i < text.length; i++) { h = (Math.imul(31, h) + text.charCodeAt(i)) | 0; }
      return Math.abs(h).toString(16).padStart(8, '0') + '0000000000000000000000000000000000000000000000000000000';
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 3.  STYLES (injected once)
  // ─────────────────────────────────────────────────────────────────────────
  function injectStyles() {
    const style = document.createElement('style');
    style.id = 'auditai-enhancements-css';
    style.textContent = `
      /* ── MODE BANNER ── */
      #aai-mode-banner {
        position: sticky; top: 0; z-index: 10000;
        padding: 6px 20px;
        font-family: 'IBM Plex Mono', 'Courier New', monospace;
        font-size: 11px; font-weight: 600; letter-spacing: 0.07em;
        display: flex; align-items: center; gap: 12px;
        transition: all 0.4s ease;
        width: 100%;
      }
      #aai-mode-banner.demo {
        background: linear-gradient(90deg, rgba(255,149,0,0.18) 0%, rgba(255,149,0,0.04) 100%);
        border-bottom: 1px solid rgba(255,149,0,0.35);
        color: #ff9500;
      }
      #aai-mode-banner.live {
        background: linear-gradient(90deg, rgba(0,230,118,0.14) 0%, rgba(0,230,118,0.02) 100%);
        border-bottom: 1px solid rgba(0,230,118,0.3);
        color: #00e676;
      }
      #aai-mode-banner .aai-dot {
        width: 7px; height: 7px; border-radius: 50%;
        background: currentColor; flex-shrink: 0;
        animation: aai-pulse 2s ease-in-out infinite;
      }
      #aai-mode-banner .aai-detail { color: rgba(200,212,232,0.55); font-weight: 400; margin-left: 4px; }
      #aai-mode-banner .aai-hash { 
        color: rgba(200,212,232,0.35); font-weight: 300; 
        font-size: 10px; letter-spacing: 0.04em;
      }
      #aai-mode-banner .aai-right { margin-left: auto; font-size: 10px; color: rgba(200,212,232,0.3); }
      @keyframes aai-pulse {
        0%,100% { opacity:1; transform:scale(1); }
        50% { opacity:0.35; transform:scale(0.75); }
      }

      /* ── VALIDATION GATE ── */
      #aai-validation-gate {
        display: none;
        margin: 14px 0;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #1e2535;
        animation: aai-slideIn 0.25s ease;
      }
      #aai-validation-gate.visible { display: block; }
      @keyframes aai-slideIn {
        from { opacity:0; transform:translateY(-8px); }
        to { opacity:1; transform:translateY(0); }
      }
      .aai-val-header {
        padding: 11px 16px;
        display: flex; align-items: center; gap: 10px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }
      .aai-val-header.pass { background: rgba(0,230,118,0.09); }
      .aai-val-header.fail { background: rgba(255,61,61,0.09); }
      .aai-val-header.warn { background: rgba(255,149,0,0.09); }
      .aai-val-title { font-size: 12px; font-weight: 700; }
      .aai-val-header.pass .aai-val-title { color: #00e676; }
      .aai-val-header.fail .aai-val-title { color: #ff4d4d; }
      .aai-val-header.warn .aai-val-title { color: #ff9500; }
      .aai-val-body { padding: 14px 16px; background: rgba(15,18,24,0.8); }
      .aai-val-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 8px; margin-bottom: 12px;
      }
      .aai-val-metric {
        background: rgba(26,32,48,0.9);
        border: 1px solid #1e2535;
        border-radius: 6px; padding: 9px 11px;
      }
      .aai-val-metric-lbl {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 9px; color: #4a5568;
        text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 3px;
      }
      .aai-val-metric-val {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 13px; font-weight: 600; color: #c8d4e8;
      }
      .aai-val-metric-val.ok { color: #00e676; }
      .aai-val-metric-val.warn { color: #ff9500; }
      .aai-val-metric-val.err { color: #ff4d4d; }
      .aai-val-hash {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 10px; color: #4a5568;
        background: rgba(10,12,16,0.6);
        border: 1px solid #1a2030;
        border-radius: 4px; padding: 7px 10px;
        margin-bottom: 12px; word-break: break-all;
        letter-spacing: 0.03em;
      }
      .aai-val-hash .aai-hash-label { color: #7a8aaa; margin-right: 6px; }
      .aai-null-table { width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 12px; }
      .aai-null-table th {
        text-align: left; padding: 5px 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em;
        color: #4a5568; border-bottom: 1px solid #1e2535;
      }
      .aai-null-table td { padding: 5px 8px; border-bottom: 1px solid rgba(30,37,53,0.5); color: #7a8aaa; }
      .aai-null-table td.ok { color: #00b85a; }
      .aai-null-table td.warn { color: #ff9500; }
      .aai-null-table td.err { color: #ff4d4d; }
      .aai-null-bar {
        height: 3px; border-radius: 2px;
        background: #1a2030; overflow: hidden; display: inline-block;
        width: 60px; vertical-align: middle; margin-right: 6px;
      }
      .aai-null-bar-fill { height: 100%; border-radius: 2px; transition: width 0.4s ease; }
      .aai-val-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
      .aai-btn {
        padding: 8px 16px; border-radius: 5px;
        font-size: 12px; font-weight: 600; cursor: pointer;
        border: 1px solid; transition: all 0.15s;
        font-family: inherit;
        letter-spacing: 0.02em;
      }
      .aai-btn-confirm {
        background: rgba(0,230,118,0.12);
        border-color: rgba(0,230,118,0.35);
        color: #00e676;
      }
      .aai-btn-confirm:hover { background: rgba(0,230,118,0.2); }
      .aai-btn-cancel {
        background: transparent;
        border-color: #1e2535;
        color: #7a8aaa;
      }
      .aai-btn-cancel:hover { background: rgba(255,255,255,0.04); color: #c8d4e8; }
      .aai-val-missing {
        background: rgba(255,77,77,0.08);
        border: 1px solid rgba(255,77,77,0.25);
        border-radius: 5px; padding: 8px 12px;
        font-size: 11px; color: #ff7777; margin-bottom: 10px;
      }

      /* ── PRECISION KPI TILE ── */
      #aai-precision-kpi {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; gap: 3px;
        padding: 12px 18px;
        background: rgba(168,85,247,0.06);
        border: 1px solid rgba(168,85,247,0.2);
        border-radius: 8px; cursor: pointer;
        transition: all 0.2s; position: relative;
        min-width: 110px;
      }
      #aai-precision-kpi:hover { background: rgba(168,85,247,0.1); }
      .aai-kpi-icon { font-size: 14px; }
      .aai-kpi-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 18px; font-weight: 700; color: #a855f7;
        line-height: 1;
      }
      .aai-kpi-value.insufficient { font-size: 11px; color: #4a5568; }
      .aai-kpi-label { font-size: 10px; color: #7a8aaa; text-align: center; line-height: 1.2; }
      .aai-kpi-sub { font-size: 9px; color: #4a5568; font-family: 'IBM Plex Mono', monospace; }

      /* ── VERDICT BUTTONS ── */
      .aai-verdict-cell { white-space: nowrap; }
      .aai-verdict-btn {
        padding: 3px 8px; border-radius: 4px;
        font-size: 11px; cursor: pointer; border: 1px solid;
        transition: all 0.15s; background: transparent;
        margin-right: 3px; font-family: inherit;
      }
      .aai-verdict-btn.tp {
        border-color: rgba(0,230,118,0.3); color: #00b85a;
      }
      .aai-verdict-btn.tp:hover, .aai-verdict-btn.tp.active {
        background: rgba(0,230,118,0.12); border-color: rgba(0,230,118,0.5); color: #00e676;
      }
      .aai-verdict-btn.fp {
        border-color: rgba(255,77,77,0.3); color: #cc4444;
      }
      .aai-verdict-btn.fp:hover, .aai-verdict-btn.fp.active {
        background: rgba(255,77,77,0.1); border-color: rgba(255,77,77,0.5); color: #ff4d4d;
      }
      .aai-verdict-badge {
        display: inline-block; font-size: 10px;
        font-family: 'IBM Plex Mono', monospace;
        padding: 2px 6px; border-radius: 3px;
        font-weight: 600; margin-left: 3px;
      }
      .aai-verdict-badge.tp { background: rgba(0,230,118,0.12); color: #00e676; }
      .aai-verdict-badge.fp { background: rgba(255,77,77,0.1); color: #ff4d4d; }
      .aai-verdict-badge.nr { background: rgba(255,149,0,0.1); color: #ff9500; }

      /* ── EVIDENCE PANEL ── */
      .aai-evidence-row { display: none; }
      .aai-evidence-row.open { display: table-row; }
      .aai-evidence-cell {
        padding: 0 !important;
        border-bottom: 2px solid rgba(0,212,255,0.15) !important;
      }
      .aai-evidence-inner {
        padding: 16px 20px;
        background: rgba(10,12,16,0.7);
        border-top: 1px solid rgba(0,212,255,0.1);
      }
      .aai-evidence-header {
        display: flex; align-items: center; gap: 12px;
        margin-bottom: 12px; flex-wrap: wrap;
      }
      .aai-evidence-title { font-size: 12px; font-weight: 700; color: #c8d4e8; }
      .aai-evidence-meta { font-size: 10px; color: #4a5568; font-family: 'IBM Plex Mono', monospace; }
      .aai-evidence-rule {
        font-size: 10px; font-family: 'IBM Plex Mono', monospace;
        background: rgba(0,212,255,0.06);
        border: 1px solid rgba(0,212,255,0.15);
        border-radius: 4px; padding: 2px 7px; color: #00aad4;
      }
      .aai-source-table { width: 100%; border-collapse: collapse; font-size: 11px; }
      .aai-source-table th {
        text-align: left; padding: 5px 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em;
        color: #4a5568; border-bottom: 1px solid #1e2535;
        background: rgba(20,24,32,0.6);
      }
      .aai-source-table td {
        padding: 5px 8px; border-bottom: 1px solid rgba(30,37,53,0.4);
        color: #7a8aaa; max-width: 200px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .aai-source-table td.highlight { color: #00d4ff; font-weight: 500; }
      .aai-source-table tr:hover td { background: rgba(255,255,255,0.02); }
      .aai-evidence-hash {
        font-family: 'IBM Plex Mono', monospace; font-size: 9px;
        color: #2a3545; margin-top: 8px; padding-top: 8px;
        border-top: 1px solid #1a2030;
      }

      /* ── CORROBORATION BADGE ── */
      .aai-corr-badge {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 10px; font-family: 'IBM Plex Mono', monospace;
        padding: 2px 6px; border-radius: 3px; margin-left: 4px;
        font-weight: 600; vertical-align: middle;
      }
      .aai-corr-badge.single {
        background: rgba(122,138,170,0.08);
        border: 1px solid rgba(122,138,170,0.2);
        color: #7a8aaa;
      }
      .aai-corr-badge.corroborated {
        background: rgba(0,230,118,0.1);
        border: 1px solid rgba(0,230,118,0.3);
        color: #00e676;
        animation: aai-glow 2s ease-in-out infinite;
      }
      @keyframes aai-glow {
        0%,100% { box-shadow: 0 0 4px rgba(0,230,118,0.2); }
        50% { box-shadow: 0 0 10px rgba(0,230,118,0.4); }
      }

      /* ── PRECISION TOOLTIP ── */
      .aai-precision-tooltip {
        display: none;
        position: absolute; top: calc(100% + 8px); right: 0;
        background: #0f1218;
        border: 1px solid #1e2535;
        border-radius: 8px; padding: 12px 14px;
        width: 220px; z-index: 9999;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      }
      #aai-precision-kpi:hover .aai-precision-tooltip { display: block; }
      .aai-pt-row { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px; }
      .aai-pt-row:last-child { margin: 0; }
      .aai-pt-label { color: #7a8aaa; }
      .aai-pt-val { font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
      .aai-pt-tp { color: #00e676; }
      .aai-pt-fp { color: #ff4d4d; }
      .aai-pt-total { color: #c8d4e8; }
      .aai-pt-divider { border: none; border-top: 1px solid #1e2535; margin: 8px 0; }
      .aai-pt-title { font-size: 10px; font-weight: 700; color: #c8d4e8; margin-bottom: 8px; letter-spacing: 0.05em; text-transform: uppercase; font-family: 'IBM Plex Mono', monospace; }
      .aai-pt-note { font-size: 10px; color: #4a5568; margin-top: 8px; line-height: 1.4; }

      /* ── FINDING ROW CLICKABLE ── */
      .aai-finding-row-clickable { cursor: pointer; }
      .aai-finding-row-clickable:hover td { background: rgba(0,212,255,0.03) !important; }
      .aai-expand-icon { font-size: 10px; color: #4a5568; margin-right: 4px; transition: transform 0.2s; }
      .aai-finding-row-clickable.expanded .aai-expand-icon { transform: rotate(90deg); color: #00d4ff; }

      /* ── ROW INSERTION INDICATOR ── */
      .aai-inserting td { animation: aai-rowInsert 0.3s ease; }
      @keyframes aai-rowInsert {
        from { background: rgba(0,212,255,0.08); }
        to { background: transparent; }
      }
    `;
    document.head.appendChild(style);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 4.  MODE BANNER
  // ─────────────────────────────────────────────────────────────────────────
  function injectModeBanner() {
    const banner = document.createElement('div');
    banner.id = 'aai-mode-banner';
    banner.className = 'demo';
    banner.innerHTML = `
      <span class="aai-dot"></span>
      <span>⚠ DEMO MODE</span>
      <span class="aai-detail">Client-side rules engine · no backend connection · results are illustrative</span>
      <span class="aai-right">AuditAI Suite v4.0</span>
    `;
    document.body.insertBefore(banner, document.body.firstChild);
  }

  function setLiveMode(source, hash, rowCount, agent) {
    AuditState.mode = 'LIVE';
    AuditState.source = source;
    AuditState.fileHash = hash;
    AuditState.rowCount = rowCount;
    AuditState.agentType = agent;
    const banner = document.getElementById('aai-mode-banner');
    if (!banner) return;
    banner.className = 'live';
    banner.innerHTML = `
      <span class="aai-dot"></span>
      <span>🟢 LIVE ANALYSIS</span>
      <span class="aai-detail">Source: ${escapeHtml(source)} · ${rowCount.toLocaleString()} records · Agent: ${escapeHtml(agent || 'Unknown')}</span>
      <span class="aai-hash">SHA-256: ${hash ? hash.slice(0, 16) + '…' : '—'}</span>
      <span class="aai-right">AuditAI Suite v4.0</span>
    `;
  }

  function resetToDemo() {
    AuditState.mode = 'DEMO';
    const banner = document.getElementById('aai-mode-banner');
    if (!banner) return;
    banner.className = 'demo';
    banner.innerHTML = `
      <span class="aai-dot"></span>
      <span>⚠ DEMO MODE</span>
      <span class="aai-detail">Client-side rules engine · no backend connection · results are illustrative</span>
      <span class="aai-right">AuditAI Suite v4.0</span>
    `;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 5.  VALIDATION GATE
  // ─────────────────────────────────────────────────────────────────────────

  // Column requirements per agent type
  const REQUIRED_COLUMNS = {
    sod: ['user_id', 'role_id'],
    'segregation of duties': ['user_id', 'role_id'],
    access: ['user_id', 'status'],
    'logical access': ['user_id', 'status'],
    change: ['change_id', 'requestor_id'],
    'change management': ['change_id', 'requestor_id'],
    journal: ['je_id', 'amount', 'posted_by'],
    'financial reporting': ['je_id', 'amount', 'posted_by'],
    'journal entry': ['je_id', 'amount'],
    transaction: ['transaction_id', 'amount'],
    vendor: ['vendor_id', 'vendor_name'],
    'master data': ['vendor_id', 'vendor_name'],
    sdlc: ['change_id', 'requestor_id'],
    'program development': ['change_id', 'requestor_id'],
    config: ['config_key', 'current_value'],
    interface: ['interface_id', 'source_system'],
    operations: ['job_id', 'status'],
  };

  function getRequiredColumns(agentType) {
    if (!agentType) return [];
    const key = agentType.toLowerCase();
    for (const [k, v] of Object.entries(REQUIRED_COLUMNS)) {
      if (key.includes(k)) return v;
    }
    return [];
  }

  async function validateData(data, fileName, agentType) {
    if (!data || data.length === 0) {
      return { passed: false, reason: 'No data rows found', rowCount: 0 };
    }

    const hash = await sha256(JSON.stringify(data));
    const required = getRequiredColumns(agentType);
    const cols = data.length > 0 ? Object.keys(data[0]) : [];

    const missingCols = required.filter(c =>
      !cols.some(col => col.toLowerCase().replace(/[\s_-]/g, '') === c.toLowerCase().replace(/[\s_-]/g, ''))
    );

    const nullReport = {};
    cols.forEach(col => {
      const nullCount = data.filter(r => r[col] === null || r[col] === undefined || r[col] === '').length;
      nullReport[col] = { count: nullCount, pct: data.length > 0 ? (nullCount / data.length * 100) : 0 };
    });

    const highNullCols = Object.entries(nullReport).filter(([, v]) => v.pct > 10);
    const dupCount = data.length - new Set(data.map(r => JSON.stringify(r))).size;

    // Date range
    let minDate = null, maxDate = null;
    const dateCols = cols.filter(c => c.toLowerCase().includes('date') || c.toLowerCase().includes('timestamp'));
    if (dateCols.length > 0) {
      const dates = data.map(r => r[dateCols[0]]).filter(Boolean).map(d => new Date(d)).filter(d => !isNaN(d));
      if (dates.length > 0) {
        minDate = new Date(Math.min(...dates)).toLocaleDateString();
        maxDate = new Date(Math.max(...dates)).toLocaleDateString();
      }
    }

    const passed = missingCols.length === 0 && highNullCols.filter(([, v]) => v.pct > 50).length === 0;

    return {
      passed,
      rowCount: data.length,
      colCount: cols.length,
      hash,
      fileName,
      missingCols,
      nullReport,
      highNullCols,
      dupCount,
      minDate,
      maxDate,
      cols,
      required
    };
  }

  function renderValidationGate(result, onConfirm, onCancel) {
    let gate = document.getElementById('aai-validation-gate');
    if (!gate) {
      gate = document.createElement('div');
      gate.id = 'aai-validation-gate';
      // Try to insert after the upload area, before the column mapping / run button
      const uploadSection = document.querySelector('[id*="upload"], [class*="upload-section"], [id*="step2"], [data-step="2"]');
      if (uploadSection) {
        uploadSection.parentNode.insertBefore(gate, uploadSection.nextSibling);
      } else {
        // Fallback: insert before the first "Run Audit" button we can find
        const runBtn = document.querySelector('button[onclick*="run"], button[onclick*="Run"], [id*="run-btn"], [class*="run-btn"]');
        if (runBtn) {
          runBtn.parentNode.insertBefore(gate, runBtn);
        } else {
          document.body.appendChild(gate);
        }
      }
    }

    const headerClass = result.passed ? 'pass' : (result.missingCols.length > 0 ? 'fail' : 'warn');
    const headerIcon = result.passed ? '✅' : (result.missingCols.length > 0 ? '❌' : '⚠️');
    const headerText = result.passed ? 'Data Validated — Ready to Run Audit' :
      result.missingCols.length > 0 ? 'Validation Failed — Missing Required Columns' : 'Validation Warning — Review Before Proceeding';

    const highNullRows = Object.entries(result.nullReport)
      .filter(([, v]) => v.count > 0)
      .sort((a, b) => b[1].pct - a[1].pct)
      .slice(0, 8);

    gate.innerHTML = `
      <div class="aai-val-header ${headerClass}">
        <span style="font-size:16px">${headerIcon}</span>
        <span class="aai-val-title">${headerText}</span>
        <span style="margin-left:auto;font-size:10px;color:#4a5568;font-family:monospace">${escapeHtml(result.fileName || '')}</span>
      </div>
      <div class="aai-val-body">
        <div class="aai-val-grid">
          <div class="aai-val-metric">
            <div class="aai-val-metric-lbl">Total Rows</div>
            <div class="aai-val-metric-val ok">${result.rowCount.toLocaleString()}</div>
          </div>
          <div class="aai-val-metric">
            <div class="aai-val-metric-lbl">Columns</div>
            <div class="aai-val-metric-val">${result.colCount}</div>
          </div>
          <div class="aai-val-metric">
            <div class="aai-val-metric-lbl">Duplicates</div>
            <div class="aai-val-metric-val ${result.dupCount > 0 ? 'warn' : 'ok'}">${result.dupCount.toLocaleString()}</div>
          </div>
          ${result.minDate ? `
          <div class="aai-val-metric">
            <div class="aai-val-metric-lbl">Date Range</div>
            <div class="aai-val-metric-val" style="font-size:10px">${result.minDate} → ${result.maxDate}</div>
          </div>` : ''}
        </div>

        <div class="aai-val-hash">
          <span class="aai-hash-label">FILE HASH (SHA-256):</span>${result.hash}
        </div>

        ${result.missingCols.length > 0 ? `
          <div class="aai-val-missing">
            ⚠ Missing required columns for ${AuditState.agentType || 'selected agent'}:
            <strong>${result.missingCols.join(', ')}</strong>
            <div style="margin-top:4px;font-size:10px;opacity:0.7">
              Expected: ${result.required.join(', ')}
              &nbsp;·&nbsp; Found: ${result.cols.slice(0, 6).join(', ')}${result.cols.length > 6 ? ', …' : ''}
            </div>
          </div>
        ` : ''}

        ${highNullRows.length > 0 ? `
          <table class="aai-null-table">
            <thead><tr><th>Column</th><th>Null Count</th><th>Null %</th><th></th></tr></thead>
            <tbody>
              ${highNullRows.map(([col, v]) => {
                const cls = v.pct > 50 ? 'err' : v.pct > 10 ? 'warn' : 'ok';
                const barW = Math.min(100, v.pct);
                const barColor = v.pct > 50 ? '#ff4d4d' : v.pct > 10 ? '#ff9500' : '#00b85a';
                return `<tr>
                  <td>${escapeHtml(col)}</td>
                  <td class="${cls}">${v.count}</td>
                  <td class="${cls}">${v.pct.toFixed(1)}%</td>
                  <td><span class="aai-null-bar"><span class="aai-null-bar-fill" style="width:${barW}%;background:${barColor}"></span></span></td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        ` : `<div style="font-size:11px;color:#00b85a;margin-bottom:10px">✓ No null value issues detected across ${result.colCount} columns</div>`}

        <div class="aai-val-actions">
          <button class="aai-btn aai-btn-cancel" id="aai-val-cancel">✕ Re-upload File</button>
          <button class="aai-btn aai-btn-confirm ${result.passed ? '' : 'aai-btn-warn'}" id="aai-val-confirm"
            style="${!result.passed ? 'background:rgba(255,149,0,0.1);border-color:rgba(255,149,0,0.4);color:#ff9500' : ''}">
            ${result.passed ? '✅ Confirm & Run Audit' : '⚠ Override & Run Anyway'}
          </button>
        </div>
      </div>
    `;

    gate.classList.add('visible');
    gate.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    document.getElementById('aai-val-confirm').addEventListener('click', () => {
      gate.classList.remove('visible');
      onConfirm(result);
    });
    document.getElementById('aai-val-cancel').addEventListener('click', () => {
      gate.classList.remove('visible');
      if (onCancel) onCancel();
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 6.  PRECISION KPI TILE
  // ─────────────────────────────────────────────────────────────────────────
  async function injectPrecisionKPI() {
    // Wait for KPI bar to appear in the DOM
    const kpiBar = await waitForElement('[class*="kpi"], [id*="kpi"], .cc-kpi, .kpi-bar, .kpi-row, .stats-bar', 5000);
    if (!kpiBar) return;

    const tile = document.createElement('div');
    tile.id = 'aai-precision-kpi';
    tile.title = 'AI Precision Score — hover for details';
    tile.innerHTML = `
      <span class="aai-kpi-icon">🎯</span>
      <span class="aai-kpi-value insufficient" id="aai-prec-value">—</span>
      <span class="aai-kpi-label">AI Precision<br>Score</span>
      <span class="aai-kpi-sub" id="aai-prec-sub">0 reviewed</span>
      <div class="aai-precision-tooltip" id="aai-prec-tooltip">
        <div class="aai-pt-title">📊 Precision Breakdown</div>
        <div class="aai-pt-row"><span class="aai-pt-label">True Positives</span><span class="aai-pt-val aai-pt-tp" id="aai-pt-tp">0</span></div>
        <div class="aai-pt-row"><span class="aai-pt-label">False Positives</span><span class="aai-pt-val aai-pt-fp" id="aai-pt-fp">0</span></div>
        <div class="aai-pt-row"><span class="aai-pt-label">Unreviewed</span><span class="aai-pt-val aai-pt-total" id="aai-pt-nr">0</span></div>
        <hr class="aai-pt-divider"/>
        <div class="aai-pt-row"><span class="aai-pt-label">Precision</span><span class="aai-pt-val" id="aai-pt-pct" style="color:#a855f7">—</span></div>
        <div class="aai-pt-note">Precision = TP ÷ (TP + FP). Click ✅/❌ on findings to record verdicts. Data persists across sessions via IndexedDB.</div>
      </div>
    `;

    // Append to the KPI container
    kpiBar.appendChild(tile);
    await refreshPrecisionKPI();
  }

  async function refreshPrecisionKPI() {
    const all = await dbGetAll('verdicts');
    const tp = all.filter(v => v.verdict === 'tp').length;
    const fp = all.filter(v => v.verdict === 'fp').length;
    const total = all.length;
    const reviewed = tp + fp;
    const precision = reviewed > 0 ? (tp / reviewed * 100) : null;

    const valEl = document.getElementById('aai-prec-value');
    const subEl = document.getElementById('aai-prec-sub');
    const tpEl = document.getElementById('aai-pt-tp');
    const fpEl = document.getElementById('aai-pt-fp');
    const nrEl = document.getElementById('aai-pt-nr');
    const pctEl = document.getElementById('aai-pt-pct');

    if (tpEl) tpEl.textContent = tp;
    if (fpEl) fpEl.textContent = fp;
    if (nrEl) nrEl.textContent = Math.max(0, total - reviewed);
    if (subEl) subEl.textContent = `${reviewed} reviewed`;

    if (valEl) {
      if (precision === null || reviewed < 3) {
        valEl.className = 'aai-kpi-value insufficient';
        valEl.textContent = reviewed < 3 ? `${reviewed}/3` : '—';
        if (pctEl) pctEl.textContent = `Need ${3 - reviewed} more`;
      } else {
        valEl.className = 'aai-kpi-value';
        valEl.textContent = `${precision.toFixed(1)}%`;
        if (pctEl) pctEl.textContent = `${precision.toFixed(1)}%`;
        // Color by score
        const color = precision >= 90 ? '#00e676' : precision >= 70 ? '#ff9500' : '#ff4d4d';
        valEl.style.color = color;
        if (pctEl) pctEl.style.color = color;
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 7.  FINDINGS TABLE INTERCEPTOR (MutationObserver)
  // ─────────────────────────────────────────────────────────────────────────
  let processedRows = new WeakSet();

  function startFindingsObserver() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mut => {
        mut.addedNodes.forEach(node => {
          if (node.nodeType !== 1) return;
          // Look for table rows that look like finding rows
          const rows = node.tagName === 'TR' ? [node] : node.querySelectorAll('tr');
          rows.forEach(row => enhanceFindingRow(row));
        });
        // Also check for attribute changes (e.g. row re-renders)
        if (mut.type === 'childList') {
          const tables = document.querySelectorAll('table');
          tables.forEach(tbl => {
            const rows = tbl.querySelectorAll('tbody tr:not(.aai-evidence-row):not([data-aai-enhanced])');
            rows.forEach(row => enhanceFindingRow(row));
          });
        }
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  function enhanceFindingRow(row) {
    if (processedRows.has(row)) return;
    if (row.classList.contains('aai-evidence-row')) return;
    if (row.dataset.aaiEnhanced) return;

    const cells = row.querySelectorAll('td');
    if (cells.length < 3) return;

    // Heuristic: a "finding row" has severity-like text or severity classes
    const text = row.textContent;
    const hasSeverity = /critical|high|medium|low|🔴|🟠|🟡|🟢/i.test(text);
    const hasEntity = cells.length >= 4;

    if (!hasSeverity && !hasEntity) return;

    processedRows.add(row);
    row.dataset.aaiEnhanced = '1';
    row.classList.add('aai-finding-row-clickable');

    // Generate a stable finding ID from content
    const findingId = 'f_' + hashStr(row.textContent.trim().slice(0, 120));

    // Extract finding info from cells
    const entityCell = cells[0] || cells[1];
    const entity = entityCell ? entityCell.textContent.trim() : 'Unknown';
    const ruleCell = cells[1] || cells[2];
    const rule = ruleCell ? ruleCell.textContent.trim() : '';
    const sevCell = Array.from(cells).find(c => /critical|high|medium|low/i.test(c.textContent));
    const severity = sevCell ? sevCell.textContent.trim() : 'Unknown';

    // Register finding in state
    if (!AuditState.findings.find(f => f.id === findingId)) {
      AuditState.findings.push({ id: findingId, entity, rule, severity, rowEl: row });
      trackCorroboration(entity, findingId);
    }

    // Add expand icon to first cell
    const firstCell = cells[0];
    if (firstCell && !firstCell.querySelector('.aai-expand-icon')) {
      firstCell.innerHTML = `<span class="aai-expand-icon">›</span>` + firstCell.innerHTML;
    }

    // Add verdict cell (append after last cell)
    const lastCell = cells[cells.length - 1];
    if (!lastCell.querySelector('.aai-verdict-btn')) {
      const verdictCell = document.createElement('td');
      verdictCell.className = 'aai-verdict-cell';
      verdictCell.innerHTML = `
        <button class="aai-verdict-btn tp" title="True Positive — confirmed finding">✅ TP</button>
        <button class="aai-verdict-btn fp" title="False Positive — not a real exception">❌ FP</button>
        <span class="aai-verdict-badge" id="vb-${findingId}"></span>
      `;
      row.appendChild(verdictCell);

      verdictCell.querySelector('.aai-verdict-btn.tp').addEventListener('click', async (e) => {
        e.stopPropagation();
        await recordVerdict(findingId, 'tp', entity, rule, severity);
      });
      verdictCell.querySelector('.aai-verdict-btn.fp').addEventListener('click', async (e) => {
        e.stopPropagation();
        await recordVerdict(findingId, 'fp', entity, rule, severity);
      });
    }

    // Also add corroboration badge to severity cell if present
    if (sevCell && !sevCell.querySelector('.aai-corr-badge')) {
      const corrBadge = document.createElement('span');
      corrBadge.id = `corr-${findingId}`;
      corrBadge.className = 'aai-corr-badge single';
      corrBadge.textContent = '1 agent';
      sevCell.appendChild(corrBadge);
    }

    // Create evidence row (hidden)
    const evidenceRow = document.createElement('tr');
    evidenceRow.className = 'aai-evidence-row';
    evidenceRow.id = `er-${findingId}`;
    const evidenceCell = document.createElement('td');
    evidenceCell.className = 'aai-evidence-cell';
    evidenceCell.colSpan = 999;
    evidenceRow.appendChild(evidenceCell);
    row.parentNode.insertBefore(evidenceRow, row.nextSibling);

    // Click to expand evidence
    row.addEventListener('click', (e) => {
      if (e.target.classList.contains('aai-verdict-btn')) return;
      toggleEvidence(findingId, row, evidenceRow, entity, rule, severity);
    });

    // Restore verdict from DB
    restoreVerdict(findingId);
  }

  async function restoreVerdict(findingId) {
    const stored = await dbGet('verdicts', findingId);
    if (stored) {
      updateVerdictUI(findingId, stored.verdict);
    }
  }

  async function recordVerdict(findingId, verdict, entity, rule, severity) {
    await dbSet('verdicts', {
      finding_id: findingId,
      verdict,
      entity,
      rule,
      severity,
      timestamp: Date.now(),
      agent: AuditState.agentType,
      mode: AuditState.mode
    });
    updateVerdictUI(findingId, verdict);
    await refreshPrecisionKPI();
  }

  function updateVerdictUI(findingId, verdict) {
    const badge = document.getElementById(`vb-${findingId}`);
    const tpBtn = document.querySelector(`[data-aai-enhanced] .aai-verdict-btn.tp`);
    if (badge) {
      badge.className = `aai-verdict-badge ${verdict}`;
      badge.textContent = verdict === 'tp' ? '✓ TP' : verdict === 'fp' ? '✗ FP' : '? NR';
    }
    // Mark the row buttons
    const row = document.querySelector(`[data-aai-enhanced][data-finding-id="${findingId}"]`);
    if (!row) {
      // Try finding by evidence row sibling
      const er = document.getElementById(`er-${findingId}`);
      if (er && er.previousElementSibling) {
        const prevRow = er.previousElementSibling;
        prevRow.querySelectorAll('.aai-verdict-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = prevRow.querySelector(`.aai-verdict-btn.${verdict}`);
        if (activeBtn) activeBtn.classList.add('active');
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 8.  EVIDENCE DRILL-DOWN
  // ─────────────────────────────────────────────────────────────────────────
  function toggleEvidence(findingId, row, evidenceRow, entity, rule, severity) {
    const isOpen = evidenceRow.classList.contains('open');

    if (isOpen) {
      evidenceRow.classList.remove('open');
      row.classList.remove('expanded');
      return;
    }

    evidenceRow.classList.add('open');
    row.classList.add('expanded');

    // Build evidence content
    const sourceRows = getSourceRowsForFinding(entity, rule);
    const detectionLogic = getDetectionLogic(rule, severity);
    const cell = evidenceRow.querySelector('.aai-evidence-cell');

    cell.innerHTML = `
      <div class="aai-evidence-inner">
        <div class="aai-evidence-header">
          <span class="aai-evidence-title">📎 Source Evidence — ${entity}</span>
          <span class="aai-evidence-rule">${escapeHtml(detectionLogic.rule)}</span>
          <span class="aai-evidence-meta">
            ${sourceRows.length} source row(s) · severity: ${escapeHtml(severity)} · 
            mode: ${AuditState.mode}
            ${AuditState.fileHash ? ` · file: ${AuditState.fileHash.slice(0, 12)}…` : ''}
          </span>
        </div>
        ${sourceRows.length > 0 ? `
          <table class="aai-source-table">
            <thead>
              <tr>${Object.keys(sourceRows[0]).map(k => `<th>${escapeHtml(k)}</th>`).join('')}</tr>
            </thead>
            <tbody>
              ${sourceRows.slice(0, 8).map(r => `
                <tr>
                  ${Object.entries(r).map(([k, v]) => {
                    const isKey = k.toLowerCase().includes('user') || k.toLowerCase().includes('entity') || k.toLowerCase().includes('id');
                    return `<td class="${isKey ? 'highlight' : ''}" title="${escapeHtml(String(v))}">${escapeHtml(String(v ?? ''))}</td>`;
                  }).join('')}
                </tr>
              `).join('')}
              ${sourceRows.length > 8 ? `<tr><td colspan="999" style="color:#4a5568;font-style:italic">… ${sourceRows.length - 8} more rows not shown</td></tr>` : ''}
            </tbody>
          </table>
        ` : `
          <div style="font-size:11px;color:#7a8aaa;padding:8px 0">
            <strong>Detection Logic:</strong> ${escapeHtml(detectionLogic.description)}<br><br>
            <em style="color:#4a5568">Upload a real data file to see source row evidence here. 
            In DEMO mode, detection rules run against synthetic patterns without linked source rows.</em>
          </div>
        `}
        <div class="aai-evidence-hash">
          DETECTION_RULE: ${escapeHtml(detectionLogic.formula)} 
          &nbsp;·&nbsp; FILE_HASH: ${AuditState.fileHash ? AuditState.fileHash.slice(0, 32) + '…' : 'N/A (DEMO MODE)'}
          &nbsp;·&nbsp; FINDING_ID: ${findingId}
          &nbsp;·&nbsp; AGENT: ${escapeHtml(AuditState.agentType || 'client-side')}
        </div>
      </div>
    `;
  }

  // Get actual source rows from uploaded data for this entity
  function getSourceRowsForFinding(entity, rule) {
    if (!AuditState.uploadedData || AuditState.uploadedData.length === 0) return [];
    const entityLower = entity.toLowerCase();
    return AuditState.uploadedData.filter(row => {
      return Object.values(row).some(v =>
        String(v ?? '').toLowerCase().includes(entityLower) ||
        entityLower.includes(String(v ?? '').toLowerCase())
      );
    }).slice(0, 20);
  }

  function getDetectionLogic(rule, severity) {
    const r = (rule || '').toLowerCase();
    if (r.includes('sod') || r.includes('segregation')) {
      return {
        rule: 'SOD_CONFLICT',
        formula: 'user_roles ∩ conflict_matrix ≠ ∅',
        description: 'User holds two or more roles that create a toxic combination (e.g. can both create vendors and approve payments).'
      };
    }
    if (r.includes('self') && (r.includes('approv') || r.includes('review'))) {
      return {
        rule: 'SELF_APPROVAL',
        formula: 'requestor_id = approver_id',
        description: 'The requestor and approver fields reference the same user — a self-approval violation.'
      };
    }
    if (r.includes('terminat') || r.includes('access')) {
      return {
        rule: 'TERMINATED_ACCESS',
        formula: 'termination_date < TODAY() AND account_status = "ACTIVE"',
        description: 'User account remains active after recorded termination date.'
      };
    }
    if (r.includes('mfa') || r.includes('multi')) {
      return {
        rule: 'MISSING_MFA',
        formula: 'mfa_enabled = FALSE AND account_status = "ACTIVE"',
        description: 'Active privileged account has multi-factor authentication disabled.'
      };
    }
    if (r.includes('round') || r.includes('journal') || r.includes('je')) {
      return {
        rule: 'ROUND_DOLLAR_JE',
        formula: 'amount % 1000 = 0 AND approver IS NULL',
        description: 'Round-dollar journal entry posted without an approver — indicator of potential manipulation.'
      };
    }
    if (r.includes('duplicate') || r.includes('dup')) {
      return {
        rule: 'DUPLICATE_TRANSACTION',
        formula: 'COUNT(*) > 1 GROUP BY amount, vendor, date',
        description: 'Duplicate transaction detected with matching amount, vendor, and posting date.'
      };
    }
    if (r.includes('vendor') || r.includes('master')) {
      return {
        rule: 'VENDOR_ANOMALY',
        formula: 'bank_account_changes > 2 IN 30d OR duplicate_tin',
        description: 'Vendor record shows suspicious modification pattern or duplicate tax identification number.'
      };
    }
    if (r.includes('change') || r.includes('cab') || r.includes('rfc')) {
      return {
        rule: 'CHANGE_MGMT_VIOLATION',
        formula: 'cab_approval_date IS NULL OR approval_date > change_date',
        description: 'Change was implemented without prior CAB approval or approval post-dates the change.'
      };
    }
    return {
      rule: rule.toUpperCase().replace(/\s+/g, '_').slice(0, 30) || 'EXCEPTION_DETECTED',
      formula: 'rule_engine.evaluate(record) = TRUE',
      description: 'Exception detected by the audit rules engine for this control area.'
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 9.  CROSS-AGENT CORROBORATION
  // ─────────────────────────────────────────────────────────────────────────
  function trackCorroboration(entity, findingId) {
    if (!AuditState.agentRunCounts[entity]) {
      AuditState.agentRunCounts[entity] = { count: 1, findingIds: [findingId] };
    } else {
      AuditState.agentRunCounts[entity].count++;
      AuditState.agentRunCounts[entity].findingIds.push(findingId);
      // Update corroboration badge for all findings related to this entity
      AuditState.agentRunCounts[entity].findingIds.forEach(fid => {
        const badge = document.getElementById(`corr-${fid}`);
        if (badge) {
          const cnt = AuditState.agentRunCounts[entity].count;
          badge.className = `aai-corr-badge ${cnt > 1 ? 'corroborated' : 'single'}`;
          badge.textContent = cnt > 1 ? `${cnt} agents ✓` : '1 agent';
          if (cnt > 1) badge.title = `Corroborated by ${cnt} independent audit agents — high confidence`;
        }
      });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 10. FILE UPLOAD INTERCEPTOR
  // ─────────────────────────────────────────────────────────────────────────
  function interceptFileUploads() {
    // Hook all file inputs
    document.addEventListener('change', async (e) => {
      const input = e.target;
      if (input.type !== 'file' || !input.files || input.files.length === 0) return;

      const file = input.files[0];
      if (!file) return;

      // Only intercept data files, not policy docs
      const isDataFile = /\.(csv|xlsx|xls|json|tsv)$/i.test(file.name);
      if (!isDataFile) return;

      await handleFileUpload(file);
    }, true);

    // Hook drop zones
    document.addEventListener('drop', async (e) => {
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      const file = e.dataTransfer.files[0];
      const isDataFile = /\.(csv|xlsx|xls|json|tsv)$/i.test(file.name);
      if (!isDataFile) return;
      await handleFileUpload(file);
    }, true);
  }

  async function handleFileUpload(file) {
    const agentType = getSelectedAgent();
    AuditState.agentType = agentType;

    try {
      const data = await parseFile(file);
      AuditState.uploadedData = data;

      const result = await validateData(data, file.name, agentType);
      AuditState.validationResult = result;

      renderValidationGate(
        result,
        // onConfirm
        (r) => {
          setLiveMode(
            `CSV Upload — ${file.name}`,
            r.hash,
            r.rowCount,
            agentType
          );
          // Let existing code continue — just don't block it
        },
        // onCancel
        () => {
          resetToDemo();
        }
      );
    } catch (err) {
      console.warn('[AuditAI] File parse error:', err);
    }
  }

  async function parseFile(file) {
    return new Promise((resolve, reject) => {
      const name = file.name.toLowerCase();
      if (name.endsWith('.csv') || name.endsWith('.tsv')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target.result;
          if (typeof Papa !== 'undefined') {
            const result = Papa.parse(text, { header: true, skipEmptyLines: true });
            resolve(result.data || []);
          } else {
            // Basic CSV parse fallback
            const lines = text.split('\n').filter(l => l.trim());
            if (lines.length < 2) { resolve([]); return; }
            const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
            const rows = lines.slice(1).map(line => {
              const vals = line.split(',').map(v => v.trim().replace(/"/g, ''));
              const obj = {};
              headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
              return obj;
            });
            resolve(rows);
          }
        };
        reader.onerror = reject;
        reader.readAsText(file);
      } else if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          if (typeof XLSX !== 'undefined') {
            const wb = XLSX.read(e.target.result, { type: 'binary' });
            const ws = wb.Sheets[wb.SheetNames[0]];
            resolve(XLSX.utils.sheet_to_json(ws, { defval: '' }));
          } else {
            resolve([]);
          }
        };
        reader.onerror = reject;
        reader.readAsBinaryString(file);
      } else if (name.endsWith('.json')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const parsed = JSON.parse(e.target.result);
            resolve(Array.isArray(parsed) ? parsed : (parsed.data || parsed.rows || [parsed]));
          } catch { resolve([]); }
        };
        reader.onerror = reject;
        reader.readAsText(file);
      } else {
        resolve([]);
      }
    });
  }

  function getSelectedAgent() {
    // Try to find selected agent from existing UI
    const selected = document.querySelector('[class*="selected"] [class*="agent-name"], .agent-card.selected .agent-name, [data-selected="true"] .agent-name');
    if (selected) return selected.textContent.trim();

    // Try active/checked radio
    const checked = document.querySelector('input[type="radio"]:checked, [class*="agent"].active, [class*="agent"].selected');
    if (checked) {
      const label = checked.closest('[class*="agent"]');
      if (label) return label.textContent.trim().slice(0, 40);
    }

    // Fallback: read from any visible agent indicator
    const agentIndicator = document.querySelector('[id*="selected-agent"], [class*="current-agent"], [id*="agent-type"]');
    if (agentIndicator) return agentIndicator.textContent.trim();

    return AuditState.agentType || 'SOD Auditor';
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 11. "NEW AUDIT" RESET HOOK
  // ─────────────────────────────────────────────────────────────────────────
  function interceptResetButton() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('button, a');
      if (!btn) return;
      const text = btn.textContent.toLowerCase();
      if (text.includes('new audit') || text.includes('reset') || text.includes('start over')) {
        resetToDemo();
        AuditState.findings = [];
        AuditState.agentRunCounts = {};
        AuditState.uploadedData = null;
        AuditState.validationResult = null;
        const gate = document.getElementById('aai-validation-gate');
        if (gate) gate.classList.remove('visible');
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 12. UTILITIES
  // ─────────────────────────────────────────────────────────────────────────
  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function hashStr(str) {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = (h * 0x01000193) >>> 0;
    }
    return h.toString(16);
  }

  function waitForElement(selector, timeout = 3000) {
    return new Promise(resolve => {
      const el = document.querySelector(selector);
      if (el) { resolve(el); return; }
      const obs = new MutationObserver(() => {
        const found = document.querySelector(selector);
        if (found) { obs.disconnect(); resolve(found); }
      });
      obs.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => { obs.disconnect(); resolve(null); }, timeout);
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // 13. INIT
  // ─────────────────────────────────────────────────────────────────────────
  async function init() {
    await initDB();
    injectStyles();
    injectModeBanner();
    interceptFileUploads();
    interceptResetButton();
    startFindingsObserver();

    // Wait briefly for DOM to settle before injecting KPI
    setTimeout(() => injectPrecisionKPI(), 800);

    console.log('[AuditAI Enhancements v1.0] Loaded — DEMO mode active. Upload a file to activate LIVE mode.');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
