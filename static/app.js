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
    resultsEyebrow: "提取结果",
    totalPrefix: "共抓到",
    totalSuffix: "条",
    download: "下载 Excel",
    retry: "重新抓取",
    rowHint: "点选一行可以告诉 Lioran 哪条记录才是正确结果。",
    disclaimer: "仅用于公开数据，请遵守目标网站条款与当地法律法规。",
    placeholderUrl: "https://example.com/news",
    placeholderRequirement: "例如：我要标题、发布时间和链接",
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
    loading: "AI is understanding the page...",
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
const errorPanel = document.querySelector("#error-panel");
const errorMessage = document.querySelector("#error-message");
const resultsPanel = document.querySelector("#results-panel");
const table = document.querySelector("#results-table");
const langButton = document.querySelector("#language-toggle");
let language = "zh";
let activeTaskId = null;
let requestInProgress = false;

function t(key) {
  return copy[language][key];
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
}

function setLoading(loading, message = "") {
  requestInProgress = loading;
  submitButton.disabled = loading;
  buttonLabel.textContent = loading ? t("loading") : t("start");
  spinner.classList.toggle("hidden", !loading);
  statusMessage.textContent = message;
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

function renderTable(columns, rows, total, taskId) {
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
    tr.addEventListener("click", sendFeedback);
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        sendFeedback();
      }
    });
    tbody.append(tr);
  });

  document.querySelector("#total-count").textContent = String(total);
  resultsPanel.classList.remove("hidden");
}

async function startScrape(event) {
  event.preventDefault();
  if (requestInProgress) return;
  clearError();
  resultsPanel.classList.add("hidden");
  setLoading(true, t("working"));
  const values = new FormData(form);
  try {
    const result = await api("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: values.get("url"),
        requirement: values.get("requirement"),
        max_pages: 1,
      }),
    });
    activeTaskId = result.task_id;
    renderTable(result.columns, result.preview_rows, result.total, result.task_id);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", startScrape);
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
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `lioran-${activeTaskId.slice(0, 8)}.xlsx`;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  } catch (error) {
    showError(error.message || t("downloadError"));
  }
});

renderLanguage();
