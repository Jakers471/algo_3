/**
 * The Layers control: a checkbox per drawing. One job, and it is a door.
 *
 * It reads the layer definitions the server sent, renders a checkbox for each,
 * and calls `layers.set()`. It holds no state of its own and knows no indicator
 * - the label came from Python, and so did the order.
 */

/** Fill a `<details>` with one checkbox per layer. Returns nothing; wires events. */
export function LayersPanel(root, layers) {
  if (!root || !layers.defs.length) return;
  const panel = root.querySelector('.layers-panel');

  for (const def of layers.defs) {
    const row = document.createElement('label');
    row.className = 'layer';

    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = layers.visible(def.id);
    box.addEventListener('change', () => layers.set(def.id, box.checked));

    const name = document.createElement('span');
    name.textContent = def.label;

    row.append(box, name);
    panel.append(row);
  }

  // Click anywhere else and the panel closes, like every other menu on the page.
  document.addEventListener('click', (event) => {
    if (root.open && !root.contains(event.target)) root.open = false;
  });
}
