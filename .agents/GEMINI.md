# Project Rules & Agent Directives (dancecoveruni)

You are operating within this codebase as an autonomous pair programmer for **`dancecoveruni`** — an automated YouTube Shorts pipeline for Dance Cover content. You must strictly abide by the following non-negotiable engineering directives.

---

## 1. Project Overview & Architecture
`dancecoveruni` is a fully autonomous daily pipeline deployed and executed entirely on **GitHub Actions** (Ubuntu 24.04 / Python 3.11 runner):
- **Autonomous Publishing Schedule**: Operates on a strict 3/3 daily distribution model:
  - **3 videos published today**: Staggered across target delays (e.g., 0h, 4h, 8h).
  - **3 videos scheduled for tomorrow**: Pre-staged into YouTube scheduled publish slots (e.g., 24h, 28h, 32h).
  - Daily pipeline runs continuously without requiring manual approvals.
- **Topic & Keyword Management**:
  - Structured via `config/topics.json` (categorized by dance genre, Asian dancer choreography focus, Chinese queries for Douyin, and hashtags for TikTok).
  - Uses **Gemini API** (`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` with dynamic API availability checks) to generate trending search terms.
- **Search & Discovery**:
  - Primary source: **Douyin** via Jina Search API (`s.jina.ai` with `X-Site: douyin.com`).
  - Secondary fallback: **TikTok** via Jina Search API when Douyin fresh candidates are below target.
  - Canonical URL filtering: Rigorous regex cleansing stripping all trailing punctuation (`.,:;…!?'\"/`) and trackers.
  - Token Accounting: Extracts Jina API tokens used and remaining quota, triggering alerts when remaining quota drops to <= 1,000,000 tokens.
- **3-Tier Media Download Architecture**:
  - **Layer 1 (Pure CLI yt-dlp)**: High-speed CLI download using the patched `viking1304/yt-dlp@douyin-fix` (PR #17826) with `curl_cffi` impersonation. Does NOT require cookies.
  - **Layer 2 (CLI yt-dlp with cookies)**: Uses `DOUYIN_COOKIES` injected via GitHub Secrets if Layer 1 encounters rate limits.
  - **Layer 3 (Direct Signed Python API)**: Autonomous fallback in `src/downloader.py` using MD5 query signing (`_SEC_SALT = 'A96D855A08C0A9707F8BEF0D9A527E4E'`, `_AID = 6383`), automated `ttwid` registration, and `uifid` extraction.
- **AI Quality Gate**: Evaluates extracted video frames using Gemini Vision (`gemini-3.1-flash-lite`) to verify active dance choreography, performer visibility, and safety.
- **Telegram Notification & Backup**:
  - Uploads full MP4 video files to Telegram as cloud backup.
  - Sends an **Executive Summary** HTML report summarizing Jina tokens used/remaining, scraped video counts, download/approval stats, and quota warnings.
- **YouTube Upload**: Uploads approved videos as `#Shorts` using YouTube Data API v3 with OAuth2 Refresh Token.
- **State Management**: Persists processed URLs, upload IDs, and cumulative Jina token usage in `data/history.json`, automatically committed back to `main` via `stefanzweifel/git-auto-commit-action`.

---

## 2. Directory Scopes & Editable Zones

### ✅ Allowed Zones (Full Autonomy)
The Agent has full authority to create, update, and refactor code in:
- `src/`: Python source modules (`ai_keywords.py`, `searcher.py`, `downloader.py`, `quality_checker.py`, `telegram_notifier.py`, `youtube_uploader.py`, `main.py`).
- `config/`: Configuration files (`channel_config.json`, `topics.json`).
- `docs/`: Technical playbooks and roadmaps (`DEBUGGING_PLAYBOOK.md`, `ROADMAP.md`).
- `.github/workflows/`: GitHub Actions workflow files (`pipeline.yml`).
- `data/`: Local state files (`data/history.json`).
- `tests/`: Unit tests and mock suites.
- `requirements.txt`: Dependencies.
- `README.md` & project documentation.

### ⛔ Forbidden / Protected Zones (Zero Modification / No Staging)
The Agent must **NEVER** edit, create, stage, or push to:
- **Temporary / Cache Directories**: `downloads/`, `tmp/`, `.temp/`, `*.mp4`, `*.webm`, `*.part` (MUST be in `.gitignore`).
- **Credentials & Secret Files**: `.env*`, `client_secrets.json`, `token.json`, `*.pickle`, `*.pem`, `*.key`.
- **Git History**: Never execute `git push --force`.

---

## 3. Strict Execution & Verification Directives

> [!CAUTION]
> **ABSOLUTE RULE: ZERO LOCAL PYTHON EXECUTION**
> Under NO circumstances should the Agent run `python`, `pytest`, `pip`, or pipeline commands locally on the user's Windows machine.
> All execution, unit testing, and integration verification MUST run inside GitHub Actions runners via `gh workflow run pipeline.yml -f dry_run=true`.
> The local machine is strictly for code editing, git commits, and dispatching GitHub CLI commands.

- **Automated Verification Workflow**:
  1. Commit code locally (`git add ... ; git commit -m "..."`).
  2. Sync with remote (`git pull --rebase origin main ; git push origin main` using `BypassSandbox: true`).
  3. Dispatch workflow: `gh workflow run pipeline.yml -f dry_run=true` (using `BypassSandbox: true`).
  4. Watch run: `gh run watch <run_id> --exit-status`.
  5. Inspect logs: `gh run view <run_id> --log` to verify exit codes, unit tests, and pipeline output.

---

## 4. Security, Credentials & Boundary Protection
- **Zero Secrets Exposure**: Never hardcode API keys or credentials. All secrets are injected dynamically via GitHub Actions Secrets:
  - `GEMINI_API_KEY`
  - `JINA_API_KEY`, `FIRECRAWL_API_KEY`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`
  - `DOUYIN_COOKIES`
- **Log & Payload Redaction**: Never print raw authorization tokens in logs.
- **Workspace Containment**: Restrict file operations to the repository directory.

---

## 5. Token Conservation & Communication Directives
- **Concise Execution**: Keep responses direct, actionable, and technical.
- **Clickable File Links**: Format all file paths and code symbols as clickable Markdown links adhering to the `file://` URI scheme (e.g., [pipeline.yml](file:///c:/Users/LENOVO/Documents/MEGA%20Programming%20Database/web-dev/antigravity/automation-ytb/dancecoveruni/.github/workflows/pipeline.yml)).
