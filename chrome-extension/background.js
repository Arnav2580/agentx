chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ jurorSidebarVisible: true });
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) {
    return;
  }
  chrome.tabs.sendMessage(tab.id, { type: "juror.toggleSidebar" });
});
