# TV Manager + Sonarr Queue Cleaner

A combined Flask web app and automated maintenance tool for:
- Managing processed TV show folders
- Copying Plex artwork PNGs into video folders
- Cleaning Deluge torrents
- Clearing failed/manual Sonarr queue items

## Environment Variables

| Variable | Description | Default |
|-----------|-------------|----------|
| BASE_DIR | Path to TV shows directory | `/tv` |
| PROCESSED_DIR_FILE | File to store processed directory list | `/data/processed_directories.json` |
| PNG_FILE | PNG image to copy into each video directory | `plex.png` |
| DELUGE_HOST | Deluge RPC hostname | `localhost` |
| DELUGE_PORT | Deluge RPC port | `58846` |
| DELUGE_USER | Deluge RPC username | `localclient` |
| DELUGE_PASS | Deluge RPC password | *(blank)* |
| SONARR_URL | Sonarr base URL | `http://localhost:8989` |
| SONARR_API_KEY | Sonarr API key | *(required)* |
| SONARR_MIN_AGE | Minutes failed/manual Sonarr items must exist before deletion | `120` |

## Ports
- Web UI: `5555`

## Example Docker Run

```bash
docker run -d \
  --name=tvmanager \
  -p 5555:5555 \
  -e SONARR_URL="http://192.168.0.156:8989" \
  -e SONARR_API_KEY="YOUR_KEY" \
  -e DELUGE_HOST="192.168.0.156" \
  -v /mnt/user/tv:/tv \
  -v /mnt/user/appdata/tvmanager:/data \
  wjm896/tvmanager:latest
