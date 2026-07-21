"use strict";

const $ = id => document.getElementById(id);
const SERVER = "https://www.toudimianban.cloud";
var _refreshTimer = null;

// ── Log ────────────────────────────────────────────────────────────
function log(msg, isError) {
  const el = $("log");
  el.style.display = "block";
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  el.innerHTML += `<div style="${isError ? "color:#e11d48" : ""}">${time} ${msg}</div>`;
  el.scrollTop = el.scrollHeight;
}

// ── Panel switching ────────────────────────────────────────────────
function showPanel(name) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  $(`panel-${name}`).classList.add("active");
}

function updateHeader(username, profileCount) {
  $("conn-status").textContent = username ? `✅ ${username} · ${profileCount || 0} 模板` : "未登录";
  $("btn-logout").style.display = username ? "" : "none";
}

async function loadProfiles(token) {
  try {
    const resp = await fetch(SERVER + "/api/autofill/extension/config", {
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }
    });
    if (!resp.ok) throw new Error("会话过期");
    const data = await resp.json();
    const profiles = data.profiles || [];
    const { selectedProfileId } = await chrome.storage.local.get(["selectedProfileId"]);
    renderProfiles(profiles, selectedProfileId);
    await chrome.storage.local.set({ profiles, aiProvider: data.ai_provider, hasAiKey: data.has_ai_key });
    return profiles;
  } catch (e) {
    throw e;
  }
}

function renderProfiles(profiles, selectedId) {
  const sel = $("profile-select");
  sel.innerHTML = profiles.map(p =>
    `<option value="${p.id}" ${p.id === selectedId ? "selected" : ""}>${escHtml(p.name)} (${Object.keys(p.fields||{}).length}字段)</option>`
  ).join("") || '<option value="">无模板</option>';
}

function escHtml(s) {
  return String(s).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[m]);
}

// ── Auto refresh ───────────────────────────────────────────────────
function startAutoRefresh(token) {
  stopAutoRefresh();
  _refreshTimer = setInterval(async () => {
    try {
      await loadProfiles(token);
    } catch (e) { /* silent */ }
  }, 5 * 60 * 1000); // every 5 minutes
}

function stopAutoRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
}

// ── Login ──────────────────────────────────────────────────────────
$("btn-login").addEventListener("click", async () => {
  const btn = $("btn-login");
  const username = $("username").value.trim();
  const password = $("password").value.trim();
  const errEl = $("login-error");

  if (!username || !password) {
    errEl.textContent = "请输入用户名和密码";
    errEl.style.display = "block";
    return;
  }
  errEl.style.display = "none";
  btn.disabled = true;
  btn.textContent = "登录中…";

  try {
    const resp = await fetch(SERVER + "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({ detail: "用户名或密码错误" }));
      throw new Error(e.detail || "登录失败");
    }
    const data = await resp.json();
    const token = data.token;

    const profiles = await loadProfiles(token);
    await chrome.storage.local.set({ token, username });
    if (profiles.length && !(await chrome.storage.local.get(["selectedProfileId"])).selectedProfileId) {
      await chrome.storage.local.set({ selectedProfileId: profiles[0].id });
    }

    $("password").value = "";
    showPanel("main");
    updateHeader(username, profiles.length);
    startAutoRefresh(token);
    log("已登录 · " + profiles.length + " 个模板");
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = "block";
  }
  btn.disabled = false;
  btn.textContent = "登 录";
});

// Enter key to login
$("password").addEventListener("keydown", e => { if (e.key === "Enter") $("btn-login").click(); });
$("username").addEventListener("keydown", e => { if (e.key === "Enter") $("password").focus(); });

// ── Logout ─────────────────────────────────────────────────────────
async function doLogout() {
  stopAutoRefresh();
  await chrome.storage.local.remove(["token", "username", "profiles", "selectedProfileId"]);
  showPanel("login");
  updateHeader("", 0);
  $("log").style.display = "none";
  $("log").innerHTML = "";
}
// expose to inline onclick
window.doLogout = doLogout;

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
window.toggleAutoDetect = function () {
  const toggle = $("toggle-auto");
  const on = !toggle.classList.contains("on");
  toggle.classList.toggle("on", on);
  chrome.storage.local.set({ autoDetect: on });
};

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
      action: "fill", profile, mode: fillMode || "full"
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
(async () => {
  const { token, username, fillMode, autoDetect, profiles, selectedProfileId } =
    await chrome.storage.local.get(["token", "username", "fillMode", "autoDetect", "profiles", "selectedProfileId"]);

  // Restore UI state
  if (fillMode) {
    document.querySelectorAll(".mode-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.mode === fillMode);
    });
  }
  if (autoDetect !== undefined) {
    $("toggle-auto").classList.toggle("on", autoDetect);
  }

  if (token && username) {
    // Already logged in — try to refresh
    showPanel("main");
    if (profiles) {
      renderProfiles(profiles, selectedProfileId);
      updateHeader(username, profiles.length);
    } else {
      updateHeader(username, 0);
    }
    $("username").value = username;
    // Refresh in background
    loadProfiles(token).then(p => {
      updateHeader(username, p.length);
    }).catch(() => {
      // Token expired, show login
      chrome.storage.local.remove(["token", "username"]);
      showPanel("login");
      updateHeader("", 0);
    });
    startAutoRefresh(token);
    // Check extension update
    chrome.runtime.sendMessage({ action: "checkUpdate" });
    setTimeout(() => {
      chrome.action.getBadgeText({}).then(text => {
        if (text === "!") log("⚠ 有新版本可用", true);
      });
    }, 2000);
  }
})();
