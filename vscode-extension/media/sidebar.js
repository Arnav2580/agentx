const vscode = acquireVsCodeApi();

const content = document.getElementById("content");
const verifyButton = document.getElementById("verify-button");

verifyButton?.addEventListener("click", () => {
  content.innerHTML = `<div class="idle">Jury convening...</div>`;
  vscode.postMessage({ command: "verify" });
});

window.addEventListener("message", (event) => {
  const message = event.data;
  if (message.type === "health") {
    if (!message.healthy) {
      content.innerHTML = `<div class="error">Juror server is unreachable. Run \`juror start\`.</div>`;
    }
    return;
  }

  if (message.type === "error") {
    content.innerHTML = `<div class="error">${message.message}</div>`;
    return;
  }

  if (message.type === "verdict") {
    renderVerdict(message.data);
  }
});

function renderVerdict(data) {
  const colors = {
    APPROVED: "#34d399",
    FLAGGED: "#fbbf24",
    BLOCKED: "#f87171"
  };
  const color = colors[data.final_verdict] || "#94a3b8";

  const verdictHtml = `
    <div class="verdict-banner" style="border-color:${color}; background:${color}14">
      <div class="verdict-main" style="color:${color}">${data.final_verdict}</div>
      <div class="verdict-details">${data.fail_count}/5 failed · ${(data.overall_confidence * 100).toFixed(0)}% confidence · ${data.execution_time_ms}ms</div>
    </div>
  `;

  const agentHtml = data.agent_results.map((agent) => {
    const verdictClass = {
      PASS: "verdict-pass",
      FAIL: "verdict-fail",
      UNCERTAIN: "verdict-uncertain"
    }[agent.verdict];

    const issues = (agent.issues || []).slice(0, 2).map((issue) => `<div class="issue">- ${escapeHtml(issue)}</div>`).join("");

    return `
      <div class="agent">
        <div class="agent-header">
          <span class="agent-name">A${agent.agent_id} ${escapeHtml(agent.agent_name)}</span>
          <span class="${verdictClass}">${agent.verdict}</span>
        </div>
        ${issues}
      </div>
    `;
  }).join("");

  const correctionHtml = data.final_verdict === "BLOCKED" && data.correction
    ? `<div class="correction">${escapeHtml(data.correction.substring(0, 700))}</div>`
    : "";

  content.innerHTML = verdictHtml + agentHtml + correctionHtml;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
