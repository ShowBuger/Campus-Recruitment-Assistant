"use strict";

const SERVER = "https://www.toudimianban.cloud";

// ── Server API helpers ────────────────────────────────────────────
async function apiCall(endpoint, options = {}) {
  const url = SERVER + endpoint;
  const headers = { "Content-Type": "application/json" };
  const { token } = await chrome.storage.local.get(["token"]);
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(url, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── Load config from server ───────────────────────────────────────
async function loadServerConfig() {
  try {
    const data = await apiCall("/api/autofill/extension/config");
    const profiles = data.profiles || [];
    await chrome.storage.local.set({ profiles, aiProvider: data.ai_provider, hasAiKey: data.has_ai_key });
    const { selectedProfileId } = await chrome.storage.local.get(["selectedProfileId"]);
    if (!selectedProfileId && profiles.length > 0) {
      await chrome.storage.local.set({ selectedProfileId: profiles[0].id });
    }
    return { success: true, profiles };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

// ── Message handlers ──────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "getProfileAndFill") {
    (async () => {
      const { selectedProfileId, profiles, fillMode } = await chrome.storage.local.get([
        "selectedProfileId", "profiles", "fillMode"
      ]);
      const profile = (profiles || []).find(p => p.id === selectedProfileId);
      if (!profile) { sendResponse({ error: "请先选择简历模板" }); return; }
      sendResponse({ profile, mode: fillMode || "full" });
    })();
    return true;
  }

  if (msg.action === "loadConfig") {
    loadServerConfig().then(sendResponse);
    return true;
  }

  if (msg.action === "getProfiles") {
    chrome.storage.local.get(["profiles", "selectedProfileId", "fillMode", "autoDetect",
      "aiProvider", "hasAiKey"], sendResponse);
    return true;
  }

  if (msg.action === "saveSettings") {
    chrome.storage.local.set(msg.settings).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (msg.action === "checkUpdate") {
    checkForUpdates(false);
    sendResponse({ ok: true });
    return true;
  }

  if (msg.action === "aiMatch") {
    (async () => {
      try {
        const data = await apiCall("/api/autofill/extension/match", {
          method: "POST",
          body: JSON.stringify({ fields: msg.fields, profile_id: msg.profileId })
        });
        sendResponse({ success: true, mappings: data.mappings || [] });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }
});

// ── Version check / auto-update ───────────────────────────────────
const CURRENT_VERSION = "1.0";

async function checkForUpdates(silent) {
  try {
    const resp = await fetch(SERVER + "/api/autofill/extension/version");
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.version !== CURRENT_VERSION) {
      chrome.action.setBadgeText({ text: "!" });
      chrome.action.setBadgeBackgroundColor({ color: "#e11d48" });
      if (!silent) {
        chrome.notifications.create("update", {
          type: "basic",
          iconUrl: "icons/icon128.png",
          title: "自动投递助手有新版本",
          message: `v${data.version}：${data.changelog || "点击下载更新"}`,
          buttons: [{ title: "下载更新" }],
          requireInteraction: true,
        });
      }
    } else {
      chrome.action.setBadgeText({ text: "" });
    }
  } catch (e) { /* offline, ignore */ }
}

chrome.notifications.onButtonClicked.addListener((notifId) => {
  if (notifId === "update") {
    chrome.tabs.create({ url: SERVER + "/api/autofill/extension/download" });
  }
});

// Check using chrome.alarms (reliable, survives service worker sleep)
chrome.alarms.create("version-check", { periodInMinutes: 360 }); // every 6 hours
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "version-check") checkForUpdates(false);
});

// ── On install ────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ autoDetect: true, fillMode: "full" });
  setTimeout(() => checkForUpdates(true), 5000);
});
