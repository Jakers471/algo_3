/**
 * The live session scorecard: a floating card of session_stats fields.
 *
 * One job: render the current session's numbers and toggle visibility on
 * request. It holds no state of its own beyond the DOM node - the caller
 * (main.js) decides WHEN to open it (a click near the session's own vline)
 * and feeds it the latest fields on every bar, the same `snapshot.fields`
 * the desktop table reads. It computes nothing: session_stats is the only
 * thing that ever touches these numbers, so this file only formats them.
 */

const pct = (n) => (n == null ? '--' : `${Math.round(n * 100)}%`);

/** A field measured in range_scale multiples, shown back out in points. */
const asPoints = (n, scale) => (n == null || scale == null ? '--' : Math.round(n * scale));

const eff = (n) => (n == null ? '--' : n.toFixed(2));

const vol = (n) => {
  if (n == null) return '--';
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(1)}K`;
  return `${sign}${Math.round(abs)}`;
};

export class SessionPanel {
  constructor(root) {
    this.root = root;
    this.visible = false;
    this.label = null;
  }

  /** Click the SAME session's line again to close it; a different one reopens. */
  toggle(label, fields) {
    if (this.visible && this.label === label) {
      this.hide();
      return;
    }
    this.show(label, fields);
  }

  show(label, fields) {
    this.label = label;
    this.visible = true;
    this.root.classList.add('visible');
    this.update(fields);
  }

  hide() {
    this.visible = false;
    this.label = null;
    this.root.classList.remove('visible');
  }

  /** Called on every bar while open; a no-op otherwise - cheap to call always. */
  update(fields) {
    if (!this.visible) return;
    if (!fields || fields.session_bars == null) {
      this.root.innerHTML = `<div class="session-title">${this.label}</div>`
        + '<div class="session-row muted">no reading yet</div>';
      return;
    }

    const scale = fields.range_scale;
    const poc = fields.session_poc == null ? '--' : fields.session_poc.toFixed(2);

    this.root.innerHTML = `
      <div class="session-title">${this.label}</div>
      <div class="session-row">range ${asPoints(fields.session_range, scale)} pts `
        + `(${fields.session_bars} bars)</div>
      <div class="session-row">net ${asPoints(fields.session_net, scale)} = `
        + `${pct(fields.session_net_ratio)} of range `
        + `<span class="muted">&lt;- direction/strength</span></div>
      <div class="session-row">closed at ${pct(fields.session_closed_ratio)} of range</div>
      <div class="session-row">body ${pct(fields.session_body_ratio)} | `
        + `up-wick ${pct(fields.session_upwick_ratio)} | `
        + `low-wick ${pct(fields.session_lowwick_ratio)}</div>
      <div class="session-row">travel ${asPoints(fields.session_travel, scale)} pts | `
        + `efficiency ${eff(fields.session_efficiency)}</div>
      <div class="session-row">direction changes ${fields.session_dir_changes ?? '--'} | `
        + `high formed ${pct(fields.session_high_at_ratio)} in | `
        + `low formed ${pct(fields.session_low_at_ratio)} in</div>
      <div class="session-row">volume ${vol(fields.session_volume)} | `
        + `delta ${vol(fields.session_delta)}</div>
      <div class="session-row">POC @ ${poc} (${pct(fields.session_poc_ratio)} of range)</div>
    `;
  }
}
