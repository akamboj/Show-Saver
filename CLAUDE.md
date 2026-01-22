# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Show-Saver is a Flask-based video downloader that queues and processes video downloads using yt-dlp. It provides a web interface for managing downloads and automatically organizes them into a TV show library structure (ShowName/Season N/episode.ext).

## Commands

### Development with Docker (Recommended)
```bash
docker compose -f compose.dev.yaml up --build
```

### Local Python Development
```bash
pip install -r requirements.txt
python showsaver/main.py
```

The Flask app runs on http://localhost:5000.

### VS Code
- Use the "Python Run script" launch configuration for debugging
- VS Code tasks are available for docker-compose build/up

## Architecture

```
Flask Web Server (main.py)
├── Routes: /, /submit, /status/<job_id>, /queue
└── Background download_worker thread → processes queue via downloader.process_url()

downloader.py
├── get_metadata() → extracts show info via yt-dlp
├── download_show() → downloads video with embedded subtitles to TMP_DIR
└── copy_to_destination() → organizes to SHOW_DIR/{ShowName}/Season {N}/

env.py
└── Environment configuration (CONFIG_DIR, SHOW_DIR, TMP_DIR, etc.)
```

### Download Flow
1. URL submitted via POST /submit → added to queue with job ID
2. Background worker picks up job, updates status to "downloading"
3. yt-dlp extracts metadata, downloads video with subtitle embedding
4. File copied to organized path: `{SHOW_DIR}/{series}/Season {N}/{episode}.ext`
5. Temp file cleaned up if AUTO_CLEANUP_TMP=true

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| CONFIG_DIR | /config | Stores urls.txt and .netrc for auth |
| SHOW_DIR | /tvshows | Final destination for organized episodes |
| TMP_DIR | /tmp | Temporary download directory |
| SHOW_URL | (empty) | Single URL to queue on startup |
| AUTO_CLEANUP_TMP | true | Delete temp files after processing |
| PORT | 5000 | Flask server port |
| SONARR_URL | (empty) | Sonarr API URL (e.g., http://localhost:8989) |
| SONARR_API_KEY | (empty) | Sonarr API key for authentication |

### Authentication
Uses `.netrc` file in CONFIG_DIR for site credentials. The netrc_location is passed to yt-dlp.

### Show Name Overrides
`SHOW_NAME_OVERRIDES` dict in downloader.py maps metadata names to corrected folder names (e.g., 'Very Important People' → 'Very Important People (2023)').

### Sonarr Integration
Optional integration that triggers a series rescan in Sonarr after downloading. Configure `SONARR_URL` and `SONARR_API_KEY` to enable. The integration is non-blocking - Sonarr failures are logged as warnings but never cause downloads to fail.

## CI/CD

GitHub Actions workflow builds and publishes Docker image to DockerHub (`akamboj2000/show-saver:latest`) on push/PR to main.
