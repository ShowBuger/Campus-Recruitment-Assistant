"use strict";

const $ = id => document.getElementById(id);

// ── Log ────────────────────────────────────────────────────────────
function log(msg, isError) {
  const el = $("log");
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  el.innerHTML += `<div style="${isError ? "color:#e11d48" : ""}">${time} ${msg}</div>`;
  el.scrollTop = el.scrollHeight;
}

// ── Load saved state ──────────────────────────────────────────────
async function loadState() {
  const data = await chrome.storage.local.get([
    "serverUrl", "username", "token", "profiles", "selectedProfileId", "fillMode", "autoDetect"
  ]);
  $("server-url").value = data.serverUrl || "https://www.toudimianban.cloud";
  if (data.username) $("username").value = data.username;
  if (data.profiles) {
    renderProfiles(data.profiles, data.selectedProfileId);
    updateConnectionStatus(true, data.username, data.profiles.length);
  } else if (data.token) {
    // Already logged in from before, try to refresh
    $("btn-connect").textContent = "刷新";
    updateConnectionStatus(true, data.username || "已登录");
  }
  if (data.fillMode) {
    document.querySelectorAll(".mode-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.mode === data.fillMode);
    });
  }
  if (data.autoDetect !== undefined) {
    $("toggle-auto").classList.toggle("on", data.autoDetect);
  }
}

function renderProfiles(profiles, selectedId) {
  const sel = $("profile-select");
  sel.innerHTML = profiles.map(p =>
    `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${escHtml(p.name)} (${Object.keys(p.fields||{}).length}字段)</option>`
  ).join("") || '<option value="">无模板</option>';
}

function updateConnectionStatus(ok, username, profileCount) {
  const el = $("conn-status");
  if (ok) {
    el.innerHTML = `✅ ${escHtml(username || "")} · ${profileCount || 0} 个模板`;
  } else {
    el.innerHTML = "⚠ 未登录";
  }
}

function escHtml(s) {
  return String(s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[m]);
}

// ── Connect / Login ────────────────────────────────────────────────
$("btn-connect").addEventListener("click", async () => {
  const btn = $("btn-connect");
  btn.disabled = true;
  btn.textContent = "登录中…";
  const serverUrl = $("server-url").value.trim();
  const username = $("username").value.trim();
  const password = $("password").value.trim();
  if (!serverUrl) { log("请输入服务器地址", true); btn.disabled = false; btn.textContent = "登录"; return; }
  if (!username || !password) { log("请输入用户名和密码", true); btn.disabled = false; btn.textContent = "登录"; return; }

  try {
    // Step 1: Login to get token
    const loginResp = await fetch(serverUrl + "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!loginResp.ok) {
      const err = await loginResp.json().catch(() => ({ detail: "用户名或密码错误" }));
      throw new Error(err.detail || "登录失败");
    }
    const loginData = await loginResp.json();
    const token = loginData.token;

    // Step 2: Fetch profiles
    const configResp = await fetch(serverUrl + "/api/autofill/extension/config", {
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }
    });
    if (!configResp.ok) throw new Error("获取配置失败");
    const data = await configResp.json();
    const profiles = data.profiles || [];

    await chrome.storage.local.set({
      serverUrl, token, username,
      profiles, aiProvider: data.ai_provider, hasAiKey: data.has_ai_key,
      selectedProfileId: profiles[0]?.id || ""
    });
    $("password").value = "";
    renderProfiles(profiles, profiles[0]?.id);
    updateConnectionStatus(true, username, profiles.length);
    log(`已登录 · ${profiles.length} 个模板`);
    btn.textContent = "刷新";
  } catch (e) {
    updateConnectionStatus(false);
    log("登录失败: " + e.message, true);
    btn.textContent = "登录";
  }
  btn.disabled = false;
});

// ── Profile selection ─────────────────────────────────────────────
$("profile-select").addEventListener("change", async () => {
  await chrome.storage.local.set({ selectedProfileId: $("profile-select").value });
});

// ── Fill mode ─────────────────────────────────────────────────────
document.querySelectorAll(".mode-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    await chrome.storage.local.set({ fillMode: btn.dataset.mode });
  });
});

// ── Auto detect toggle ────────────────────────────────────────────
function toggleAutoDetect() {
  const toggle = $("toggle-auto");
  const on = !toggle.classList.contains("on");
  toggle.classList.toggle("on", on);
  chrome.storage.local.set({ autoDetect: on });
}

// ── Fill button ───────────────────────────────────────────────────
$("btn-fill").addEventListener("click", async () => {
  const btn = $("btn-fill");
  btn.disabled = true;
  btn.textContent = "填充中…";

  const { profiles, selectedProfileId, fillMode } = await chrome.storage.local.get([
    "profiles", "selectedProfileId", "fillMode"
  ]);
  const profile = (profiles || []).find(p => p.id === selectedProfileId);
  if (!profile) { log("请先选择简历模板", true); btn.disabled = false; btn.textContent = "🚀 立即填充"; return; }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) { log("无法获取当前标签页", true); btn.disabled = false; btn.textContent = "🚀 立即填充"; return; }

  try {
    const result = await chrome.tabs.sendMessage(tab.id, {
      action: "fill",
      profile,
      mode: fillMode || "full"
    });
    if (result) {
      log(`已填充 ${result.succeeded}/${result.total} 字段`);
      result.details?.forEach(d => {
        if (d.filled) log(`  ✓ ${d.field} → ${d.label || ""}`, false);
        else log(`  ✗ ${d.field} → ${d.reason || "未匹配"}`, true);
      });
    }
  } catch (e) {
    log("填充失败: " + e.message, true);
  }
  btn.disabled = false;
  btn.textContent = "🚀 立即填充";
});

// ── Detect button ─────────────────────────────────────────────────
$("btn-detect").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  try {
    const result = await chrome.tabs.sendMessage(tab.id, { action: "collectFields" });
    if (result?.fields) {
      log(`检测到 ${result.fields.length} 个表单字段`);
      result.fields.slice(0, 10).forEach(f => {
        log(`  ${f.tagName}[${f.type}] ${f.label || f.name || f.id || "(未知)"}`);
      });
      if (result.fields.length > 10) log(`  ... 还有 ${result.fields.length - 10} 个`);
    }
  } catch (e) {
    log("请刷新页面后重试", true);
  }
});

// ── Init ──────────────────────────────────────────────────────────
loadState();
