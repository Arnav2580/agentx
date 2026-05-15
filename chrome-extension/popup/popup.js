const JUROR_URL = "http://localhost:8000";

async function checkServer() {
  const status = document.getElementById("status");
  try {
    const response = await fetch(`${JUROR_URL}/health`, { signal: AbortSignal.timeout(3000) });
    const data = await response.json();
    status.className = "status ok";
    status.textContent = `Server online\n${data.model}`;
  } catch (_) {
    status.className = "status err";
    status.textContent = "Server offline\nRun: juror start";
  }
}

async function sendToTab(type) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    chrome.tabs.sendMessage(tab.id, { type });
  }
  window.close();
}

document.getElementById("btn-scan").addEventListener("click", () => sendToTab("MANUAL_VERIFY"));
document.getElementById("btn-sel").addEventListener("click", () => sendToTab("VERIFY_SELECTED_TEXT"));
document.getElementById("btn-dash").addEventListener("click", () => {
  chrome.tabs.create({ url: JUROR_URL });
});

void checkServer();
