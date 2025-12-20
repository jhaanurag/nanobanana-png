// Lightweight helper for Puter.js demo in index.html
// Waits for DOMContentLoaded and wires up the Puter demo UI.
(function () {
  function el(id) { return document.getElementById(id); }

  function setStatus(msg) {
    const st = el('puter_status');
    if (st) st.textContent = msg;
  }

  async function generate() {
    const prompt = el('puter_prompt').value.trim();
    const model = el('puter_model').value || undefined;
    if (!prompt) { setStatus('Please enter a prompt'); return; }
    setStatus('Generating…');
    try {
      if (typeof puter === 'undefined' || !puter.ai || !puter.ai.txt2img) {
        throw new Error('Puter.js not available. Confirm https://js.puter.com/v2/ is reachable.');
      }
      const opts = model ? { model } : {};
      const img = await puter.ai.txt2img(prompt, opts);
      const container = el('puter_result');
      container.innerHTML = '';
      container.appendChild(img);
      setStatus('Done');
    } catch (err) {
      setStatus('Error: ' + (err && err.message ? err.message : String(err)));
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const btn = el('puter_generate');
    if (btn) btn.addEventListener('click', generate);
  });
})();
