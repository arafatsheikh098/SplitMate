// Split form behaviour.
//
// All amounts are converted to *integer minor units* (paisa) in the
// hidden inputs the form submits.  This keeps the server contract
// honest: even if a user types "10.50" the wire value is 1050.
//
// We never read or write floats; we work in strings and integers.

const form = document.getElementById("expense-form");
if (form) {
  const amountInput = form.querySelector("input[name=amount]");
  const payerAmount = form.querySelector("input[name=payer_amount]");
  const methodSelect = form.querySelector("select[name=split_method]");
  const participantList = document.getElementById("participants-list");

  // Convert a decimal string to integer minor units (× 100, half-even).
  // Rejects scientific notation and more than two decimals.
  function toMinor(text) {
    if (text === null || text === undefined) return null;
    const t = String(text).trim();
    if (!t) return null;
    if (/e/i.test(t)) throw new Error("scientific notation not allowed");
    const cleaned = t.replace(/,/g, "");
    if (!/^-?\d+(\.\d+)?$/.test(cleaned)) throw new Error("invalid amount");
    const dot = cleaned.indexOf(".");
    let whole = cleaned;
    let frac = "";
    if (dot >= 0) {
      whole = cleaned.slice(0, dot);
      frac = cleaned.slice(dot + 1);
    }
    if (frac.length > 2) throw new Error("too many decimals");
    while (frac.length < 2) frac += "0";
    const sign = whole.startsWith("-") ? -1 : 1;
    if (sign < 0) whole = whole.slice(1);
    const minor = sign * (BigInt(whole || "0") * 100n + BigInt(frac));
    return Number(minor);
  }

  // Convert a hidden integer field back to a human "X.YY" preview.
  function toMajor(minor) {
    if (minor === null || minor === undefined || minor === "") return "";
    const sign = minor < 0 ? "-" : "";
    const abs = Math.abs(minor);
    const major = Math.floor(abs / 100);
    const frac = String(abs % 100).padStart(2, "0");
    return `${sign}${major}.${frac}`;
  }

  // When the user types a decimal amount in the visible field, write
  // the integer minor-unit value into the matching hidden input.
  function bindAmountField(visible, hidden) {
    if (!visible || !hidden) return;
    visible.addEventListener("input", () => {
      try {
        const minor = toMinor(visible.value);
        hidden.value = minor === null ? "" : String(minor);
      } catch {
        hidden.value = "";
      }
    });
  }

  // For the top-level amount and payer_amount we don't have hidden
  // pairs — we just keep the decimal string and let the server
  // convert.  But we *also* pre-validate to keep the form from
  // submitting something obviously broken.
  function validateDecimal(input) {
    if (!input) return true;
    const v = input.value.trim();
    if (!v) return true; // server reports "required"
    try {
      toMinor(v);
      return true;
    } catch {
      input.setCustomValidity("invalid amount");
      return false;
    }
  }

  // Show / hide the right per-participant inputs depending on the
  // chosen split method.
  function applyMethodVisibility() {
    const method = methodSelect ? methodSelect.value : "equal";
    if (!participantList) return;
    for (const li of participantList.querySelectorAll("li")) {
      const exact = li.querySelector('[data-method="exact"]');
      const pct = li.querySelector('[data-method="pct"]');
      const share = li.querySelector('[data-method="share"]');
      if (exact) exact.hidden = method !== "exact";
      if (pct) pct.hidden = method !== "percentage";
      if (share) share.hidden = method !== "shares";
    }
  }

  if (methodSelect) {
    methodSelect.addEventListener("change", applyMethodVisibility);
    applyMethodVisibility();
  }

  // Disallow float-only fields: warn the user before submit.
  form.addEventListener("submit", (event) => {
    const ok =
      validateDecimal(amountInput) & validateDecimal(payerAmount);
    if (!ok) {
      event.preventDefault();
    }
  });
}
