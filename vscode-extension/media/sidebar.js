const vscode = acquireVsCodeApi();

const content = document.getElementById("content");
const verifyButton = document.getElementById("verify-button");
const serverStatus = document.getElementById("server-status");
const cmdFeed = document.getElementById("cmd-feed");
const cmdResult = document.getElementById("cmd-result");
const checkCommandButton = document.getElementById("check-command-button");

verifyButton?.addEventListener("click", () => {
  verifyButton.disabled = true;
  verifyButton.textContent = "Verifying...";
  content.innerHTML = `
    <div class="loading">
      <div class="loading-title">Jury convening...</div>
      <div class="loading-copy">Running the 5-agent review against your current file or selection.</div>
    </div>
  `;
  vscode.postMessage({ command: "verify" });
});

checkCommandButton?.addEventListener("click", () => {
  vscode.postMessage({ command: "checkCommand" });
});

window.addEventListener("message", (event) => {
  const message = event.data;

  if (message.type === "health") {
    renderHealth(Boolean(message.healthy));
    if (!message.healthy) {
      content.innerHTML = `<div class="error">Juror server is unreachable. Run <code>juror start</code> and try again.</div>`;
    }
    return;
  }

  if (message.type === "error") {
    resetVerifyButton();
    content.innerHTML = `<div class="error">${escapeHtml(message.message)}</div>`;
    return;
  }

  if (message.type === "loading") {
    content.innerHTML = `
      <div class="loading">
        <div class="loading-title">Jury convening...</div>
        <div class="loading-copy">${escapeHtml(message.message)}</div>
      </div>
    `;
    return;
  }

  if (message.type === "verdict") {
    resetVerifyButton();
    renderVerdict(message.data);
    return;
  }

  if (message.type === "command-history") {
    renderCommandHistory(message.history || []);
    return;
  }

  if (message.type === "command-check-loading") {
    renderCommandResultLoading(message.command || "");
    return;
  }

  if (message.type === "command-check-result") {
    renderCommandResult(message.command, message.data);
    return;
  }

  if (message.type === "command-check-error") {
    renderCommandResultError(message.message || "Unable to check command.");
  }
});

function renderVerdict(data) {
  const colors = {
    APPROVED: "#7ab87a",
    FLAGGED: "#c8a040",
    BLOCKED: "#c86060"
  };
  const color = colors[data.final_verdict] || "#a89070";

  const verdictHtml = `
    <div class="verdict-banner" style="border-color:${color}; background:${color}14">
      <div class="verdict-main" style="color:${color}">${escapeHtml(data.final_verdict)}</div>
      <div class="verdict-details">${data.fail_count}/5 failed · ${(data.overall_confidence * 100).toFixed(0)}% confidence · ${data.execution_time_ms}ms</div>
    </div>
  `;

  const domainHtml = `
    <div class="domain-row">
      <div class="domain-pill">${escapeHtml((data.domain || "general").replaceAll("_", " "))}</div>
      <div class="meta-pill">5-agent jury</div>
    </div>
  `;

  const agentHtml = (data.agent_results || []).map((agent) => {
    const verdictClass = {
      PASS: "verdict-pass",
      FAIL: "verdict-fail",
      UNCERTAIN: "verdict-uncertain"
    }[agent.verdict] || "";

    const issues = (agent.issues || [])
      .slice(0, 2)
      .map((issue) => `<div class="issue">${escapeHtml(issue)}</div>`)
      .join("");

    return `
      <div class="agent">
        <div class="agent-header">
          <span class="agent-name">A${agent.agent_id} ${escapeHtml(agent.agent_name)}</span>
          <span class="${verdictClass}">${escapeHtml(agent.verdict)}</span>
        </div>
        ${issues}
      </div>
    `;
  }).join("");

  const summaryHtml = (data.issues_summary || []).length
    ? `
      <div class="issues-summary">
        <div class="issues-summary-title">Issues found</div>
        ${(data.issues_summary || []).slice(0, 4).map((issue) => `<div class="summary-line">${escapeHtml(issue)}</div>`).join("")}
      </div>
    `
    : "";

  const correctionHtml = data.final_verdict === "BLOCKED" && data.correction
    ? `
      <div class="correction">
        <div class="correction-title">Corrected output (Agent 6)</div>
        ${escapeHtml(data.correction.substring(0, 700))}
      </div>
    `
    : "";

  content.innerHTML = verdictHtml + domainHtml + agentHtml + summaryHtml + correctionHtml;
}

function renderHealth(healthy) {
  if (!serverStatus) return;
  serverStatus.className = `server-status ${healthy ? "ok" : "offline"}`;
  serverStatus.textContent = healthy ? "Server online" : "Server offline";
}

function renderCommandHistory(history) {
  if (!cmdFeed) return;
  if (!history.length) {
    cmdFeed.innerHTML = `<div class="cmd-idle">No commands intercepted yet.</div>`;
    return;
  }

  cmdFeed.innerHTML = history.map((entry) => {
    const colors = { SAFE: "#7ab87a", WARN: "#c8a040", BLOCK: "#c86060" };
    const color = colors[entry.verdict] || "#a89070";
    const reasons = parseReasons(entry.reasons);
    return `
      <div class="cmd-card">
        <div class="cmd-row">
          <span class="cmd-verdict" style="color:${color}">${escapeHtml(entry.verdict)}</span>
          <span class="cmd-source">${escapeHtml(entry.source || "unknown")}</span>
        </div>
        <div class="cmd-text">${escapeHtml(entry.command_preview || "")}</div>
        ${reasons[0] ? `<div class="cmd-reason">${escapeHtml(reasons[0])}</div>` : ""}
      </div>
    `;
  }).join("");
}

function renderCommandResultLoading(command) {
  if (!cmdResult) return;
  cmdResult.classList.remove("hidden");
  cmdResult.innerHTML = `
    <div class="cmd-result-title">Inspecting command</div>
    <div class="cmd-text">${escapeHtml(command)}</div>
    <div class="cmd-reason">Running command shield analysis...</div>
  `;
}

function renderCommandResult(command, data) {
  if (!cmdResult) return;
  const colors = { SAFE: "#7ab87a", WARN: "#c8a040", BLOCK: "#c86060" };
  const color = colors[data.verdict] || "#a89070";
  const packages = (data.packages_checked || []).map((pkg) => {
    let label = `${pkg.package} · ${pkg.ecosystem}`;
    if (!pkg.exists) {
      label += " · missing";
    } else if ((pkg.cve_count || 0) > 0) {
      label += ` · ${pkg.cve_count} CVEs`;
    }
    return `<span class="cmd-pill">${escapeHtml(label)}</span>`;
  }).join("");

  cmdResult.classList.remove("hidden");
  cmdResult.innerHTML = `
    <div class="cmd-result-title">Latest command check</div>
    <div class="cmd-row">
      <span class="cmd-verdict" style="color:${color}">${escapeHtml(data.verdict)}</span>
      <span class="cmd-meta">${Math.round((data.confidence || 0) * 100)}% confidence</span>
    </div>
    <div class="cmd-text">${escapeHtml(command)}</div>
    ${(data.reasons || []).slice(0, 3).map((reason) => `<div class="cmd-reason">${escapeHtml(reason)}</div>`).join("")}
    ${data.suggestion ? `<div class="cmd-suggestion">Safer alternative: ${escapeHtml(data.suggestion)}</div>` : ""}
    ${packages ? `<div class="cmd-packages">${packages}</div>` : ""}
  `;
}

function renderCommandResultError(message) {
  if (!cmdResult) return;
  cmdResult.classList.remove("hidden");
  cmdResult.innerHTML = `
    <div class="cmd-result-title">Command shield</div>
    <div class="cmd-reason">${escapeHtml(message)}</div>
  `;
}

function parseReasons(raw) {
  try {
    return JSON.parse(raw || "[]");
  } catch {
    return [];
  }
}

function resetVerifyButton() {
  if (!verifyButton) return;
  verifyButton.disabled = false;
  verifyButton.textContent = "Verify current file or selection";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

vscode.postMessage({ command: "refreshCommands" });
setInterval(() => {
  vscode.postMessage({ command: "refreshCommands" });
}, 5000);
