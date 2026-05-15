async function checkServer() {
  const status = document.getElementById("status");
  try {
    const response = await fetch("http://localhost:8000/health");
    if (!response.ok) {
      throw new Error("unhealthy");
    }
    status.textContent = "Backend connected";
    status.dataset.state = "ok";
  } catch {
    status.textContent = "Backend offline - run juror start";
    status.dataset.state = "error";
  }
}

document.getElementById("toggle-sidebar")?.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    await chrome.tabs.sendMessage(tab.id, { type: "juror.toggleSidebar" });
  }
});

void checkServer();
