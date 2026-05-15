chrome.runtime.onInstalled.addListener(() => {
  console.log("AI Hallucination Juror installed - works on any AI site");
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "VERIFY_FROM_POPUP") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "MANUAL_VERIFY" }, sendResponse);
      }
    });
    return true;
  }
  if (message.type === "VERIFY_SELECTION") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "VERIFY_SELECTED_TEXT" }, sendResponse);
      }
    });
    return true;
  }
});
