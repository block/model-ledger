/* Per-page Markdown actions: Copy / View / Open in Claude.
 * Exposes the raw .md the docs already publish (built by docs_hooks/llms_txt.py),
 * so this site is as consumable by an agent as it is by a human — fitting for a
 * tool whose product is an MCP server. Re-runs on Material's instant navigation. */
document$.subscribe(function () {
  var content = document.querySelector(".md-content__inner");
  if (!content) return;
  var h1 = content.querySelector("h1");
  if (!h1 || content.querySelector(".md-actions")) return;

  // Rendered pages use directory URLs (/x/); their source .md lives at /x.md,
  // and the site root maps to /index.md. The logo href gives the base path.
  var logo = document.querySelector(".md-header__button.md-logo");
  var base = logo ? new URL(logo.href).pathname : "/";
  var path = location.pathname;
  var mdUrl =
    path === base || path === base.replace(/\/$/, "")
      ? base.replace(/\/$/, "") + "/index.md"
      : path.replace(/\/$/, "") + ".md";

  var bar = document.createElement("div");
  bar.className = "md-actions";

  var copy = document.createElement("button");
  copy.type = "button";
  copy.className = "md-action";
  copy.textContent = "Copy as Markdown";
  copy.addEventListener("click", function () {
    fetch(mdUrl)
      .then(function (r) {
        return r.text();
      })
      .then(function (text) {
        return navigator.clipboard.writeText(text);
      })
      .then(function () {
        copy.textContent = "Copied ✓";
        setTimeout(function () {
          copy.textContent = "Copy as Markdown";
        }, 1600);
      })
      .catch(function () {
        copy.textContent = "Copy failed";
      });
  });

  var view = document.createElement("a");
  view.className = "md-action";
  view.href = mdUrl;
  view.textContent = "View as Markdown";

  var claude = document.createElement("a");
  claude.className = "md-action";
  claude.target = "_blank";
  claude.rel = "noopener";
  claude.href =
    "https://claude.ai/new?q=" +
    encodeURIComponent("Read " + location.origin + mdUrl + " and help me use model-ledger.");
  claude.textContent = "Open in Claude";

  bar.appendChild(copy);
  bar.appendChild(view);
  bar.appendChild(claude);
  h1.insertAdjacentElement("afterend", bar);
});
