const JUROR_URL = "http://localhost:8000";

async function checkServer() {
  const element = document.getElementById("status");
  try {
    const response = await fetch(`${JUROR_URL}/health`, { signal: AbortSignal.timeout(3000) });
    const data = await response.json();
    element.className = "status ok";
    element.textContent = `✓ Running · ${data.model}`;
  } catch {
    element.className = "status err";
    element.textContent = "✗ Offline\nRun: juror start";
  }
}

async function sendToTab(type) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) chrome.tabs.sendMessage(tab.id, { type });
  window.close();
}

document.getElementById("btn-scan").onclick = () => sendToTab("MANUAL_VERIFY");
document.getElementById("btn-sel").onclick = () => sendToTab("VERIFY_SELECTED_TEXT");
document.getElementById("btn-dash").onclick = () => {
  chrome.tabs.create({ url: `${JUROR_URL}` });
};

checkServer();
