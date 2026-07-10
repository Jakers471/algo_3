/**
 * Which overlay layers are drawn. One job: hold that set, and filter marks by it.
 *
 * A visibility switch, never a computation switch. The server computes every
 * indicator and ships every mark regardless; hiding one only stops it being
 * stroked. That is deliberate - the snapshot table reads the same row the chart
 * draws, so a hidden leg is still a leg in the table, and the two windows cannot
 * come to disagree about what happened, only about what is on screen.
 *
 * The filter never learns what a layer means. Every mark carries `source` - the
 * indicator that produced it - and this file compares strings.
 */

const STORAGE_KEY = 'chart.hiddenLayers';

export class Layers {
  /** `defs` is `[{id, label, visible}]` from /api/config. */
  constructor(defs = []) {
    this.defs = defs;
    const stored = load();
    this.hidden = new Set(
      stored || defs.filter((d) => !d.visible).map((d) => d.id),
    );
    this._listeners = [];
  }

  visible(source) {
    return !this.hidden.has(source);
  }

  /** Drop every mark whose layer is hidden. Marks with no source always draw. */
  filter(marks) {
    return marks.filter((m) => !m.source || this.visible(m.source));
  }

  set(id, visible) {
    if (visible) this.hidden.delete(id);
    else this.hidden.add(id);
    save(this.hidden);
    for (const fn of this._listeners) fn(this);
  }

  /** Called whenever the set changes, so both draw paths can restroke. */
  onChange(fn) {
    this._listeners.push(fn);
  }
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;   // a corrupt or unavailable store is not worth a broken chart
  }
}

function save(hidden) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...hidden]));
  } catch {
    /* private mode, quota, whatever. The chart still works for this session. */
  }
}
