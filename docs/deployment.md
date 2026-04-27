# Deployment Guide

Hivemind can be deployed as a background service on Linux (`systemd`) or macOS (`launchd`).

## Systemd (Linux)

Create a service file at `/etc/systemd/system/hivemind-indexer.service`:

```ini
[Unit]
Description=Hivemind Code Indexer
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/hivemind
ExecStart=/usr/local/bin/uv run python main.py indexer start /path/to/your/codebase
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable hivemind-indexer
sudo systemctl start hivemind-indexer
```

## PM2 (Node.js Process Manager)

If you prefer PM2:
```bash
pm2 start "uv run python main.py indexer start /path/to/code" --name hivemind-indexer
pm2 start "uv run python main.py api" --name hivemind-api
```

## Docker

While the core logic runs locally, the database (Qdrant) should be run in Docker. See `infra/compose.yml`.
To run the entire Hivemind stack in Docker, you can create a custom `Dockerfile` based on `python:3.12-slim`.
