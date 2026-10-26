/**
 * SplitMate — Modern Dynamic Frontend Interactions
 * Compliant with strict CSP ('self')
 */

// ---------------------------------------------------------------------------
// 1. Theme Switcher (Dark / Light)
// ---------------------------------------------------------------------------
function initTheme() {
  const saved = localStorage.getItem("splitmate_theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = saved || (prefersDark ? "dark" : "light");

  document.documentElement.setAttribute("data-theme", theme);
  updateThemeToggleUI(theme);

  const toggleBtn = document.getElementById("theme-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("splitmate_theme", next);
      updateThemeToggleUI(next);
      showToast(next === "dark" ? "🌙 Dark mode enabled" : "☀️ Light mode enabled", "info");
    });
  }
}

function updateThemeToggleUI(theme) {
  const toggleBtn = document.getElementById("theme-toggle");
  if (!toggleBtn) return;
  const isDark = theme === "dark";
  toggleBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
  toggleBtn.title = isDark ? "Switch to light theme" : "Switch to dark theme";
  
  const iconSun = toggleBtn.querySelector(".icon-sun");
  const iconMoon = toggleBtn.querySelector(".icon-moon");
  if (iconSun && iconMoon) {
    iconSun.style.display = isDark ? "block" : "none";
    iconMoon.style.display = isDark ? "none" : "block";
  }
}

// ---------------------------------------------------------------------------
// 2. Toast Notifications
// ---------------------------------------------------------------------------
window.showToast = function(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 2600);
};

// ---------------------------------------------------------------------------
// 3. One-Click Clipboard Copying
// ---------------------------------------------------------------------------
function initCopyButtons() {
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy-target], .copy-btn");
    if (!btn) return;

    let textToCopy = "";
    if (btn.dataset.copyText) {
      textToCopy = btn.dataset.copyText;
    } else if (btn.dataset.copyTarget) {
      const target = document.querySelector(btn.dataset.copyTarget);
      if (target) {
        textToCopy = target.value || target.textContent || "";
      }
    }

    if (!textToCopy) return;

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        const ta = document.createElement("textarea");
        ta.value = textToCopy;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }

      const originalHtml = btn.innerHTML;
      btn.classList.add("copied");
      btn.innerHTML = `<span>✓ Copied!</span>`;
      window.showToast("Link copied to clipboard!", "success");

      setTimeout(() => {
        btn.classList.remove("copied");
        btn.innerHTML = originalHtml;
      }, 1800);
    } catch (_err) {
      window.showToast("Failed to copy", "error");
    }
  });
}

// ---------------------------------------------------------------------------
// 4. Live Expense Search & Filter
// ---------------------------------------------------------------------------
function initExpenseFiltering() {
  const searchInput = document.getElementById("expense-search");
  const categoryFilters = document.querySelectorAll(".category-pill");
  const expenseItems = document.querySelectorAll(".expense-item");
  const countBadge = document.getElementById("expense-count");
  const totalDisplay = document.getElementById("visible-total-amount");
  const emptyState = document.getElementById("no-filter-results");

  if (!searchInput && categoryFilters.length === 0) return;

  let activeCategory = "all";
  let searchQuery = "";

  function applyFilter() {
    let visibleCount = 0;
    let visibleMinorSum = 0;

    expenseItems.forEach((item) => {
      const title = (item.dataset.title || "").toLowerCase();
      const category = (item.dataset.category || "").toLowerCase();
      const amountMinor = parseInt(item.dataset.amountMinor || "0", 10);
      const payer = (item.dataset.payer || "").toLowerCase();

      const matchesCat = activeCategory === "all" || category === activeCategory;
      const matchesSearch = !searchQuery || 
        title.includes(searchQuery) || 
        category.includes(searchQuery) ||
        payer.includes(searchQuery);

      if (matchesCat && matchesSearch) {
        item.style.display = "";
        visibleCount++;
        visibleMinorSum += amountMinor;
      } else {
        item.style.display = "none";
      }
    });

    if (countBadge) {
      countBadge.textContent = visibleCount;
    }

    if (totalDisplay) {
      const major = Math.floor(visibleMinorSum / 100);
      const minor = String(visibleMinorSum % 100).padStart(2, "0");
      totalDisplay.textContent = `${major}.${minor}`;
    }

    if (emptyState) {
      emptyState.style.display = (visibleCount === 0 && expenseItems.length > 0) ? "block" : "none";
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      applyFilter();
    });
  }

  categoryFilters.forEach((pill) => {
    pill.addEventListener("click", () => {
      categoryFilters.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeCategory = (pill.dataset.category || "all").toLowerCase();
      applyFilter();
    });
  });
}

// ---------------------------------------------------------------------------
// 5. Active Tab Highlighting for Subnavigation
// ---------------------------------------------------------------------------
function initNavHighlight() {
  const currentPath = window.location.pathname;
  const navTabs = document.querySelectorAll(".group-nav-tab");
  navTabs.forEach((tab) => {
    const href = tab.getAttribute("href");
    if (!href) return;
    if (href === currentPath || (href !== "/" && currentPath.startsWith(href) && href.length > 10)) {
      tab.classList.add("active");
      tab.setAttribute("aria-current", "page");
    }
  });
}

// ---------------------------------------------------------------------------
// 6. Expense Form Helper: Auto-sync Payer Amount
// ---------------------------------------------------------------------------
function initExpenseFormSync() {
  const form = document.getElementById("expense-form");
  if (!form) return;

  const totalInput = form.querySelector("input[name=amount]");
  const payerInput = form.querySelector("input[name=payer_amount]");

  if (totalInput && payerInput) {
    let userEditedPayer = false;

    payerInput.addEventListener("input", () => {
      userEditedPayer = payerInput.value.trim() !== "";
    });

    totalInput.addEventListener("input", () => {
      if (!userEditedPayer || payerInput.value.trim() === "") {
        payerInput.value = totalInput.value;
      }
    });
  }
}

// ---------------------------------------------------------------------------
// 7. Initialize on DOM ready
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initCopyButtons();
  initExpenseFiltering();
  initNavHighlight();
  initExpenseFormSync();
});
