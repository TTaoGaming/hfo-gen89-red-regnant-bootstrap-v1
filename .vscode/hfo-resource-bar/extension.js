// HFO Resource Monitor — VSCode Status Bar Extension
// Reads .hfo_resource_status.json written by P0 Lidless Legion (TRUE_SEEING)
// every 3 seconds and updates the status bar with real resource telemetry.
// Shows current value, 10-min avg, and delta vs 80% target.

const vscode = require('vscode');
const fs     = require('fs');
const path   = require('path');

const POLL_MS      = 3000;   // refresh interval
const STATUS_FILE  = '.hfo_resource_status.json';

// All thresholds relative to the 80% target read from the status file
const OVER_TARGET_WARN  = 5;   // > target + 5%  → yellow
const OVER_TARGET_CRIT  = 15;  // > target + 15% → red

/**
 * Return warning/critical colour if metric is above target.
 * Returns undefined (default) when below target.
 */
function targetColour(pct, target) {
    if (pct >= target + OVER_TARGET_CRIT)
        return new vscode.ThemeColor('statusBarItem.errorBackground');
    if (pct >= target + OVER_TARGET_WARN)
        return new vscode.ThemeColor('statusBarItem.warningBackground');
    return undefined;
}

/** Format a delta: -31.0 → "−31" / +5.0 → "+5" */
function fmtDelta(d) {
    if (d == null) return '?';
    return (d >= 0 ? '+' : '') + d.toFixed(0);
}

function activate(context) {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) return;

    const statusFilePath = path.join(workspaceRoot, STATUS_FILE);

    // Five left-bar items: CPU · RAM · VRAM · NPU · Swap
    const items = {
        cpu:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 104),
        ram:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 103),
        vram: vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 102),
        npu:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 101),
        swap: vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100),
    };
    Object.values(items).forEach(item => {
        item.command = 'hfoResourceBar.showDetails';
        context.subscriptions.push(item);
    });

    // ── Detail command ───────────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('hfoResourceBar.showDetails', () => {
            try {
                const raw    = fs.readFileSync(statusFilePath, 'utf8');
                const status = JSON.parse(raw);
                const c  = status.current    || {};
                const r  = status.rolling_10min || {};
                const g  = status.governance  || {};
                const tgt = status.resource_target_pct || 80;
                const models = (c.ollama_models || [])
                    .map(m => `  • ${m.name}  ${m.vram_mb} MB VRAM`).join('\n') || '  (none loaded)';
                const govLines = (g.actions_taken || []).length
                    ? (g.actions_taken || []).map(a => `  ! ${a}`).join('\n')
                    : '  none this window';

                const msg = [
                    `HFO Gen89 — P0 TRUE_SEEING  (target: ${tgt}% per resource)`,
                    `Updated: ${c.timestamp}`,
                    ``,
                    `                  current   avg10m   peak   Δtarget`,
                    `CPU           ${String(c.cpu_pct||'?').padStart(6)}%  ${String(r.cpu_pct_avg||'?').padStart(6)}%  ${String(r.cpu_pct_peak||'?').padStart(5)}%  ${fmtDelta(r.cpu_delta_to_target)}%`,
                    `RAM           ${String(c.ram_pct||'?').padStart(6)}%  ${String(r.ram_pct_avg||'?').padStart(6)}%  ${String(r.ram_pct_peak||'?').padStart(5)}%  ${fmtDelta(r.ram_delta_to_target)}%`,
                    `VRAM          ${String(c.vram_pct||'?').padStart(6)}%  ${String(r.vram_pct_avg||'?').padStart(6)}%  ${String(r.vram_pct_peak||'?').padStart(5)}%  ${fmtDelta(r.vram_delta_to_target)}%`,
                    `Swap          ${String(c.swap_pct||'?').padStart(6)}%  ${String(r.swap_pct_avg||'?').padStart(6)}%  ${String(r.swap_pct_peak||'?').padStart(5)}%`,
                    ``,
                    `VRAM detail   ${c.vram_used_gb} GB / ${c.vram_budget_gb} GB  gate: ${c.gpu_gate}`,
                    `RAM free      ${c.ram_free_gb} GB  (avg ${r.ram_free_gb_avg} GB)`,
                    ``,
                    `Ollama models loaded:`,
                    models,
                    ``,
                    `NPU           ${c.npu_active ? 'ACTIVE ●' : 'idle ○'}  10-min rate ${r.npu_active_rate_pct}%${r.npu_underutilised ? '  ⚠ UNDERUTILISED' : ''}`,
                    ``,
                    `Governance actions (this window):`,
                    govLines,
                    `NPU preferred: ${g.npu_preferred ? 'YES — GPU/RAM pressure detected' : 'no'}`,
                    `Evictions:     ${g.evicted_models || 0} model(s) this session`,
                    `Violations (10m): ${r.governance_violations || 0}`,
                    ``,
                    `Python procs  ${c.python_proc_count}   HFO daemons ${c.hfo_daemon_count}`,
                    `Disk free     ${c.disk_free_gb} GB  (${c.disk_used_pct}% used)`,
                ].join('\n');

                vscode.window.showInformationMessage(msg, { modal: true });
            } catch (e) {
                vscode.window.showWarningMessage(
                    `HFO Resource Bar: could not read ${STATUS_FILE} — is P0 daemon running?`
                );
            }
        })
    );

    // ── Poll & update ────────────────────────────────────────────────────────
    function update() {
        let status;
        try {
            const raw = fs.readFileSync(statusFilePath, 'utf8');
            status    = JSON.parse(raw);
        } catch {
            items.cpu.text = '$(loading~spin) HFO…';
            items.cpu.tooltip = `Waiting for P0 TRUE_SEEING\n(${statusFilePath})`;
            items.cpu.backgroundColor = undefined;
            items.cpu.show();
            [items.ram, items.vram, items.npu, items.swap].forEach(i => i.hide());
            return;
        }

        const c   = status.current        || {};
        const r   = status.rolling_10min  || {};
        const g   = status.governance     || {};
        const tgt = status.resource_target_pct || 80;

        // ── CPU ──────────────────────────────────────────────────────────────
        const cpuPct  = c.cpu_pct ?? 0;
        const cpuAvg  = r.cpu_pct_avg ?? cpuPct;
        const cpuDelta = r.cpu_delta_to_target;
        items.cpu.text = `$(pulse) CPU:${cpuPct}%(${fmtDelta(cpuDelta)})`;
        items.cpu.tooltip = new vscode.MarkdownString(
            `**CPU** — target ${tgt}%\n\nCurrent: \`${cpuPct}%\`\n` +
            `10-min avg: \`${cpuAvg}%\`  peak: \`${r.cpu_pct_peak}%\`\n` +
            `Δ target: \`${fmtDelta(cpuDelta)}%\``
        );
        items.cpu.backgroundColor = targetColour(cpuAvg, tgt);
        items.cpu.show();

        // ── RAM ──────────────────────────────────────────────────────────────
        const ramPct   = c.ram_pct ?? 0;
        const ramAvg   = r.ram_pct_avg ?? ramPct;
        const ramDelta = r.ram_delta_to_target;
        const npuPref  = g.npu_preferred;
        items.ram.text = `$(database) RAM:${ramPct}%(${fmtDelta(ramDelta)})`;
        items.ram.tooltip = new vscode.MarkdownString(
            `**RAM** — target ${tgt}%\n\nCurrent: \`${ramPct}%\`  free: \`${c.ram_free_gb} GB\`\n` +
            `10-min avg: \`${ramAvg}%\`  peak: \`${r.ram_pct_peak}%\`\n` +
            `Δ target: \`${fmtDelta(ramDelta)}%\`` +
            (npuPref ? '\n\n⚠ **NPU PREFERRED** — RAM/GPU pressure' : '')
        );
        items.ram.backgroundColor = targetColour(ramAvg, tgt);
        items.ram.show();

        // ── VRAM ─────────────────────────────────────────────────────────────
        const vramPct   = c.vram_pct ?? 0;
        const vramAvg   = r.vram_pct_avg ?? vramPct;
        const vramDelta = r.vram_delta_to_target;
        const modelNames = (c.ollama_models || []).map(m => m.name).join(', ') || 'none';
        items.vram.text = `$(circuit-board) VRAM:${c.vram_used_gb}G(${fmtDelta(vramDelta)})`;
        items.vram.tooltip = new vscode.MarkdownString(
            `**GPU VRAM** — target ${tgt}% of ${c.vram_budget_gb} GB\n\n` +
            `Used: \`${c.vram_used_gb} GB  (${vramPct}%)\`\n` +
            `10-min avg: \`${r.vram_used_gb_avg} GB\`  peak: \`${r.vram_pct_peak}%\`\n` +
            `Δ target: \`${fmtDelta(vramDelta)}%\`\n` +
            `Gate: \`${c.gpu_gate}\`  Models: \`${modelNames}\``
        );
        items.vram.backgroundColor = targetColour(vramAvg, tgt);
        items.vram.show();

        // ── NPU ──────────────────────────────────────────────────────────────
        const npuActive = !!c.npu_active;
        const npuUnder  = r.npu_underutilised;
        items.npu.text = npuActive
            ? '$(zap) NPU:●'
            : (npuUnder ? '$(warning) NPU:○↓' : '$(debug-disconnect) NPU:○');
        items.npu.tooltip = new vscode.MarkdownString(
            `**NPU (OpenVINO)** — target: actively used when GPU/RAM pressure\n\n` +
            `Status: \`${npuActive ? 'ACTIVE' : 'idle'}\`` +
            (c.npu_last_inference_s != null ? `\nLast inference: \`${c.npu_last_inference_s}s ago\`` : '') +
            `\n10-min active rate: \`${r.npu_active_rate_pct ?? 0}%\`` +
            (npuUnder ? '\n\n⚠ **UNDERUTILISED** — NPU has not run in 10 min' : '') +
            (npuPref   ? '\n🔁 Governor recommends routing to NPU'           : '')
        );
        items.npu.backgroundColor = npuUnder
            ? new vscode.ThemeColor('statusBarItem.warningBackground')
            : undefined;
        items.npu.show();

        // ── Swap ─────────────────────────────────────────────────────────────
        const swapPct  = c.swap_pct ?? 0;
        const swapAvg  = r.swap_pct_avg ?? swapPct;
        items.swap.text = `$(symbol-keyword) Swap:${swapPct}%`;
        items.swap.tooltip = new vscode.MarkdownString(
            `**Swap / Pagefile** — warn at 75%\n\n` +
            `Current: \`${swapPct}%\`  used: \`${c.swap_used_gb}/${c.swap_total_gb} GB\`\n` +
            `10-min avg: \`${swapAvg}%\`  peak: \`${r.swap_pct_peak}%\``
        );
        items.swap.backgroundColor = swapPct >= 75
            ? new vscode.ThemeColor('statusBarItem.errorBackground')
            : swapPct >= 55
                ? new vscode.ThemeColor('statusBarItem.warningBackground')
                : undefined;
        items.swap.show();
    }

    update();
    const timer = setInterval(update, POLL_MS);
    context.subscriptions.push({ dispose: () => clearInterval(timer) });
}

function deactivate() {}

module.exports = { activate, deactivate };

// Reads .hfo_resource_status.json written by P0 Lidless Legion (TRUE_SEEING)
// every 3 seconds and updates the status bar with real resource telemetry.

const vscode = require('vscode');
const fs     = require('fs');
const path   = require('path');

const POLL_MS      = 3000;   // refresh interval
const STATUS_FILE  = '.hfo_resource_status.json';

// Warn thresholds (colour the item yellow/red)
const CPU_WARN     = 85;   // %
const CPU_CRIT     = 92;
const RAM_WARN     = 80;
const RAM_CRIT     = 90;
const VRAM_WARN    = 70;
const VRAM_CRIT    = 90;
const SWAP_WARN    = 55;
const SWAP_CRIT    = 75;

/**
 * Determine status-bar background colour based on metric pressure.
 * Returns a ThemeColor key or undefined (= default).
 */
function pressureColour(pct, warn, crit) {
    if (pct >= crit)  return new vscode.ThemeColor('statusBarItem.errorBackground');
    if (pct >= warn)  return new vscode.ThemeColor('statusBarItem.warningBackground');
    return undefined;
}

/**
 * Build tooltip markdown for a resource row.
 */
function mkTooltip(title, current, avg, peak, unit = '%') {
    return `**${title}**\n\nCurrent: \`${current}${unit}\`\n10-min avg: \`${avg ?? '…'}${unit}\`\n10-min peak: \`${peak ?? '…'}${unit}\``;
}

function activate(context) {
    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!workspaceRoot) return;

    const statusFilePath = path.join(workspaceRoot, STATUS_FILE);

    // ── Create status bar items (left side, high priority) ──────────────────
    const items = {
        cpu:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 104),
        ram:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 103),
        vram: vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 102),
        npu:  vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 101),
        swap: vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100),
    };

    Object.values(items).forEach(item => {
        item.command = 'hfoResourceBar.showDetails';
        context.subscriptions.push(item);
    });

    // ── Command: show details ────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('hfoResourceBar.showDetails', () => {
            try {
                const raw    = fs.readFileSync(statusFilePath, 'utf8');
                const status = JSON.parse(raw);
                const c = status.current;
                const r = status.rolling_10min;
                const models = (c.ollama_models || [])
                    .map(m => `  • ${m.name}  ${m.vram_mb} MB VRAM`)
                    .join('\n') || '  (none loaded)';

                const msg = [
                    `HFO Gen89 — P0 TRUE_SEEING`,
                    `Updated: ${c.timestamp}`,
                    ``,
                    `CPU        ${c.cpu_pct}%  (avg ${r.cpu_pct_avg}%  peak ${r.cpu_pct_peak}%)`,
                    `RAM        ${c.ram_pct}%  free ${c.ram_free_gb} GB  (avg ${r.ram_pct_avg}%)`,
                    `Swap       ${c.swap_pct}%  used ${c.swap_used_gb}/${c.swap_total_gb} GB`,
                    `VRAM       ${c.vram_used_gb} GB / ${c.vram_budget_gb} GB  (${c.vram_pct}%)`,
                    `GPU gate   ${c.gpu_gate}`,
                    `Ollama models loaded:`,
                    models,
                    ``,
                    `NPU active   ${c.npu_active ? 'YES' : 'no'}   10-min rate ${r.npu_active_rate_pct}%`,
                    `Python procs ${c.python_proc_count}   HFO daemons ${c.hfo_daemon_count}`,
                    `Disk free    ${c.disk_free_gb} GB  (${c.disk_used_pct}% used)`,
                    `Governance violations (10 min): ${r.governance_violations}`,
                ].join('\n');

                vscode.window.showInformationMessage(msg, { modal: true });
            } catch (e) {
                vscode.window.showWarningMessage(
                    `HFO Resource Bar: could not read ${STATUS_FILE} — is P0 daemon running?`
                );
            }
        })
    );

    // ── Poll & update ────────────────────────────────────────────────────────
    function update() {
        let status;
        try {
            const raw = fs.readFileSync(statusFilePath, 'utf8');
            status    = JSON.parse(raw);
        } catch {
            // P0 not yet started or file missing — show waiting state
            items.cpu.text = '$(loading~spin) HFO…';
            items.cpu.tooltip = `Waiting for P0 TRUE_SEEING\n(${statusFilePath})`;
            items.cpu.backgroundColor = undefined;
            items.cpu.show();
            [items.ram, items.vram, items.npu, items.swap].forEach(i => i.hide());
            return;
        }

        const c = status.current    || {};
        const r = status.rolling_10min || {};

        // ── CPU ──────────────────────────────────────────────────────────────
        const cpuPct  = c.cpu_pct ?? 0;
        const cpuIcon = cpuPct >= CPU_CRIT ? '$(warning)' : '$(pulse)';
        items.cpu.text            = `${cpuIcon} CPU:${cpuPct}%`;
        items.cpu.tooltip         = new vscode.MarkdownString(
            mkTooltip('CPU', cpuPct, r.cpu_pct_avg, r.cpu_pct_peak)
        );
        items.cpu.backgroundColor = pressureColour(cpuPct, CPU_WARN, CPU_CRIT);
        items.cpu.show();

        // ── RAM ──────────────────────────────────────────────────────────────
        const ramPct  = c.ram_pct ?? 0;
        const ramIcon = ramPct >= RAM_CRIT ? '$(warning)' : '$(database)';
        items.ram.text            = `${ramIcon} RAM:${ramPct}%`;
        items.ram.tooltip         = new vscode.MarkdownString(
            mkTooltip('RAM', ramPct, r.ram_pct_avg, r.ram_pct_peak) +
            `\nFree: \`${c.ram_free_gb} GB\``
        );
        items.ram.backgroundColor = pressureColour(ramPct, RAM_WARN, RAM_CRIT);
        items.ram.show();

        // ── VRAM ─────────────────────────────────────────────────────────────
        const vramPct  = c.vram_pct ?? 0;
        const vramIcon = vramPct >= VRAM_CRIT ? '$(warning)' : '$(circuit-board)';
        const modelNames = (c.ollama_models || []).map(m => m.name).join(', ') || 'none';
        items.vram.text            = `${vramIcon} VRAM:${c.vram_used_gb}GB`;
        items.vram.tooltip         = new vscode.MarkdownString(
            mkTooltip('GPU VRAM', vramPct, r.vram_pct_avg, r.vram_pct_peak) +
            `\nUsed: \`${c.vram_used_gb} / ${c.vram_budget_gb} GB\`` +
            `\nGate: \`${c.gpu_gate}\`` +
            `\nModels: \`${modelNames}\``
        );
        items.vram.backgroundColor = pressureColour(vramPct, VRAM_WARN, VRAM_CRIT);
        items.vram.show();

        // ── NPU ──────────────────────────────────────────────────────────────
        const npuActive = !!c.npu_active;
        items.npu.text            = npuActive ? '$(zap) NPU:●' : '$(debug-disconnect) NPU:○';
        items.npu.tooltip         = new vscode.MarkdownString(
            `**NPU (OpenVINO)**\n\nStatus: \`${npuActive ? 'ACTIVE' : 'idle'}\`` +
            (c.npu_last_inference_s != null ? `\nLast inference: \`${c.npu_last_inference_s}s ago\`` : '') +
            `\n10-min active rate: \`${r.npu_active_rate_pct ?? 0}%\``
        );
        items.npu.backgroundColor = (!npuActive && r.npu_active_rate_pct === 0)
            ? new vscode.ThemeColor('statusBarItem.warningBackground')
            : undefined;
        items.npu.show();

        // ── Swap ─────────────────────────────────────────────────────────────
        const swapPct  = c.swap_pct ?? 0;
        items.swap.text            = `$(symbol-keyword) Swap:${swapPct}%`;
        items.swap.tooltip         = new vscode.MarkdownString(
            mkTooltip('Swap', swapPct, r.swap_pct_avg, r.swap_pct_peak) +
            `\nUsed: \`${c.swap_used_gb} / ${c.swap_total_gb} GB\``
        );
        items.swap.backgroundColor = pressureColour(swapPct, SWAP_WARN, SWAP_CRIT);
        items.swap.show();
    }

    update();
    const timer = setInterval(update, POLL_MS);
    context.subscriptions.push({ dispose: () => clearInterval(timer) });
}

function deactivate() {}

module.exports = { activate, deactivate };
