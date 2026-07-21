/* content.js — 校招自动投递助手 · 内容脚本
   Injected into every page. Handles field detection, rule-based matching, and filling. */

(function () {
  "use strict";

  // ── Field alias table (same as server) ─────────────────────────────
  const FIELD_ALIASES = {
    "姓名": ["name","姓名","fullname","your-name","realname","真实姓名","中文姓名"],
    "邮箱": ["email","邮箱","电子邮箱","e-mail","mail","email_address","联系邮箱"],
    "手机": ["phone","手机","电话","mobile","tel","telephone","联系电话","手机号码"],
    "性别": ["gender","sex","性别"],
    "出生日期": ["birthday","birth","出生日期","出生年月","birthdate","date_of_birth"],
    "民族": ["ethnicity","nation","民族","ethnic"],
    "政治面貌": ["political","政治面貌","politics","party","党员","团员"],
    "学校": ["school","学校","毕业学校","毕业院校","university","college","院校"],
    "专业": ["major","专业","specialty","speciality","所学专业","discipline"],
    "学历": ["education","degree","学历","最高学历","edu","education_level"],
    "毕业时间": ["graduation","毕业时间","graduation_date","graduate_date","预计毕业"],
    "英语水平": ["english","英语水平","英语等级","english_level","cet","toefl","ielts","外语水平"],
    "实习经历": ["internship","实习经历","实习","intern","intern_experience","工作经历"],
    "项目经历": ["project","项目经历","项目经验","project_experience","projects"],
    "技能": ["skills","skill","技能","专业技能","技术栈","tech_skills"],
    "获奖情况": ["awards","award","获奖","获奖情况","荣誉","honors","achievements"],
    "自我评价": ["self_evaluation","self_intro","自我介绍","个人简介","个人介绍","summary","bio"],
    "期望城市": ["city","城市","期望城市","工作城市","location","preferred_city"],
    "期望薪资": ["salary","薪资","期望薪资","expected_salary","salary_range","薪酬"],
    "最快到岗": ["availability","到岗时间","最快到岗","入职时间","available_date"],
    "GitHub": ["github","gitlab","gitee","博客","blog","website","portfolio","个人网站"]
  };

  // ── Field collection ───────────────────────────────────────────────
  function collectFields() {
    const fields = [];
    const seen = new Set();
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]):not([type="file"]), textarea, select'
    );
    inputs.forEach(el => {
      const name = (el.name || "").trim();
      const id = (el.id || "").trim();
      let label = "";
      let lbl = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
      if (!lbl && el.closest) {
        const row = el.closest("label") || el.closest(".form-item") || el.closest(".form-group") ||
                    el.closest("tr") || el.closest(".el-form-item") || el.closest(".ant-form-item") ||
                    el.closest("div");
        if (row) lbl = row.querySelector("label, .label, .title");
      }
      if (lbl) label = (lbl.textContent || "").replace(/\s+/g, " ").trim();
      const key = `${name}|${id}|${label}`;
      if (seen.has(key)) return;
      seen.add(key);

      const options = [];
      if (el.tagName === "SELECT") {
        Array.from(el.options).forEach(o => {
          if (o.value) options.push({ value: o.value, text: (o.textContent || "").trim() });
        });
      }

      fields.push({
        name, id,
        type: el.type || el.tagName.toLowerCase(),
        label,
        placeholder: (el.placeholder || "").trim(),
        required: el.required || el.getAttribute("aria-required") === "true",
        options: options.slice(0, 50),
        tagName: el.tagName,
        _el: el  // direct reference for filling
      });
    });
    return fields;
  }

  // ── Rule-based field matching ──────────────────────────────────────
  function matchFields(fields, profileFields) {
    const fills = [];
    fields.forEach((f, idx) => {
      const label = (f.label || "").toLowerCase();
      const name = (f.name || "").toLowerCase();
      const uid = (f.id || "").toLowerCase();
      const ph = (f.placeholder || "").toLowerCase();
      let bestField = null, bestScore = 0;
      for (const [pk, aliases] of Object.entries(FIELD_ALIASES)) {
        if (!profileFields[pk]) continue;
        for (const alias of aliases) {
          const a = alias.toLowerCase();
          let score = 0;
          if (a === name) score = 95;
          else if (label.includes(a)) score = 90;
          else if (a === uid) score = 80;
          else if (name.includes(a)) score = 75;
          else if (uid.includes(a)) score = 70;
          else if (ph.includes(a)) score = 60;
          else continue;
          if (score > bestScore) { bestScore = score; bestField = pk; }
        }
      }
      if (bestField && bestScore >= 60) {
        fills.push({ pageFieldIndex: idx, profileField: bestField, value: profileFields[bestField], confidence: bestScore });
      }
    });
    return fills;
  }

  // ── Field filling ──────────────────────────────────────────────────
  function fillField(f, value) {
    if (!value) return false;
    const el = f._el;
    if (!el || !document.contains(el)) return false;
    try {
      if (el.tagName === "SELECT") {
        const v = value.toLowerCase().trim();
        let best = null;
        Array.from(el.options).forEach(o => {
          const ot = (o.textContent || "").trim().toLowerCase();
          const ov = (o.value || "").toLowerCase();
          if (ot === v || ov === v) best = o.value;
        });
        if (!best) {
          Array.from(el.options).forEach(o => {
            const ot = (o.textContent || "").trim().toLowerCase();
            if (ot.includes(v) || v.includes(ot)) best = o.value;
          });
        }
        if (best) { el.value = best; el.dispatchEvent(new Event("change", { bubbles: true })); return true; }
        return false;
      }
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value") ||
                     Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
      if (setter && setter.set) setter.set.call(el, value);
      else el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      // Also trigger for Vue/React
      el.dispatchEvent(new Event("compositionend", { bubbles: true }));
      return true;
    } catch (e) {
      try { el.value = value; el.dispatchEvent(new Event("change", { bubbles: true })); return true; }
      catch (e2) { return false; }
    }
  }

  function normalizeValue(profileField, value, fieldInfo) {
    if (fieldInfo.type === "select-one" || fieldInfo.options?.length) {
      const v = value.trim().toLowerCase();
      for (const o of fieldInfo.options) {
        if (o.text.toLowerCase() === v || o.value.toLowerCase() === v) return o.value || o.text;
      }
      for (const o of fieldInfo.options) {
        if (o.text.toLowerCase().includes(v) || v.includes(o.text.toLowerCase())) return o.value || o.text;
      }
      return value;
    }
    return value;
  }

  function executeFill(fields, profileFields, mode) {
    const fills = matchFields(fields, profileFields);
    const results = { total: fills.length, succeeded: 0, details: [] };
    fills.forEach(m => {
      const f = fields[m.pageFieldIndex];
      const val = normalizeValue(m.profileField, m.value, f);
      if (mode === "incremental" && f._el && f._el.value && f._el.value.trim()) {
        // Incremental: skip already-filled fields
        results.details.push({ field: m.profileField, filled: false, reason: "已填写，跳过" });
        return;
      }
      const ok = fillField(f, val);
      if (ok) results.succeeded++;
      results.details.push({ field: m.profileField, filled: ok, label: f.label || f.name || f.id });
    });
    return results;
  }

  // ── Auto-detect: show banner when forms are detected ──────────────
  let bannerEl = null;
  function showBanner(fieldCount) {
    if (bannerEl) return;
    bannerEl = document.createElement("div");
    bannerEl.id = "__af_banner";
    bannerEl.innerHTML = `<div style="
      position:fixed;top:10px;right:10px;z-index:2147483647;
      background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;
      padding:8px 14px;border-radius:12px;font:13px/1.4 -apple-system,BlinkMacSystemFont,sans-serif;
      box-shadow:0 4px 20px rgba(37,99,235,.4);cursor:pointer;display:flex;align-items:center;gap:8px;
    ">
      <span>📋 检测到 ${fieldCount} 个表单字段</span>
      <span style="background:rgba(255,255,255,.2);padding:2px 8px;border-radius:6px;font-size:11px">点击填充</span>
    </div>`;
    bannerEl.onclick = () => { bannerEl.remove(); bannerEl = null; triggerFill(); };
    document.body.appendChild(bannerEl);
  }

  function triggerFill() {
    chrome.runtime.sendMessage({ action: "getProfileAndFill" }, response => {
      if (!response || !response.profile) {
        showToast("请先在扩展设置中选择简历模板");
        return;
      }
      const fields = collectFields();
      if (!fields.length) {
        showToast("未检测到表单字段");
        return;
      }
      const result = executeFill(fields, response.profile.fields, response.mode || "full");
      showToast(`已填充 ${result.succeeded}/${result.total} 个字段`);
    });
  }

  function showToast(msg) {
    const el = document.createElement("div");
    el.textContent = msg;
    Object.assign(el.style, {
      position: "fixed", bottom: "20px", left: "50%", transform: "translateX(-50%)",
      zIndex: "2147483647", background: "#111", color: "#fff",
      padding: "10px 20px", borderRadius: "20px", fontSize: "13px",
      fontFamily: "-apple-system,BlinkMacSystemFont,sans-serif",
      boxShadow: "0 4px 16px rgba(0,0,0,.3)", transition: "opacity .3s",
    });
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 2500);
  }

  // ── Listen for messages from popup ──────────────────────────────
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "collectFields") {
      sendResponse({ fields: collectFields().map(f => {
        const { _el, ...rest } = f; return rest;
      }), count: 0, url: location.href, title: document.title });
    }
    if (msg.action === "fill") {
      const fields = collectFields();
      const result = executeFill(fields, msg.profile.fields, msg.mode || "full");
      sendResponse(result);
    }
  });

  // ── Watch for SPA forms (MutationObserver) ──────────────────────
  let bannerShown = false;
  const observer = new MutationObserver(() => {
    if (bannerShown) return;
    const fields = collectFields();
    if (fields.length >= 3) {
      bannerShown = true;
      setTimeout(() => {
        chrome.storage.local.get(["autoDetect"], data => {
          if (data.autoDetect !== false) showBanner(fields.length);
        });
      }, 1500);
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  // Delayed initial check
  setTimeout(() => {
    const fields = collectFields();
    if (fields.length >= 3 && !bannerShown) {
      bannerShown = true;
      chrome.storage.local.get(["autoDetect"], data => {
        if (data.autoDetect !== false) showBanner(fields.length);
      });
    }
  }, 2000);
})();
