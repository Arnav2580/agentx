(function () {
  function ensureSidebar() {
    if (document.getElementById("juror-sidebar")) {
      return document.getElementById("juror-sidebar");
    }

    const sidebar = document.createElement("aside");
    sidebar.id = "juror-sidebar";
    sidebar.innerHTML = `
      <div class="juror-header">
        <div class="juror-brand">
          <span class="juror-logo">⬡</span>
          <span class="juror-title">AI HALLUCINATION JUROR</span>
        </div>
        <button id="juror-close" class="juror-close" aria-label="Hide juror sidebar">×</button>
      </div>
      <div id="juror-status" class="juror-status">
        <div class="juror-idle">Monitoring AI responses...</div>
      </div>
      <div id="juror-agents" class="juror-agents"></div>
      <div id="juror-verdict" class="juror-verdict" hidden></div>
      <div id="juror-correction" class="juror-correction" hidden></div>
      <div class="juror-history">
        <div class="juror-history-title">RECENT VERDICTS</div>
        <div id="juror-history-list"></div>
      </div>
    `;

    document.body.appendChild(sidebar);
    sidebar.querySelector("#juror-close")?.addEventListener("click", () => {
      sidebar.style.display = "none";
      chrome.storage.local.set({ jurorSidebarVisible: false });
    });

    return sidebar;
  }

  function showSidebar() {
    const sidebar = ensureSidebar();
    sidebar.style.display = "flex";
    chrome.storage.local.set({ jurorSidebarVisible: true });
  }

  function renderLoading() {
    showSidebar();
    const status = document.getElementById("juror-status");
    const agents = document.getElementById("juror-agents");
    const verdict = document.getElementById("juror-verdict");
    const correction = document.getElementById("juror-correction");
    if (!status || !agents || !verdict || !correction) {
      return;
    }

    status.innerHTML = `<div class="juror-loading">Jury convening... running 5 agents in parallel</div>`;
    agents.innerHTML = [
      "Fact Verifier",
      "Math Validator",
      "Standards Checker",
      "Logic Auditor",
      "Domain Expert"
    ].map((name, index) => `
      <div class="juror-agent firing">
        <div class="agent-header">
          <span class="agent-name">A${index + 1} ${name}</span>
          <span class="agent-status">...</span>
        </div>
      </div>
    `).join("");
    verdict.hidden = true;
    correction.hidden = true;
  }

  function renderError(message) {
    showSidebar();
    const status = document.getElementById("juror-status");
    if (status) {
      status.innerHTML = `<div class="juror-error">${message}</div>`;
    }
  }

  function renderVerdict(data) {
    showSidebar();
    const status = document.getElementById("juror-status");
    const agents = document.getElementById("juror-agents");
    const verdict = document.getElementById("juror-verdict");
    const correction = document.getElementById("juror-correction");

    if (!status || !agents || !verdict || !correction) {
      return;
    }

    const colors = {
      APPROVED: "#34d399",
      FLAGGED: "#fbbf24",
      BLOCKED: "#f87171"
    };
    const color = colors[data.final_verdict] || "#94a3b8";

    status.innerHTML = `<div class="juror-complete" style="color:${color}">Verification complete</div>`;

    agents.innerHTML = data.agent_results.map((agent) => {
      const verdictClass = agent.verdict === "PASS" ? "pass" : agent.verdict === "FAIL" ? "fail" : "uncertain";
      const issues = (agent.issues || []).slice(0, 2).map((issue) => `<div class="agent-issue">- ${escapeHtml(issue)}</div>`).join("");

      return `
        <div class="juror-agent ${verdictClass}">
          <div class="agent-header">
            <span class="agent-name">A${agent.agent_id} ${escapeHtml(agent.agent_name)}</span>
            <span class="agent-verdict">${agent.verdict}</span>
          </div>
          ${issues}
        </div>
      `;
    }).join("");

    verdict.hidden = false;
    verdict.innerHTML = `
      <div class="verdict-banner" style="border-color:${color}; background:${color}14">
        <div class="verdict-main" style="color:${color}">${data.final_verdict}</div>
        <div class="verdict-details">${data.fail_count}/5 agents failed · ${(data.overall_confidence * 100).toFixed(0)}% confidence · ${data.execution_time_ms}ms</div>
      </div>
    `;

    if (data.final_verdict === "BLOCKED" && data.correction) {
      correction.hidden = false;
      correction.dataset.correction = data.correction;
      correction.innerHTML = `
        <div class="correction-header">CORRECTED OUTPUT (Agent 6)</div>
        <div class="correction-content">${escapeHtml(data.correction.substring(0, 800))}</div>
        <button class="copy-correction" type="button">Copy correction</button>
      `;
      correction.querySelector(".copy-correction")?.addEventListener("click", async (event) => {
        await navigator.clipboard.writeText(correction.dataset.correction || "");
        if (event.currentTarget instanceof HTMLButtonElement) {
          event.currentTarget.textContent = "Copied";
          setTimeout(() => {
            event.currentTarget.textContent = "Copy correction";
          }, 1500);
        }
      });
    } else {
      correction.hidden = true;
      correction.innerHTML = "";
    }
  }

  function addHistoryEntry(data) {
    const list = document.getElementById("juror-history-list");
    if (!list) {
      return;
    }
    const entry = document.createElement("div");
    entry.className = "history-item";
    entry.textContent = `${data.final_verdict} · ${data.domain}`;
    list.prepend(entry);
  }

  function setHistory(items) {
    const list = document.getElementById("juror-history-list");
    if (!list) {
      return;
    }
    list.innerHTML = items.map((item) => `<div class="history-item">${escapeHtml(`${item.final_verdict} · ${item.domain}`)}</div>`).join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  window.JurorSidebar = {
    ensureSidebar,
    showSidebar,
    renderLoading,
    renderError,
    renderVerdict,
    addHistoryEntry,
    setHistory
  };
})();
