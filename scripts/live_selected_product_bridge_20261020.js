/* Empire AI public-site additive product handoff, 20 Oct 2026.
 * Works on the deployed Next.js HTML/chunks without replacing another
 * owner's premium brokerage copy or direct-checkout application.
 * Product choice must match approved SAME-ORIGIN GET catalogue; no writes.
 */
(() => {
  "use strict";
  const page = location.pathname.replace(/\/$/, "");
  if (page !== "/buy" && page !== "/commercial") return;
  const normalize = value => String(value || "").normalize("NFKD")
    .toLowerCase().replace(/[^a-z0-9]/g, "");
  const matchCode = value => /^[a-z][a-z0-9_]{2,63}$/.test(value);
  const endpoint = page === "/buy"
    ? "/v1/checkout/catalog" : "/v1/checkout/commercial/offers";
  const controller = new AbortController();
  const failTimer = setTimeout(() => controller.abort(), 7000);
  fetch(endpoint, {method:"GET", credentials:"same-origin",
    cache:"no-store", signal:controller.signal})
    .then(response => {
      if (!response.ok) throw Error("catalogue unavailable");
      return response.json();
    })
    .then(data => {
      const rows = page === "/buy" ? data.products : data.offers;
      if (!Array.isArray(rows) || !rows.length || rows.length > 50) return;
      if (page === "/commercial" &&
          data.status !== "FOUNDER_LED_ENQUIRY_AVAILABLE") return;
      const catalogue = new Map();
      for (const item of rows) {
        if (item && matchCode(item.product_code)) {
          const display = item.name || item.product_code.replace(/_/g, " ");
          catalogue.set(normalize(display), item.product_code);
        }
      }
      if (page === "/buy") setupBuy(catalogue);
      else setupCommercial(new Set([...catalogue.values()]));
    })
    .catch(() => {})  // fail closed: never offer unverified product
    .finally(() => clearTimeout(failTimer));

  function setupBuy(catalogue) {
    const candidates = () => [...document.querySelectorAll("button[type=button]")]
      .filter(button => {
        const title = button.querySelector("strong");
        return title && catalogue.has(normalize(title.textContent));
      });
    let selected = "";
    const chosen = () => {
      const buttons = candidates();
      const active = buttons.find(button =>
        button.className.includes("border-[#60a5fa]/45"));
      const strong = active?.querySelector("strong");
      if (strong) selected = catalogue.get(normalize(strong.textContent)) || "";
      if (!selected && buttons.length) {
        selected = catalogue.get(normalize(buttons[0].querySelector("strong").textContent)) || "";
      }
      return selected;
    };
    function update() {
      const code = chosen();
      if (!code) return;
      const href = "/commercial?product=" + encodeURIComponent(code) + "#commercial-enquiry";
      const orderButton = [...document.querySelectorAll("form button")]
        .find(button => /CREATE PAYMENT REQUEST|CREATING ORDER/i.test(button.textContent));
      if (orderButton) {
        const form = orderButton.closest("form");
        if (form) {
          let link = form.querySelector("#empire-agency-proposal-alternative");
          if (!link) {
            link = document.createElement("a");
            link.id = "empire-agency-proposal-alternative";
            link.textContent = "REQUEST A PROPOSAL INSTEAD";
            link.className = "mt-4 flex min-h-12 w-full items-center justify-center rounded-xl border border-cyan-300/50 px-4 py-3 text-center text-xs font-bold tracking-[.1em] text-cyan-200 hover:text-white";
            // A normal anchor; never invokes the payment form's submit.
            orderButton.insertAdjacentElement("afterend", link);
          }
          if (link.getAttribute("href") !== href) link.setAttribute("href", href);
        }
      }
      // The checkout-disabled page already has a proposal anchor; keep its
      // selected product bound as well, without altering any other link.
      for (const link of document.querySelectorAll('a[href^="/commercial"]')) {
        if (link.textContent.trim().toUpperCase() === "REQUEST A PROPOSAL" &&
            link.getAttribute("href") !== href) link.setAttribute("href", href);
      }
    }
    document.addEventListener("click", event => {
      const button = event.target.closest?.("button[type=button]");
      if (!button || !candidates().includes(button)) return;
      const strong = button.querySelector("strong");
      selected = catalogue.get(normalize(strong?.textContent)) || selected;
      requestAnimationFrame(update);
    }, true);
    let queued = false;
    new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; update(); });
    }).observe(document.body, {childList:true, subtree:true});
    update();
  }

  function setupCommercial(allowedCodes) {
    const requested = new URLSearchParams(location.search).get("product");
    if (!requested || !allowedCodes.has(requested)) return;
    let applied = false;
    let queued = false;
    const apply = () => {
      if (applied) return;
      const section = document.getElementById("commercial-enquiry");
      const select = section?.querySelector("select");
      if (!select || ![...select.options].some(option => option.value === requested)) return;
      if (select.value === requested) { applied = true; return; }
      // Use the page's own product button so React owns the updated state.
      const option = [...select.options].find(option => option.value === requested);
      const offerButton = [...document.querySelectorAll('button[aria-pressed]')]
        .find(button => {
          const title = button.querySelector("strong");
          return title && normalize(title.textContent) === normalize(option.textContent);
        });
      if (offerButton) offerButton.click();
      else {
        const native = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
        native?.set?.call(select, requested);
        select.dispatchEvent(new Event("change", {bubbles:true}));
      }
      requestAnimationFrame(() => {
        if (select.value === requested) applied = true;
      });
    };
    new MutationObserver(() => {
      if (applied || queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; apply(); });
    }).observe(document.body, {childList:true, subtree:true});
    apply();
  }
})();
