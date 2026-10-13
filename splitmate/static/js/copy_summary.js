// Splits the auto-attached data-* attribute and registers a click handler.
// Used by templates/share/summary.html.j2.

(() => {
  const pre = document.getElementById("summary");
  if (!pre) {
    return;
  }
  const text = pre.textContent || "";
  const btn = document.getElementById("copy-summary-btn");
  if (!btn) {
    return;
  }
  btn.addEventListener("click", async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      const original = btn.dataset.label || btn.textContent;
      btn.textContent = "✓";
      setTimeout(() => {
        btn.textContent = original;
      }, 1200);
    } catch (_err) {
      btn.textContent = "✗";
    }
  });
})();
