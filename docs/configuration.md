# Configuration Reference

Hivemind uses Pydantic Settings for flexible and type-safe configuration.

## Configuration Methods

Settings are loaded in the following order of precedence:

1.  **Environment Variables**: Prefixed with `HIVEMIND_`.
2.  **YAML File**: `config.yaml` in the current working directory.
3.  **Defaults**: Defined in `core/config.py`.

### Environment Variables
Nested settings are accessed using double underscores `__`.
Example: `HIVEMIND_QDRANT__URL="http://192.168.1.100:6333"`

## Settings Schema

### Qdrant
| Key | Default | Description |
|-----|---------|-------------|
| `url` | `http://localhost:6333` | URL of the Qdrant instance. |
| `api_key` | `null` | API Key for Qdrant (if enabled). |
| `collection_name` | `hivemind_code` | Name of the collection in Qdrant. |

### Model
| Key | Default | Description |
|-----|---------|-------------|
| `api_url` | `http://localhost:1234/v1` | URL of the OpenAI-compatible embedding API. |
| `model_name` | `qwen3-4B-embedding` | Name of the model to use. |
| `api_key` | `hivemind` | API Key for the embedding service. |
| `embedding_dim` | `2500` | Dimension of the generated vectors. |

### Chunking
| Key | Default | Description |
|-----|---------|-------------|
| `strategy` | `by_size` | Strategy to use: `by_size` or `by_lines`. |
| `language_aware` | `true` | Enable AST-aware chunking (where supported). |
| `by_size.chunk_size` | `500` | Target character size per chunk. |
| `by_size.overlap` | `50` | Character overlap between chunks. |
| `by_lines.chunk_lines` | `50` | Number of lines per chunk. |
| `by_lines.overlap_lines` | `5` | Line overlap between chunks. |

### API
| Key | Default | Description |
|-----|---------|-------------|
| `host` | `0.0.0.0` | Host to bind the REST API. |
| `port` | `8001` | Port for the REST API. |
| `cors_origins` | `["*"]` | Allowed CORS origins. |

### State
| Key | Default | Description |
|-----|---------|-------------|
| `directory` | `~/.hivemind` | Directory for state files and logs. |

### Security
| Key | Default | Description |
|-----|---------|-------------|
| `secret_file` | `~/.hivemind/secrets.yaml` | Path to secrets file. |
| `api_key_header` | `X-API-Key` | Header name for REST API authentication. |
