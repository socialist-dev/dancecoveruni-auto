# Project Rules & Agent Directives (dancecoveruni)

You are operating within this codebase as an autonomous pair programmer for **`dancecoveruni`** — an automated YouTube Shorts pipeline for Dance Cover content. You must strictly abide by the following non-negotiable engineering directives.

---

## 1. Project Overview & Architecture
`dancecoveruni` is a daily scheduled automation pipeline deployed on **GitHub Actions** (Python-based runner):
- **Keyword Generation**: Uses **Gemini API** (free tier with high RPD, e.g., Gemini 2.5/Flash) to generate trending Chinese search keywords/topics matching the channel's dance cover scope.
- **Search & Discovery**: Queries **Jina API** & **Firecrawl API** via Google Dorking operators (e.g., `site:douyin.com/video/ "..."`) to extract direct Douyin/TikTok video URLs.
- **Media Download**: Uses **`yt-dlp`** to download high-quality vertical (9:16) videos and extract video metadata.
- **Channel Configuration**: Titles, descriptions, hashtags, credit templates, and upload parameters are decoupled into configurable JSON files (e.g., `config/channel_config.json`).
- **Telegram Notification & Backup**: Sends downloaded video/metadata to a Telegram Bot as a backup channel and execution log.
- **YouTube Upload**: Automatically uploads vertical videos as **YouTube Shorts** (`#Shorts`) using the YouTube Data API v3 with OAuth2 Refresh Token authentication.
- **Deduplication State**: Manages `data/history.json` to track processed video IDs/URLs, preventing duplicate uploads and conserving daily API quota (YouTube quota: 1,600 units/upload out of 10,000 daily units). State is committed back to the repository via GitHub Actions bot.

---

## 2. Directory Scopes & Editable Zones

### ✅ Allowed Zones (Full Autonomy)
The Agent has full authority to create, update, and refactor code in:
- `src/` or `scripts/`: Python source modules (`ai_keywords.py`, `dorking_search.py`, `downloader.py`, `telegram_bot.py`, `youtube_uploader.py`, `main.py`).
- `config/`: JSON configuration files for channel metadata, prompt templates, and non-sensitive options (`channel_config.json`, `search_patterns.json`).
- `.github/workflows/`: GitHub Actions workflow files (`daily_pipeline.yml`, `manual_dispatch.yml`).
- `data/`: Local data files such as `data/history.json` or `.gitkeep`.
- `tests/`: Unit tests and mocked integration test suites.
- `requirements.txt` / `pyproject.toml`: Dependency definitions (`google-genai`, `yt-dlp`, `requests`, `google-api-python-client`, `google-auth-oauthlib`, etc.).
- `README.md` & documentation files.

### ⛔ Forbidden / Protected Zones (Zero Modification / No Staging)
The Agent must **NEVER** edit, create, stage, or push to:
- **Temporary / Cache Directories**: `downloads/`, `tmp/`, `.temp/`, `*.mp4`, `*.webm`, `*.part` (MUST be kept in `.gitignore`).
- **Credentials & Secret Files**: `.env*`, `client_secrets.json`, `token.json`, `*.pickle`, `*.pem`, `*.key`.
- **Git History**: Never execute `git push --force` or commands altering upstream git history.

---

## 3. Security, Credentials & Boundary Protection
- **Zero Secrets Exposure**: Never hardcode API keys or credentials. All secrets are injected dynamically via environment variables / GitHub Actions Secrets:
  - `GEMINI_API_KEY`
  - `JINA_API_KEY` / `FIRECRAWL_API_KEY`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`
- **Log & Payload Redaction**: When outputting logs, CLI outputs, or debugging responses, always mask sensitive tokens and authorization headers with `[REDACTED_BY_SECURITY_POLICY]`.
- **Workspace Containment**: Restrict all file reads/writes to `c:\Users\LENOVO\Documents\MEGA Programming Database\web-dev\antigravity\automation-ytb\dancecoveruni`. Do not touch parent directories or OS paths.

---

## 4. Testing, Dry-Run & Quality Engineering
- **Mandatory `--dry-run` Default**: All pipeline runner scripts (`main.py`) must support a `--dry-run` flag. Whenever the Agent runs test executions locally:
  - Gemini API & search queries may execute or use cached sample results.
  - Video download is limited to metadata retrieval or a short 5-second sample to save bandwidth/disk.
  - YouTube upload and Telegram dispatch must be **mocked** (log output only, no actual upload/broadcast).
- **Quota Safety**: Implement deduplication checks against `data/history.json` before triggering any download or upload. Abort gracefully if daily quota limits are approached.
- **Contract-First Development**: Define data schemas (Pydantic models or TypedDict for video metadata, search results, and upload payloads) before implementing business logic.
- **Automated Verification**: Before declaring any coding step complete, verify code syntax and tests using the terminal (`python -m pytest` or `python main.py --dry-run`).

---

## 5. Token Conservation & Communication Directives
- **Concise Execution**: Keep responses direct, actionable, and technical. Avoid redundant pleasantries.
- **Atomic Modifications**: Prefer localized text replacements using targeted editing tools (`replace_file_content`) over rewriting entire files. Preserve existing comments and docstrings.
- **Clickable File Links**: Format all file paths and code symbols as clickable Markdown links adhering to the `file://` URI scheme (e.g., [main.py](file:///c:/Users/LENOVO/Documents/MEGA%20Programming%20Database/web-dev/antigravity/automation-ytb/dancecoveruni/src/main.py)).
