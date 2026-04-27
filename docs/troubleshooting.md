# Troubleshooting

## Connection Issues

### "Failed to fetch embedding"
*   **Check API URL**: Ensure `model.api_url` is correct (default: `http://localhost:1234/v1`).
*   **Check Model Server**: Verify that LM Studio or your embedding service is running and accessible.
*   **Network**: If using a remote server, check firewall settings or VPN/Wireguard status.

### "Qdrant connection refused"
*   **Check Docker**: Ensure the Qdrant container is running (`docker ps`).
*   **Check Port**: Verify Qdrant is listening on the configured port (default: `6333`).

## Indexing Issues

### Files not being indexed
*   **Extensions**: Ensure the file extension is in the supported list (defined in `indexer/watcher.py`).
*   **State**: If a file was already indexed and hasn't changed, the Indexer will skip it. Use `--verbose` to see skip logs.
*   **Ignored Paths**: Files in `.venv/` or `.git/` are automatically ignored.

## MCP Issues

### Cursor/Claude can't connect
*   **Log to stderr**: Ensure you aren't using `print()` in `server/server.py` for anything other than actual tool output. Use the provided `logger`.
*   **Absolute Paths**: When configuring MCP in your IDE, use absolute paths for both `uv` and the project directory.
