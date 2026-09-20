# AGENTS.md

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
│            /debug/memory (only when ENABLE_MEMORY_PROFILING=true)
├── Background download_worker thread → processes queue via downloader.process_url()
└── Background metadata_worker thread → fills Dropout episode metadata via yt-dlp

downloader.py
├── get_metadata()         → extracts show info via yt-dlp
├── download_show()        → downloads video with SponsorBlock removal and subtitle embedding
├── copy_to_destination()  → organizes to SHOW_DIR/{ShowName}/Season {N}/
└── process_url()          → master orchestration (metadata → download → organize → Sonarr)

sonarr.py
├── Sonarr API client: rescan, rename, wait for command completion
└── is_episode_in_library()  → episode presence lookup (hasFile) behind a 60 s TTL cache

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
- `process_info_dict()` — zeroes season/episode to S00E00 for specials (TOML pattern rules) and applies the Dimension 20 / Adventuring Party season offsets
- `process_dlp_opts()` — customizes output template for special episodes
- `process_show_name()` — applies show name overrides (e.g., `'Very Important People'` → `'Very Important People (2023)'`)
- `should_trigger_rename()` — returns `True` for episodes that need Sonarr rename
- `find_corrected_url()` — returns `(url, info_dict)` when a source-specific url rewrite applies, or `None` to keep the original. `DropoutProcessor` uses it to map a bare `/videos/<slug>` Dimension 20 url onto its `dimension-20-the-complete-series/season:N/` equivalent, which is what carries a usable `season_number`.

### Metadata Caching
Episode metadata for Dropout releases is cached in SQLite at `DB_PATH` (default `{CONFIG_DIR}/showsaver.db`).

- **Table:** `dropout_episodes(url_path PK, url, show_name, title, thumbnail, duration, fetched_at, metadata_fetched_at, season_number, episode_number)`
- **Season/episode numbers:** stored as the *raw* yt-dlp values by the metadata worker. They are remapped at read time (Dimension 20 offsets, specials → S00E00) by running `DropoutProcessor.process_info_dict()` in `_annotate_in_library()`, so the offset rules live in one place and never get frozen into the DB.
- **`in_library` field:** each video in `/dropout/new-releases` carries a tri-state `in_library` computed on every request (see *Episode presence lookup* under Sonarr Integration). The frontend shows a ✓ badge on the card when `true`.
- **Scrape path:** `/dropout/new-releases` triggers `get_new_releases()`, which scrapes the public HTML, upserts scrape-time fields via `upsert_dropout_episode_basic()` (preserves any existing `show_name`), and enqueues a background `metadata_worker` job for any row still missing `show_name`.
- **Worker:** `metadata_worker` (started in `main.py`) runs yt-dlp per URL and calls `upsert_dropout_episode()` with the full row. `metadata_in_flight` (guarded by `thread_lock`) dedups concurrent enqueues.
- **Frontend polling:** `app.js` polls `/dropout/new-releases` every 2 s (up to 30 polls) until every card is settled (has a `show_name`, or `metadata_fetched_at` is set). The refresh button calls `?refresh=true`, which bypasses the scrape cache and clears the Sonarr cache. The 1 s `/queue` poller also re-fetches `/dropout/new-releases` once (unforced) whenever a job whose URL matches a visible release card reaches `completed`, so the ✓ badge appears without a manual refresh.
- **Concurrency:** WAL journal mode + `busy_timeout=5000` are set in `init_db()` so the download worker, metadata worker, and request threads can write concurrently.
- **In-memory scrape cache:** `_new_releases_cache` holds a URL list with a 5-minute TTL to avoid re-scraping on every poll; the DB is the source of truth for metadata.
- **D20 season map:** `_d20_season_cache` holds a `slug -> season` map parsed from `https://watch.dropout.tv/sitemap.xml` with a 1-hour TTL, used by `DropoutProcessor.find_corrected_url()`. A miss forces one refresh before giving up; a failed or unparseable fetch keeps the previous map rather than overwriting it.
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
| YTDLP_PROGRESS_LOG_INTERVAL | 5.0 | Minimum seconds between yt-dlp `[download]` progress log lines |
| FLASK_PORT | 5000 | Flask server port |
| IS_DEBUG | false | Enables Flask debug mode and debugpy |
| WAIT_FOR_DEBUGGER | false | Pauses startup until debugger connects (port 5678) |
| ENABLE_MEMORY_PROFILING | false | Starts `tracemalloc` and registers the `/debug/memory` diagnostic endpoint |
| SONARR_URL | (empty) | Sonarr API URL (e.g., http://localhost:8989) |
| SONARR_API_KEY | (empty) | Sonarr API key for authentication |

### Authentication
Uses `.netrc` file in `CONFIG_DIR` for site credentials. The `netrc_location` is passed to yt-dlp. A blank `.netrc` is created automatically if missing.

### Sonarr Integration
Optional integration that triggers a series rescan (and optionally rename) in Sonarr after downloading. Configure `SONARR_URL` and `SONARR_API_KEY` to enable.
- Non-blocking: Sonarr failures are logged as warnings but never cause downloads to fail
- Always waits for the rescan command to finish (`wait_for_command`, bounded to 30 s total) and then calls `clear_cache()` (which also discards any lookup still in flight), so by the time the download job is marked completed an `in_library` lookup sees the imported file. Rename, when needed, is triggered after that wait. The frontend re-fetches the badge once on completion and once more 10 s later in case the import lagged the wait.
- Rename is only triggered when the processor's `should_trigger_rename()` returns `True`

**Episode presence lookup** (`is_episode_in_library(show_name, override_name, season_number, episode_number, title)`):
- Resolves the series with the same name matching as the download path (`_match_series`: exact override → exact original → substring, case-insensitive), then fetches `GET /api/v3/episode?seriesId=` and matches on `(seasonNumber, episodeNumber)`. When either number is unknown, or the pair is the S00E00 placeholder used for specials, it falls back to a case/punctuation-insensitive title match (`text.title_match_key`).
- Never raises. Returns:
  - `True` — the matched episode has a file (`hasFile`)
  - `False` — Sonarr knows the episode but has no file
  - `None` — show name not yet resolved, Sonarr disabled, series/episode unmatched, or the lookup failed
- Series and per-series episode lists are cached in-module for `SONARR_CACHE_TTL` (60 s). The lock is not held during the HTTP call, so a slow Sonarr never stalls other callers; a `clear_cache()` during an in-flight fetch discards that fetch's result (generation counter) rather than letting stale data outlive the clear. Failures are cached too (negative caching) and read timeouts are `LOOKUP_TIMEOUT` (5 s), so an unreachable Sonarr costs at most one short stall per minute rather than one per frontend poll. `sonarr.clear_cache()` drops the cache; `get_new_releases(force_refresh=True)` calls it.

### File Organization
- Standard episodes: `{SHOW_DIR}/{ShowName}/Season {N}/{filename}`
- Specials: `{SHOW_DIR}/{ShowName}/Specials/{filename}`
- Colons (`:`) in titles are replaced with ` -` for filesystem compatibility
- Directory permissions: `0o775`; file permissions: `0o664`

### Docker
The `Dockerfile` uses a multi-stage build:
- **base** — production image (Python 3.14-slim + ffmpeg + gosu, runs as unprivileged `appuser` uid 1000)
- **dev** — extends base with debugpy, uses Flask dev server instead of gunicorn

`entrypoint.sh` maps `PUID`/`PGID` env vars to the container's `appuser` and fixes volume permissions before starting the app.

## Code Style

### Imports
Keep all imports in alphabetical order within each group (standard library, third-party, local).

## CI/CD and Releases

Workflows: [`build-and-publish-docker-image.yml`](.github/workflows/build-and-publish-docker-image.yml) (tests + Docker publish), [`release-please.yml`](.github/workflows/release-please.yml), and [`cut-release.yml`](.github/workflows/cut-release.yml) (manual **Cut Release** button — queues a release PR via an empty `Release-As:` commit, e.g. to ship a dependency refresh with no code changes). Releases are automated with [release-please](https://github.com/googleapis/release-please): merging PRs to `main` with Conventional Commit titles updates a standing "release PR" that bumps [`showsaver/version.py`](showsaver/version.py) and the changelog; merging that PR cuts the `vX.Y.Z` tag, GitHub Release, and tagged Docker images. The version is no longer edited by hand. Python dependencies are pinned in `requirements*.txt`; Dependabot pip/docker PRs use `fix(deps):` titles so merging them queues a PATCH release PR, while `github-actions` PRs stay `build(deps):` (CI-only, no release). See [RELEASING.md](RELEASING.md) for branching, Docker tag policy, and pre-release rules.
