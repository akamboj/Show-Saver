# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Show-Saver is a Flask-based video downloader that queues and processes video downloads using yt-dlp. It provides a web interface for managing downloads and automatically organizes them into a TV show library structure (`ShowName/Season N/episode.ext`).

## Commands

### Development with Docker (Recommended)
```bash
docker compose -f compose.dev.yaml up --build
# or use the helper scripts:
bash scripts/run_dev.sh       # Linux
./scripts/run_dev.ps1         # Windows PowerShell
```

### Local Python Development
```bash
pip install -r requirements.txt
python -m showsaver.main
```

The Flask app runs on http://localhost:5000.

### VS Code
- Use the "Python Run script" launch configuration for local debugging
- Use "Docker: Attach" to connect debugpy on port 5678 when running in container
- VS Code tasks are available for docker-compose build/up

## Architecture

```
Flask Web Server (main.py)
├── Routes: /, /favicon.ico, /submit, /status/<job_id>, /queue, /history
│            /dropout/new-releases, /dropout/info
├── Background download_worker thread → processes queue via downloader.process_url()
└── Background metadata_worker thread → fills Dropout episode metadata via yt-dlp

downloader.py
├── get_metadata()         → extracts show info via yt-dlp
├── download_show()        → downloads video with SponsorBlock removal and subtitle embedding
├── copy_to_destination()  → organizes to SHOW_DIR/{ShowName}/Season {N}/
└── process_url()          → master orchestration (metadata → download → organize → Sonarr)

sonarr.py
└── Sonarr API client: rescan, rename, wait for command completion

database.py
├── init_db()                        → creates table + enables WAL / busy_timeout
├── upsert_dropout_episode()         → full row upsert (used by metadata worker)
├── upsert_dropout_episode_basic()   → scrape-time upsert that preserves show_name
├── get_dropout_episode(url_path)    → single-row read
└── get_all_dropout_episodes()       → full-table read

processors/dropout.py
├── DropoutProcessor              → custom processor for Dropout content (show name overrides, specials handling)
├── get_new_releases()            → scrapes Dropout releases, merges with DB, queues worker for rows missing show_name
├── fetch_and_store_episode_info() → yt-dlp fetch + DB upsert (called by metadata worker)
└── get_epsiode_info()            → DB-only read (worker populates rows asynchronously)

state.py
├── download_queue / download_status / download_history
├── metadata_queue / metadata_in_flight   → dedup'd queue for metadata worker
└── queue_metadata(url, url_path)         → thread-safe enqueue

env.py
└── Environment configuration (CONFIG_DIR, SHOW_DIR, TMP_DIR, DB_PATH, etc.)
```

### Download Flow
1. URL submitted via POST /submit → duplicate-checked and added to queue with job ID
2. Background worker picks up job, updates status to "downloading"
3. yt-dlp extracts metadata, downloads video with:
   - SponsorBlock segment removal (sponsor, selfpromo, interaction, intro, outro)
   - Chapter metadata update to mark removed segments
   - Subtitle downloading and embedding via FFmpegEmbedSubtitle
4. Progress reported in steps: video stream → audio stream → post-processing
5. File copied to organized path: `{SHOW_DIR}/{series}/Season {N}/{episode}.ext`
6. Sonarr rescan (and optional rename) triggered if configured
7. Temp file cleaned up if `AUTO_CLEANUP_TMP=true`

**Output filename template:**
`%(series)s - S%(season_number)02dE%(episode_number)02d - %(title)s WEBDL-1080p.%(ext)s`

### Processor Pattern
Processors customize download behavior per content source. `DropoutProcessor` (in `processors/dropout.py`) is the current implementation:
- `process_info_dict()` — marks "Last Looks" episodes as S00E00 (Specials)
- `process_dlp_opts()` — customizes output template for special episodes
- `process_show_name()` — applies show name overrides (e.g., `'Very Important People'` → `'Very Important People (2023)'`)
- `should_trigger_rename()` — returns `True` for episodes that need Sonarr rename

### Metadata Caching
Episode metadata for Dropout releases is cached in SQLite at `DB_PATH` (default `{CONFIG_DIR}/showsaver.db`).

- **Table:** `dropout_episodes(url_path PK, url, show_name, title, thumbnail, duration, fetched_at)`
- **Scrape path:** `/dropout/new-releases` triggers `get_new_releases()`, which scrapes the public HTML, upserts scrape-time fields via `upsert_dropout_episode_basic()` (preserves any existing `show_name`), and enqueues a background `metadata_worker` job for any row still missing `show_name`.
- **Worker:** `metadata_worker` (started in `main.py`) runs yt-dlp per URL and calls `upsert_dropout_episode()` with the full row. `metadata_in_flight` (guarded by `thread_lock`) dedups concurrent enqueues.
- **Frontend polling:** `app.js` polls `/dropout/new-releases` every 2 s (up to 30 polls) until every card has a `show_name`.
- **Concurrency:** WAL journal mode + `busy_timeout=5000` are set in `init_db()` so the download worker, metadata worker, and request threads can write concurrently.
- **In-memory scrape cache:** `_new_releases_cache` holds a URL list with a 5-minute TTL to avoid re-scraping on every poll; the DB is the source of truth for metadata.
- **Reset:** `bash scripts/reset_db.sh` deletes the local dev DB (`./.local/config/showsaver.db`).

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| CONFIG_DIR | /config | Stores urls.txt, .netrc for auth, and showsaver.db |
| SHOW_DIR | /tvshows | Final destination for organized episodes |
| TMP_DIR | /temp_dir | Temporary download directory |
| DB_PATH | {CONFIG_DIR}/showsaver.db | SQLite file for Dropout episode cache (derived, not overridable) |
| SHOW_URL | (empty) | Single URL to queue on startup |
| AUTO_CLEANUP_TMP | true | Delete temp files after processing |
| FLASK_PORT | 5000 | Flask server port |
| IS_DEBUG | false | Enables Flask debug mode and debugpy |
| WAIT_FOR_DEBUGGER | false | Pauses startup until debugger connects (port 5678) |
| SONARR_URL | (empty) | Sonarr API URL (e.g., http://localhost:8989) |
| SONARR_API_KEY | (empty) | Sonarr API key for authentication |

### Authentication
Uses `.netrc` file in `CONFIG_DIR` for site credentials. The `netrc_location` is passed to yt-dlp. A blank `.netrc` is created automatically if missing.

### Sonarr Integration
Optional integration that triggers a series rescan (and optionally rename) in Sonarr after downloading. Configure `SONARR_URL` and `SONARR_API_KEY` to enable.
- Non-blocking: Sonarr failures are logged as warnings but never cause downloads to fail
- Waits for rescan to complete before triggering rename (prevents race conditions)
- Rename is only triggered when the processor's `should_trigger_rename()` returns `True`

### File Organization
- Standard episodes: `{SHOW_DIR}/{ShowName}/Season {N}/{filename}`
- Specials: `{SHOW_DIR}/{ShowName}/Specials/{filename}`
- Colons (`:`) in titles are replaced with ` -` for filesystem compatibility
- Directory permissions: `0o777`; file permissions: `0o666`

### Docker
The `Dockerfile` uses a multi-stage build:
- **base** — production image (Python 3.14-slim + ffmpeg + gosu, runs as unprivileged `appuser` uid 1000)
- **dev** — extends base with debugpy, uses Flask dev server instead of gunicorn

`entrypoint.sh` maps `PUID`/`PGID` env vars to the container's `appuser` and fixes volume permissions before starting the app.

## Code Style

### Imports
Keep all imports in alphabetical order within each group (standard library, third-party, local).

## CI/CD

GitHub Actions workflow builds and publishes Docker image to DockerHub (`akamboj2000/show-saver:latest`) on push/PR to main.
