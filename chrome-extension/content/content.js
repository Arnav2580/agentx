const JUROR_URL = "http://localhost:8000";

const SITE_CONFIG = {
  "claude.ai": {
    responseSelector: '[data-is-streaming="false"] .font-claude-message',
    streamEndSignal: '[data-is-streaming="false"]'
  },
  "chat.openai.com": {
    responseSelector: '[data-message-author-role="assistant"] .markdown',
    streamEndSignal: 'button[aria-label="Copy"]'
  },
  "chatgpt.com": {
    responseSelector: '[data-message-author-role="assistant"] .markdown',
    streamEndSignal: 'button[aria-label="Copy"]'
  },
  "gemini.google.com": {
    responseSelector: '.response-content',
    streamEndSignal: '.copy-button'
  },
  "copilot.microsoft.com": {
    responseSelector: '.ac-textBlock',
    streamEndSignal: '.copy-btn'
  }
};

let isVerifying = false;
let lastVerifiedContent = "";

function getSiteConfig() {
  const hostname = window.location.hostname;
  return Object.entries(SITE_CONFIG).find(([key]) => hostname.includes(key))?.[1];
}

async function verifyContent(content) {
  if (isVerifying) {
    return;
  }
  isVerifying = true;
  window.JurorSidebar.renderLoading();

  try {
    const response = await fetch(`${JUROR_URL}/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        content: content.substring(0, 8000),
        source: "chrome"
      })
    });

    if (!response.ok) {
      throw new Error(`Juror server error: ${response.status}`);
    }

    const data = await response.json();
    window.JurorSidebar.renderVerdict(data);
    window.JurorSidebar.addHistoryEntry(data);
  } catch (error) {
    window.JurorSidebar.renderError("Cannot connect to Juror server. Run `juror start`.");
  } finally {
    isVerifying = false;
  }
}

function monitorResponses() {
  const config = getSiteConfig();
  if (!config) {
    return;
  }

  const observer = new MutationObserver(() => {
    if (isVerifying) {
      return;
    }

    const responses = document.querySelectorAll(config.responseSelector);
    if (!responses.length) {
      return;
    }

    const latest = responses[responses.length - 1];
    const content = latest.textContent?.trim();
    if (!content || content.length < 50 || content === lastVerifiedContent) {
      return;
    }

    const streamSignals = document.querySelectorAll(config.streamEndSignal);
    if (!streamSignals.length) {
      return;
    }

    lastVerifiedContent = content;
    void verifyContent(content);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });
}

async function loadHistory() {
  try {
    const response = await fetch(`${JUROR_URL}/history?limit=5`);
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    window.JurorSidebar.setHistory(data.history || []);
  } catch {
    return;
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "juror.toggleSidebar") {
    const sidebar = document.getElementById("juror-sidebar");
    if (!sidebar || sidebar.style.display === "none") {
      window.JurorSidebar.showSidebar();
    } else {
      sidebar.style.display = "none";
      chrome.storage.local.set({ jurorSidebarVisible: false });
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "j") {
    const selector = getSiteConfig()?.responseSelector;
    if (!selector) {
      return;
    }
    const responses = document.querySelectorAll(selector);
    const latest = responses[responses.length - 1];
    const content = latest?.textContent?.trim();
    if (content) {
      void verifyContent(content);
    }
  }
});

window.JurorSidebar.ensureSidebar();
chrome.storage.local.get(["jurorSidebarVisible"], ({ jurorSidebarVisible }) => {
  if (jurorSidebarVisible === false) {
    const sidebar = document.getElementById("juror-sidebar");
    if (sidebar) {
      sidebar.style.display = "none";
    }
  }
});
void loadHistory();
monitorResponses();
