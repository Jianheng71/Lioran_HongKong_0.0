# Lioran

Lioran 是一个本地运行的无代码网页数据提取工具：粘贴公开网页链接，用一句话描述需要的数据，得到表格预览并导出 Excel。

> **免责声明：** 仅用于公开数据。使用前请遵守目标网站的服务条款、robots.txt 及当地法律法规。Lioran 不会尝试绕过登录、付费墙、验证码或安全挑战。

## 效果预览

<!-- TODO: 添加应用截图 -->

## 快速开始

先安装并启动 [Ollama](https://ollama.com/download)。

**macOS / Linux：** 在项目目录打开终端，运行 `./setup.sh`；完成后运行 `./start.sh`。安装脚本会创建虚拟环境、安装 Python 依赖和浏览器，并下载 Hermes 模型。

**Windows：** 先安装并启动 Ollama，然后双击 `setup.bat`；完成后双击 `start.bat`。

打开 <http://localhost:8000> 使用。

## 手动本地运行

需要 Python 3.11 或更新版本、[Ollama](https://ollama.com/) 和 Chromium。

```bash
# 1. 安装依赖并准备浏览器
git clone https://github.com/Jianheng71/Lioran_HongKong_0.0.git
cd Lioran_HongKong_0.0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
patchright install chromium

# 2. 启动本地模型
ollama pull hermes3:8b
# 确保 Ollama 服务正在运行；如需手动启动，请在另一个终端运行 ollama serve

# 3. 启动应用
cp .env.example .env
python -m app.main
```

打开 <http://localhost:8000>。Ollama 必须在本机运行；除了访问用户指定的公开目标网页，页面理解、规则生成和数据处理均在本地完成，不调用付费 AI API。

## Docker 一键运行

安装并启动 Docker Desktop 后，在项目目录执行：

```bash
docker compose up
```

首次启动会构建应用容器、启动容器内的 Ollama 并下载 Hermes 模型（约 4.7 GB），之后启动 Lioran。模型保存在 Docker volume 中。打开 <http://localhost:8000> 使用；按 `Ctrl+C` 停止。

## 技术栈与工作流程

- **Crawl4AI**：读取单页、生成 Markdown，并通过 `JsonCssExtractionStrategy.generate_schema(html=...)` 基于精简 HTML 骨架生成 CSS 规则。
- **Hermes 3 8B / Ollama**：本地推理。Markdown 用于理解语义，HTML 骨架仅保留最多三个重复卡片的标签和 class，字段选择器必须在骨架中真实存在。
- **Scrapling**：按已校验的 CSS 规则提取页面数据；高速请求无结果时尝试其基于 Patchright 的浏览器抓取器。
- **FastAPI + 原生 HTML/CSS/JavaScript**：静态单页界面、预览与 Excel 下载。没有登录、用户系统或翻页功能。

目前每个任务只抓取一个公开页面。结果在进程内临时保存，默认一小时后过期。

## 配置

复制 `.env.example` 到 `.env` 后可调整 Ollama 地址、模型、重试次数和超时。默认模型为 `hermes3:8b`，需先通过 Ollama 下载。

## 测试

```bash
python -m unittest discover -s tests -v
```

`test_hermes_json.py` 会连接本地 Ollama 连续生成 10 次；没有运行 Ollama 时会跳过。列表页和详情页测试验证 HTML 骨架及值清洗规则，不会伪装成真实网络抓取。真实站点测试需使用你有权访问且允许自动抓取的公开页面。

## 许可

本项目以 MIT License 发布。Crawl4AI 使用 Apache-2.0；请分别遵守各依赖的许可证。
