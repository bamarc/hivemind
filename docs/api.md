# REST API Reference

The Hivemind REST API provides programmatic access to search and embedding features.

## Authentication
If configured, requests must include the API key in the header defined by `security.api_key_header` (default: `X-API-Key`).

## Endpoints

### `GET /health`
Returns detailed health status of the system.
**Response**:
```json
{
  "status": "healthy",
  "components": {
    "qdrant": { "status": "connected", "collection": "hivemind_code" },
    "embedder": { "status": "connected", "model": "qwen3-4B-embedding" },
    "version": "0.2.0"
  }
}
```

### `POST /embed`
Generates a vector embedding for the provided text.
**Request**:
```json
{
  "text": "code snippet or query"
}
```

### `POST /search`
Performs a semantic search.
**Request**:
```json
{
  "query": "how do I handle auth?",
  "limit": 5
}
```

### `GET /metrics`
Returns system metrics.
**Response**:
```json
{
  "indexed_files_total": 1234,
  "total_chunks_in_db": 5678,
  "version": "0.2.0"
}
```
