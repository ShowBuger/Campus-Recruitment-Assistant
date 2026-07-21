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
    "serverUrl", "token", "profiles", "selectedProfileId", "fillMode", "autoDetect"
  ]);
  if (data.serverUrl) $("server-url").value = data.serverUrl;
  if (data.token) $("token").value = data.token;
  if (data.profiles) {
    renderProfiles(data.profiles, data.selectedProfileId);
    updateConnectionStatus(true, data.profiles.length);
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

function updateConnectionStatus(ok, profileCount) {
  const el = $("conn-status");
  if (ok) {
    el.innerHTML = `✅ 已连接 · ${profileCount || 0} 个模板`;
  } else {
    el.innerHTML = "⚠ 未连接服务器";
  }
}

function escHtml(s) {
  return String(s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[m]);
}

// ── Connect to server ─────────────────────────────────────────────
$("btn-connect").addEventListener("click", async () => {
  const btn = $("btn-connect");
  btn.disabled = true;
  btn.textContent = "连接中…";
  const serverUrl = $("server-url").value.trim();
  const token = $("token").value.trim();
  if (!serverUrl) { log("请输入服务器地址", true); btn.disabled = false; btn.textContent = "连接"; return; }

  await chrome.storage.local.set({ serverUrl, token });

  try {
    const base = serverUrl;
    const resp = await fetch(base + "/api/autofill/extension/config", {
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
      throw new Error(err.detail || "认证失败");
    }
    const data = await resp.json();
    const profiles = data.profiles || [];
    await chrome.storage.local.set({
      profiles, aiProvider: data.ai_provider, hasAiKey: data.has_aiKey,
      selectedProfileId: profiles[0]?.id || ""
    });
    renderProfiles(profiles, profiles[0]?.id);
    updateConnectionStatus(true, profiles.length);
    log(`已连接 · ${profiles.length} 个模板`);
  } catch (e) {
    updateConnectionStatus(false);
    log("连接失败: " + e.message, true);
  }
  btn.disabled = false;
  btn.textContent = "连接";
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
