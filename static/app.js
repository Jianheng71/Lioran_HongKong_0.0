const copy = {
  zh: {
    eyebrow: "本地运行 · 无需编程",
    title: "粘贴链接，说出你想要的数据",
    subtitle: "Lioran 会理解公开网页，并把你需要的信息整理成表格。",
    formTitle: "开始提取",
    urlLabel: "网页链接",
    requirementLabel: "你想提取什么？",
    start: "开始抓取",
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
    reviewSettings: "本地合规审查",
    enableReview: "启用合规审查（本地模型，不上传页面内容）",
    deepReview: "打开详情页取证（详情页计入最大页数）",
    savedReviews: "本机已保存的审查",
    reviewAll: "全部",
    reviewIncluded: "有效保留",
    reviewExcluded: "排除",
    reviewFuture: "待生效",
    reviewManual: "待人工复核",
    reviewNeeds: "需人工确认",
    reviewTableTitle: "标题",
    reviewSection: "栏目",
    reviewCategory: "类别",
    reviewClassification: "主题分类",
    reviewConfidence: "分类信心",
    reviewStatus: "审查状态",
    reviewSourceStatus: "原文状态",
    reviewRisk: "风险等级",
    reviewEffectiveDate: "生效日期",
    reviewExpiryDate: "失效日期",
    reviewReason: "理由",
    reviewEvidence: "证据句子",
    reviewLink: "原文链接",
    reviewCaptured: "抓取时间",
    reviewCorrection: "人工改判",
    correctionSave: "保存",
    correctionIncluded: "确认有效",
    correctionExcluded: "确认排除",
    correctionFuture: "待生效",
    correctionManual: "待复核",
    loadMore: "加载更多",
    localModel: "本地合规审查使用本机 Ollama 模型。",
    classificationTitle: "确认主题标签",
    classificationDescription: "输入要保留的主题，用逗号分隔。系统会自动加入“不是政策”；低于 85% 的记录会转人工复核，高置信主题匹配仍会继续审查政策效力和日期。",
    classificationLabelsLabel: "主题标签",
    classificationPlaceholder: "例如：住房、教育、环境保护",
    classificationRequired: "请至少输入一个主题标签。",
    classificationLimit: "最多输入 8 个主题标签。",
    classificationConfirm: "确认标签并开始",
    cancel: "取消",
  },
  en: {
    eyebrow: "Runs locally · No coding required",
    title: "Paste a link. Tell us what data you need.",
    subtitle: "Lioran understands public web pages and organizes the information into a table.",
    formTitle: "Start extracting",
    urlLabel: "Web page URL",
    requirementLabel: "What would you like to extract?",
    start: "Start scraping",
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
    reviewSettings: "Local compliance review",
    enableReview: "Enable compliance review (local model; page content stays on this device)",
    deepReview: "Open detail pages for evidence (detail pages count toward the page limit)",
    savedReviews: "Saved local reviews",
    reviewAll: "All",
    reviewIncluded: "Included",
    reviewExcluded: "Excluded",
    reviewFuture: "Not yet effective",
    reviewManual: "Manual review",
    reviewNeeds: "Needs confirmation",
    reviewTableTitle: "Title",
    reviewSection: "Section",
    reviewCategory: "Category",
    reviewClassification: "Topic class",
    reviewConfidence: "Confidence",
    reviewStatus: "Review status",
    reviewSourceStatus: "Source status",
    reviewRisk: "Risk level",
    reviewEffectiveDate: "Effective date",
    reviewExpiryDate: "Expiry date",
    reviewReason: "Reason",
    reviewEvidence: "Evidence",
    reviewLink: "Source link",
    reviewCaptured: "Captured at",
    reviewCorrection: "Manual decision",
    correctionSave: "Save",
    correctionIncluded: "Confirm effective",
    correctionExcluded: "Confirm excluded",
    correctionFuture: "Not yet effective",
    correctionManual: "Needs review",
    loadMore: "Load more",
    localModel: "Compliance review runs through the local Ollama model.",
    classificationTitle: "Confirm topic labels",
    classificationDescription: "Enter the topics to keep, separated by commas. “Not a policy” is added automatically; matches below 85% go to manual review, while high-confidence topic matches still proceed to policy status and date review.",
    classificationLabelsLabel: "Topic labels",
    classificationPlaceholder: "For example: housing, education, environment",
    classificationRequired: "Enter at least one topic label.",
    classificationLimit: "Enter no more than 8 topic labels.",
    classificationConfirm: "Confirm labels and start",
    cancel: "Cancel",
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
const reviewPanel = document.querySelector("#review-results");
const reviewTable = document.querySelector("#review-table");
const reviewSummary = document.querySelector("#review-summary");
const reviewLoadMore = document.querySelector("#review-load-more");
const extractionTableWrap = document.querySelector("#extraction-table-wrap");
const savedReviewsPanel = document.querySelector("#saved-reviews");
const savedReviewList = document.querySelector("#saved-review-list");
const reviewMasterInput = document.querySelector("#enable-review-input");
const reviewSuboptions = document.querySelector("#review-suboptions");
const deepReviewInput = document.querySelector("#deep-review-input");
const classificationDialog = document.querySelector("#classification-dialog");
const classificationLabelInput = document.querySelector("#classification-label-input");
const classificationError = document.querySelector("#classification-error");
const langButton = document.querySelector("#language-toggle");
let language = "zh";
let activeTaskId = null;
let activeCrawlId = null;
let requestInProgress = false;
let activeReviewDecision = "all";
let reviewOffset = 0;
let reviewTotal = 0;

function t(key) {
  return copy[language][key];
}

function updateReviewOptions() {
  const enabled = reviewMasterInput.checked;
  deepReviewInput.disabled = !enabled;
  reviewSuboptions.classList.toggle("disabled", !enabled);
}

function renderLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-Hans" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelector("#url-input").placeholder = t("placeholderUrl");
  document.querySelector("#requirement-input").placeholder = t("placeholderRequirement");
  classificationLabelInput.placeholder = t("classificationPlaceholder");
  langButton.textContent = t("language");
  if (requestInProgress) buttonLabel.textContent = t("loading");
  document.title = language === "zh" ? "Lioran - 网页数据提取" : "Lioran - Web Data Extraction";
}

function setLoading(loading, message = "") {
  requestInProgress = loading;
  submitButton.disabled = loading;
  stopButton.disabled = !loading;
  stopButton.classList.toggle("hidden", !loading);
  buttonLabel.textContent = loading ? t("loading") : t("start");
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
  reviewPanel.classList.add("hidden");
  extractionTableWrap.classList.remove("hidden");
  document.querySelector(".hint").classList.remove("hidden");
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

function renderReviewSummary(summary = {}) {
  reviewSummary.replaceChildren();
  const entries = [
    [t("reviewIncluded"), summary.included || 0],
    [t("reviewExcluded"), summary.excluded || 0],
    [t("reviewFuture"), summary.future || 0],
    [t("reviewManual"), summary.manual_review || 0],
    [t("reviewNeeds"), summary.needs_review || 0],
  ];
  entries.forEach(([label, value]) => {
    const item = document.createElement("span");
    item.className = "review-summary-item";
    const count = document.createElement("strong");
    count.textContent = String(value);
    const caption = document.createElement("span");
    caption.textContent = label;
    item.append(count, caption);
    reviewSummary.append(item);
  });
}

function makeCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value || "—";
  return cell;
}

function addReviewRow(body, item) {
  const row = document.createElement("tr");
  row.append(
    makeCell(item.title),
    makeCell(item.section),
    makeCell(item.category),
    makeCell(item.classification_label),
    makeCell(item.classification_confidence == null
      ? ""
      : `${Math.round(Number(item.classification_confidence) * 100)}%`),
    makeCell(item.lifecycle_status),
    makeCell(item.status_text),
    makeCell(item.risk_level),
    makeCell(item.effective_date || item.effective_date_str),
    makeCell(item.expiry_date || item.expiry_date_str),
    makeCell(item.reason),
    makeCell(item.evidence),
  );
  const linkCell = document.createElement("td");
  if (item.link) {
    const link = document.createElement("a");
    link.href = item.link;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = item.link;
    linkCell.append(link);
  } else {
    linkCell.textContent = "—";
  }
  row.append(linkCell, makeCell(item.captured_at));

  const correctionCell = document.createElement("td");
  const controls = document.createElement("div");
  controls.className = "review-correction";
  const select = document.createElement("select");
  select.setAttribute("aria-label", t("reviewCorrection"));
  [
    ["included", t("correctionIncluded")],
    ["excluded", t("correctionExcluded")],
    ["future", t("correctionFuture")],
    ["manual_review", t("correctionManual")],
  ].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (item.decision === value) option.selected = true;
    select.append(option);
  });
  const save = document.createElement("button");
  save.type = "button";
  save.className = "review-save-button";
  save.textContent = t("correctionSave");
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api(`/api/review/items/${encodeURIComponent(item.review_id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: select.value, note: "" }),
      });
      const task = await api(`/api/preview?task_id=${encodeURIComponent(activeTaskId)}`);
      renderReviewSummary(task.review_summary);
      await loadReviewItems(activeReviewDecision, 0, false);
      await loadSavedReviews();
    } catch (error) {
      showError(error.message);
    } finally {
      save.disabled = false;
    }
  });
  controls.append(select, save);
  correctionCell.append(controls);
  row.append(correctionCell);
  body.append(row);
}

async function loadReviewItems(decision, offset = 0, append = false) {
  activeReviewDecision = decision;
  reviewOffset = offset;
  if (!append) {
    reviewTable.querySelector("thead").replaceChildren();
    reviewTable.querySelector("tbody").replaceChildren();
  }
  const params = new URLSearchParams({
    task_id: activeTaskId,
    decision,
    offset: String(offset),
    limit: "100",
  });
  const result = await api(`/api/review/items?${params}`);
  reviewTotal = result.total;
  const headers = [
    t("reviewTableTitle"), t("reviewSection"), t("reviewCategory"), t("reviewClassification"),
    t("reviewConfidence"), t("reviewStatus"),
    t("reviewSourceStatus"), t("reviewRisk"), t("reviewEffectiveDate"), t("reviewExpiryDate"),
    t("reviewReason"), t("reviewEvidence"), t("reviewLink"), t("reviewCaptured"),
    t("reviewCorrection"),
  ];
  const thead = reviewTable.querySelector("thead");
  if (!append) {
    const headerRow = document.createElement("tr");
    headers.forEach((value) => {
      const header = document.createElement("th");
      header.scope = "col";
      header.textContent = value;
      headerRow.append(header);
    });
    thead.append(headerRow);
  }
  const body = reviewTable.querySelector("tbody");
  result.items.forEach((item) => addReviewRow(body, item));
  const shown = Math.min(offset + result.items.length, reviewTotal);
  reviewLoadMore.classList.toggle("hidden", shown >= reviewTotal);
  reviewLoadMore.textContent = `${t("loadMore")} (${shown}/${reviewTotal})`;
  document.querySelectorAll(".review-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.decision === decision);
    tab.setAttribute("aria-selected", String(tab.dataset.decision === decision));
  });
}

async function showReviewResults(taskId, summary) {
  activeTaskId = taskId;
  reviewPanel.classList.remove("hidden");
  extractionTableWrap.classList.add("hidden");
  document.querySelector(".hint").classList.add("hidden");
  document.querySelector("#total-count").textContent = String(summary?.total || 0);
  renderReviewSummary(summary);
  resultsPanel.classList.remove("hidden");
  await loadReviewItems("all");
}

async function loadSavedReviews() {
  try {
    const result = await api("/api/review/tasks");
    savedReviewList.replaceChildren();
    if (!result.tasks.length) {
      savedReviewsPanel.classList.add("hidden");
      return;
    }
    result.tasks.forEach((task) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "saved-review-button";
      button.textContent = `${new Date(task.created_at).toLocaleString()} · ${task.url} · ${task.total}`;
      button.addEventListener("click", async () => {
        clearError();
        try {
          const result = await api(`/api/preview?task_id=${encodeURIComponent(task.task_id)}`);
          await showReviewResults(result.task_id, result.review_summary);
        } catch (error) {
          showError(error.message);
        }
      });
      savedReviewList.append(button);
    });
    savedReviewsPanel.classList.remove("hidden");
  } catch (error) {
    showError(error.message);
  }
}

async function startCrawl(event) {
  event.preventDefault();
  if (requestInProgress) return;
  if (reviewMasterInput.checked) {
    classificationError.classList.add("hidden");
    classificationError.textContent = "";
    classificationDialog.showModal();
    classificationLabelInput.focus();
    return;
  }
  await runCrawl([]);
}

async function runCrawl(classificationLabels) {
  if (requestInProgress) return;
  clearError();
  resultsPanel.classList.add("hidden");
  progressPanel.classList.add("hidden");
  activeCrawlId = null;
  setLoading(true, t("working"));
  const values = new FormData(form);
  try {
    let progress = await api("/api/crawl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: values.get("url"),
        requirement: values.get("requirement"),
        max_pages: Number(values.get("max_pages")),
        enable_review: document.querySelector("#enable-review-input").checked,
        review_time: true,
        deep_review: document.querySelector("#deep-review-input").checked,
        classification_labels: classificationLabels,
      }),
    });
    activeCrawlId = progress.crawl_id;
    updateProgress(progress);
    while (!["completed", "stopped", "error"].includes(progress.status)) {
      await new Promise((resolve) => window.setTimeout(resolve, 900));
      progress = await api(`/api/crawl/${encodeURIComponent(activeCrawlId)}`);
      updateProgress(progress);
      if (progress.status === "mapping") {
        const reviewProgress = progress.current_section?.match(
          /本地合规审查\s+(\d+)\/(\d+)\s*条/,
        );
        const classificationProgress = progress.current_section?.match(
          /本地主题分类\s+(\d+)\/(\d+)\s*条/,
        );
        statusMessage.textContent = classificationProgress
          ? `${t("classificationTitle")} (${classificationProgress[1]}/${classificationProgress[2]})`
          : reviewProgress
            ? `${t("localModel")} (${reviewProgress[1]}/${reviewProgress[2]})`
            : t("mapping");
      }
      if (progress.status === "stopping") statusMessage.textContent = t("stopping");
    }
    if (progress.status === "error") throw new Error(progress.error || t("failed"));
    if (!progress.task_id) throw new Error(t("failed"));
    const result = await api(`/api/preview?task_id=${encodeURIComponent(progress.task_id)}`);
    activeTaskId = result.task_id;
    if (result.review_enabled) {
      await showReviewResults(result.task_id, result.review_summary);
      await loadSavedReviews();
    } else {
      renderTable(result.columns, result.rows, result.total, result.task_id, false);
    }
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

form.addEventListener("submit", startCrawl);
document.querySelector("#classification-cancel").addEventListener("click", () => {
  classificationDialog.close();
});
document.querySelector("#classification-confirm").addEventListener("click", async () => {
  const labels = [...new Set(
    classificationLabelInput.value
      .split(/[，,、;；\n]+/)
      .map((label) => label.trim())
      .filter(Boolean),
  )];
  if (!labels.length || labels.length > 8) {
    classificationError.textContent = labels.length ? t("classificationLimit") : t("classificationRequired");
    classificationError.classList.remove("hidden");
    return;
  }
  classificationDialog.close();
  await runCrawl(labels);
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
reviewMasterInput.addEventListener("change", updateReviewOptions);
document.querySelectorAll(".review-tab").forEach((tab) => {
  tab.addEventListener("click", async () => {
    try {
      await loadReviewItems(tab.dataset.decision);
    } catch (error) {
      showError(error.message);
    }
  });
});
reviewLoadMore.addEventListener("click", async () => {
  try {
    await loadReviewItems(activeReviewDecision, reviewOffset + 100, true);
  } catch (error) {
    showError(error.message);
  }
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

renderLanguage();
updateReviewOptions();
loadSavedReviews();
