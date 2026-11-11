const copy = {
  zh: {
    eyebrow: "本地运行 · 无需编程",
    title: "粘贴链接，说出你想要的数据",
    subtitle: "Lioran 会理解公开网页，并把你需要的信息整理成表格。",
    formTitle: "开始提取",
    urlLabel: "网页链接",
    requirementLabel: "你想提取什么？",
    start: "开始抓取",
    clarifyFirst: "先问清楚",
    clarifyHint: "政策法规先逐项问清，全部由你拍板。这一步只生成规格，不会开始抓取。",
    specLocked: "规格已锁定，抓取还没开始。再点一次才会走现有抓取。",
    loading: "AI 正在看懂页面...",
    maxPagesLabel: "最大页数",
    crawlLimitHint: "同域名 · 最多 3 层 · 5 个并发",
    stop: "停止",
    stopping: "正在停止当前任务...",
    preparing: "正在准备",
    pagesCrawled: "页面",
    sectionsCrawled: "栏目",
    rowsFound: "条数据",
    crawlSummary: "已抓取 {pages} 页、发现 {sections} 个栏目",
    stoppedSummary: "已停止 · 已抓取 {pages} 页、发现 {sections} 个栏目",
    mapping: "正在整理字段和合并结果...",
    resultsEyebrow: "提取结果",
    totalPrefix: "共抓到",
    totalSuffix: "条",
    download: "下载 Excel",
    retry: "重新抓取",
    rowHint: "点选一行可以告诉 Lioran 哪条记录才是正确结果。",
    disclaimer: "仅用于公开数据，请遵守目标网站条款与当地法律法规。",
    placeholderUrl: "https://example.com/news",
    placeholderRequirement: "例如：我要序号、标题、链接、时间、摘要、栏目名称和类别",
    working: "正在读取网页并生成表格，请稍候...",
    feedback: "正在根据你选择的行重新识别...",
    failed: "暂时无法完成，请检查链接后重试。",
    downloadError: "下载失败，请重新抓取后再试。",
    language: "中 / EN",
  },
  en: {
    eyebrow: "Runs locally · No coding required",
    title: "Paste a link. Tell us what data you need.",
    subtitle: "Lioran understands public web pages and organizes the information into a table.",
    formTitle: "Start extracting",
    urlLabel: "Web page URL",
    requirementLabel: "What would you like to extract?",
    start: "Start scraping",
    clarifyFirst: "Clarify first",
    clarifyHint: "Policy documents are confirmed item by item, in Chinese. This step only writes a specification and does not start a scrape.",
    specLocked: "Specification locked. Scraping has not started. Click again to run the existing scrape.",
    loading: "AI is understanding the page...",
    maxPagesLabel: "Maximum pages",
    crawlLimitHint: "Same host · up to 3 levels · 5 concurrent pages",
    stop: "Stop",
    stopping: "Stopping the current crawl...",
    preparing: "Preparing",
    pagesCrawled: "pages",
    sectionsCrawled: "sections",
    rowsFound: "records",
    crawlSummary: "Crawled {pages} pages and found {sections} sections",
    stoppedSummary: "Stopped · crawled {pages} pages and found {sections} sections",
    mapping: "Mapping fields and merging results...",
    resultsEyebrow: "Results",
    totalPrefix: "Found",
    totalSuffix: "items",
    download: "Download Excel",
    retry: "Scrape again",
    rowHint: "Select a row to tell Lioran which record is correct.",
    disclaimer: "For public data only. Follow the target website's terms and applicable laws.",
    placeholderUrl: "https://example.com/news",
    placeholderRequirement: "For example: title, publish date, and link",
    working: "Reading the page and building your table...",
    feedback: "Re-checking the page based on your selected row...",
    failed: "Unable to complete the request. Check the URL and try again.",
    downloadError: "Download failed. Please scrape the page again.",
    language: "中 / EN",
  },
};

const form = document.querySelector("#scrape-form");
const submitButton = document.querySelector("#submit-button");
const buttonLabel = document.querySelector("#button-label");
const spinner = document.querySelector("#spinner");
const statusMessage = document.querySelector("#status-message");
const stopButton = document.querySelector("#stop-button");
const progressPanel = document.querySelector("#progress-panel");
const progressBar = document.querySelector(".progress-track");
const progressFill = document.querySelector("#progress-fill");
const progressPercent = document.querySelector("#progress-percent");
const progressSection = document.querySelector("#progress-section");
const errorPanel = document.querySelector("#error-panel");
const errorMessage = document.querySelector("#error-message");
const resultsPanel = document.querySelector("#results-panel");
const table = document.querySelector("#results-table");
const langButton = document.querySelector("#language-toggle");
let language = "zh";
let activeTaskId = null;
let activeCrawlId = null;
let requestInProgress = false;

function t(key) {
  return copy[language][key];
}

const CLARIFY_SPEC_KEY = "lioran-clarify-spec";

function readLockedSpec() {
  try {
    return JSON.parse(sessionStorage.getItem(CLARIFY_SPEC_KEY) || "null");
  } catch (error) {
    return null;
  }
}

function specMatches(spec, url, requirement) {
  if (!spec || !spec.confirmed_at || spec.pending !== 0) return false;
  if (!spec.session_id || !Array.isArray(spec.spec) || spec.spec.length === 0) return false;
  if (spec.url !== url || spec.requirement !== requirement) return false;
  return true;
}

function formValues() {
  const values = new FormData(form);
  return {
    url: String(values.get("url") || "").trim(),
    requirement: String(values.get("requirement") || "").trim(),
    maxPages: String(values.get("max_pages") || "").trim(),
  };
}

function clarifyHref(values) {
  const params = new URLSearchParams();
  if (values.url) params.set("url", values.url);
  if (values.requirement) params.set("requirement", values.requirement);
  if (values.maxPages) params.set("max_pages", values.maxPages);
  const query = params.toString();
  return query ? `/clarify?${query}` : "/clarify";
}

function scrapeReady() {
  const values = formValues();
  return specMatches(readLockedSpec(), values.url, values.requirement);
}

function startLabel() {
  return scrapeReady() ? t("start") : t("clarifyFirst");
}

function refreshGate() {
  const ready = scrapeReady();
  const hint = document.querySelector("#clarify-hint");
  buttonLabel.dataset.i18n = ready ? "start" : "clarifyFirst";
  hint.dataset.i18n = ready ? "specLocked" : "clarifyHint";
  hint.textContent = t(hint.dataset.i18n);
  if (!requestInProgress) buttonLabel.textContent = t(buttonLabel.dataset.i18n);
}

function renderLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-Hans" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelector("#url-input").placeholder = t("placeholderUrl");
  document.querySelector("#requirement-input").placeholder = t("placeholderRequirement");
  langButton.textContent = t("language");
  if (requestInProgress) buttonLabel.textContent = t("loading");
  document.title = language === "zh" ? "Lioran - 网页数据提取" : "Lioran - Web Data Extraction";
  refreshGate();
}

function setLoading(loading, message = "") {
  requestInProgress = loading;
  submitButton.disabled = loading;
  stopButton.disabled = !loading;
  stopButton.classList.toggle("hidden", !loading);
  buttonLabel.textContent = loading ? t("loading") : startLabel();
  spinner.classList.toggle("hidden", !loading);
  statusMessage.textContent = message;
}

function updateProgress(progress) {
  const percent = Math.max(0, Math.min(100, Number(progress.progress) || 0));
  progressPanel.classList.remove("hidden");
  progressFill.style.width = `${percent}%`;
  progressPercent.textContent = `${percent}%`;
  progressBar.setAttribute("aria-valuenow", String(percent));
  progressSection.textContent = progress.current_section || t("preparing");
  document.querySelector("#progress-pages").textContent = String(progress.pages_crawled || 0);
  document.querySelector("#progress-sections").textContent = String(progress.sections_crawled || 0);
  document.querySelector("#progress-rows").textContent = String(progress.rows_count || 0);
}

function showError(message) {
  errorMessage.textContent = message || t("failed");
  errorPanel.classList.remove("hidden");
}

function clearError() {
  errorPanel.classList.add("hidden");
  errorMessage.textContent = "";
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok || !body || body.code !== 0) {
    throw new Error(body?.msg || t("failed"));
  }
  return body.data;
}

function renderTable(columns, rows, total, taskId, feedbackEnabled = true) {
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.replaceChildren();
  tbody.replaceChildren();

  const headerRow = document.createElement("tr");
  columns.forEach((column) => {
    const header = document.createElement("th");
    header.scope = "col";
    header.textContent = column;
    headerRow.append(header);
  });
  thead.append(headerRow);

  rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.setAttribute("aria-label", `${rowIndex + 1}`);
    row.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value ?? "";
      tr.append(td);
    });
    const sendFeedback = async () => {
      if (!feedbackEnabled) return;
      if (requestInProgress || tr.classList.contains("selected")) return;
      tbody.querySelectorAll("tr").forEach((item) => item.classList.remove("selected"));
      tr.classList.add("selected");
      clearError();
      statusMessage.textContent = t("feedback");
      setLoading(true, t("feedback"));
      try {
        const result = await api("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: taskId, correct_row_index: rowIndex }),
        });
        activeTaskId = result.task_id;
        renderTable(result.columns, result.preview_rows, result.total, result.task_id);
      } catch (error) {
        showError(error.message);
      } finally {
        setLoading(false);
      }
    };
    if (feedbackEnabled) {
      tr.addEventListener("click", sendFeedback);
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          sendFeedback();
        }
      });
    } else {
      tr.removeAttribute("tabindex");
      tr.removeAttribute("aria-label");
    }
    tbody.append(tr);
  });

  document.querySelector("#total-count").textContent = String(total);
  document.querySelector("#crawl-summary").classList.add("hidden");
  resultsPanel.classList.remove("hidden");
}

async function startCrawl(event) {
  event.preventDefault();
  if (requestInProgress) return;
  const locked = readLockedSpec();
  const formData = formValues();
  if (!specMatches(locked, formData.url, formData.requirement)) {
    clearError();
    window.location.assign(clarifyHref(formData));
    return;
  }
  clearError();
  resultsPanel.classList.add("hidden");
  progressPanel.classList.add("hidden");
  activeCrawlId = null;
  setLoading(true, t("working"));
  try {
    let progress = await api("/api/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: formData.url,
        requirement: formData.requirement,
        max_pages: Number(formData.maxPages),
        session_id: locked.session_id,
        spec: locked.spec,
      }),
    });
    activeCrawlId = progress.crawl_id;
    updateProgress(progress);
    while (!["completed", "stopped", "error"].includes(progress.status)) {
      await new Promise((resolve) => window.setTimeout(resolve, 900));
      progress = await api(`/api/crawl/${encodeURIComponent(activeCrawlId)}`);
      updateProgress(progress);
      if (progress.status === "mapping") statusMessage.textContent = t("mapping");
      if (progress.status === "stopping") statusMessage.textContent = t("stopping");
    }
    if (progress.status === "error") throw new Error(progress.error || t("failed"));
    if (!progress.task_id) throw new Error(t("failed"));
    const result = await api(`/api/preview?task_id=${encodeURIComponent(progress.task_id)}`);
    activeTaskId = result.task_id;
    renderTable(result.columns, result.rows, result.total, result.task_id, false);
    const summaryKey = progress.status === "stopped" ? "stoppedSummary" : "crawlSummary";
    document.querySelector("#crawl-summary").textContent = t(summaryKey)
      .replace("{pages}", String(progress.pages_crawled))
      .replace("{sections}", String(progress.sections_crawled));
    document.querySelector("#crawl-summary").classList.remove("hidden");
  } catch (error) {
    showError(error.message);
  } finally {
    activeCrawlId = null;
    setLoading(false);
  }
}

form.addEventListener("submit", (event) => {
  if (!scrapeReady()) {
    event.preventDefault();
    clearError();
    window.location.assign(clarifyHref(formValues()));
    return;
  }
  startCrawl(event);
});
["#url-input", "#requirement-input"].forEach((selector) => {
  document.querySelector(selector).addEventListener("input", refreshGate);
});
stopButton.addEventListener("click", async () => {
  if (!activeCrawlId || stopButton.disabled) return;
  stopButton.disabled = true;
  statusMessage.textContent = t("stopping");
  try {
    const progress = await api(`/api/crawl/${encodeURIComponent(activeCrawlId)}/stop`, {
      method: "POST",
    });
    updateProgress(progress);
  } catch (error) {
    showError(error.message || t("failed"));
    stopButton.disabled = false;
  }
});
langButton.addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  renderLanguage();
});
document.querySelector("#retry-button").addEventListener("click", () => {
  if (!requestInProgress) form.requestSubmit();
});
document.querySelector("#download-button").addEventListener("click", async () => {
  if (!activeTaskId || requestInProgress) return;
  clearError();
  try {
    const response = await fetch(`/api/download?task_id=${encodeURIComponent(activeTaskId)}`);
    const type = response.headers.get("content-type") || "";
    if (!response.ok) {
      const body = type.includes("application/json") ? await response.json() : null;
      throw new Error(body?.msg || t("downloadError"));
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `lioran-${activeTaskId.slice(0, 8)}.xlsx`;
    anchor.hidden = true;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (error) {
    showError(error.message || t("downloadError"));
  }
});

const incoming = new URLSearchParams(window.location.search);
if (incoming.get("url")) document.querySelector("#url-input").value = incoming.get("url");
if (incoming.get("requirement")) {
  document.querySelector("#requirement-input").value = incoming.get("requirement");
}
if (incoming.get("max_pages")) {
  document.querySelector("#max-pages-input").value = incoming.get("max_pages");
}

renderLanguage();
