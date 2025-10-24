# Squiz Matrix Keyword Auditor

A LangChain-powered tool to audit Squiz Matrix templates for:
- Correct keyword replacement usage with RAG-based validation
- Valid server-side JavaScript class-based template structure
- Required boilerplate comments and safety patterns

## Features

- **RAG-Powered Validation**: Indexes official Squiz Matrix documentation and validates keywords with citations
- **Static Rules Engine**: Enforces server-side JS structure requirements
- **Local-First**: Uses Ollama by default (no API keys required)
- **Cost-Aware**: Budget limits on LLM calls
- **Detailed Reports**: JSONL findings + Markdown summary

## Prerequisites

1. **Python 3.11+**
2. **Ollama** installed and running:
   ```bash
   # Install Ollama: https://ollama.ai
   
   # Pull required models
   ollama pull llama3.1:8b-instruct
   ollama pull bge-small
   ```

## Installation

```bash
# Clone the repository
git clone git@github.com:ChrisH1000/Squiz-keyword-auditor.git
cd Squiz-keyword-auditor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python squiz-keyword-auditor/main.py --codebase /path/to/your/project
```

### Options

```bash
python squiz-keyword-auditor/main.py \
  --codebase /path/to/project \
  --refresh-docs           # Re-download Squiz docs (ignore cache)
  --rebuild                # Rebuild vector store from scratch
  --no-llm                 # Skip LLM summarization (rules only)
  --model llama3.1:8b      # Override Ollama model
  --max-calls 10           # Maximum LLM calls (budget limit)
```

### Examples

**Full audit with AI summary:**
```bash
python squiz-keyword-auditor/main.py --codebase ./templates
```

**Rules-only (no LLM):**
```bash
python squiz-keyword-auditor/main.py --codebase ./templates --no-llm
```

**Refresh documentation and rebuild vector store:**
```bash
python squiz-keyword-auditor/main.py \
  --codebase ./templates \
  --refresh-docs \
  --rebuild
```

## Configuration

Edit `.env` to customize settings:

```bash
# Ollama Configuration (local models - no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct
OLLAMA_EMBEDDING_MODEL=bge-small

# Vector Store Configuration
CHROMA_PERSIST_DIR=./squiz-keyword-auditor/data/vectorstore
CHUNK_SIZE=1200
CHUNK_OVERLAP=120
RETRIEVAL_K=3

# Budget Configuration
MAX_LLM_CALLS=10

# Cache Configuration
CACHE_DIR=./squiz-keyword-auditor/data/squiz_docs
```

## What It Validates

### Server-Side JavaScript Structure

The auditor checks for the following required structure:

1. **Top Comments** (exact match required):
   ```html
   <!--@@ Keep this DIV and correspondiong close tag on page if you are running client side @@-->
   <!--@@ <div id="super-content-events-%asset_assetid%"> @@-->
   ```

2. **Server-Side Script Tag**:
   ```html
   <script runat="server">
   ```

3. **IIFE Wrapper**:
   ```javascript
   (function() {
     // Your code here
   })()
   ```

4. **Class-Based Structure**:
   ```javascript
   class TemplateBuilder {
     constructor() {
       this.assets = %globals_asset_file_contents:12345%;
     }
     
     buildTemplate() {
       // Build HTML here
       return html.trim();
     }
   }
   
   const templateBuilder = new TemplateBuilder();
   print(templateBuilder.buildTemplate());
   ```

5. **Client-Side Line Commented**:
   ```javascript
   // document.getElementById('super-content-events-%asset_assetid%').innerHTML = ...
   ```

6. **Bottom Comment**:
   ```html
   <!--@@ </div> @@-->
   ```

### Keyword Validation

- Validates all `%keyword%` patterns against official Squiz documentation
- Checks modifier syntax (e.g., `^escapehtml`, `^json_encode`)
- Provides citations from documentation
- Flags unknown/deprecated keywords

## Output

The auditor generates two files in `squiz-keyword-auditor/reports/`:

1. **`findings.jsonl`**: Detailed JSON findings for each file
2. **`summary.md`**: Human-readable Markdown summary

### Exit Codes

- `0`: No errors found
- `1`: Errors found or execution failed

## Project Structure

```
squiz-keyword-auditor/
├── main.py                    # CLI entry point
├── ingest/
│   ├── fetch_docs.py          # Download & cache docs
│   └── split_embed.py         # Build vector store
├── scan/
│   ├── fs_scan.py             # File scanner
│   ├── rules_keywords.py      # Keyword extraction
│   ├── rules_structure.py     # Structure validation
│   └── rules_config.json      # Validation rules
├── rag/
│   ├── retriever.py           # RAG keyword lookup
│   └── summariser.py          # LLM summarization
├── utils/
│   ├── budget.py              # Budget manager
│   ├── cache.py               # Disk cache
│   └── text.py                # Text utilities
└── data/
    ├── squiz_docs/            # Cached HTML docs
    └── vectorstore/           # ChromaDB storage
```

## Documentation Sources

The auditor indexes these official Squiz Matrix pages:

- [Common Keywords](https://matrix.squiz.net/manuals/keyword-replacements/chapters/common-keywords)
- [Global Keywords](https://matrix.squiz.net/manuals/keyword-replacements/chapters/global-keywords)
- [Frontend Asset Keywords](https://matrix.squiz.net/manuals/keyword-replacements/chapters/frontend-asset-keywords)
- [Keyword Modifiers](https://matrix.squiz.net/manuals/keyword-replacements/chapters/keyword-modifiers)

## Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Model Not Found

```bash
# Pull the required models
ollama pull llama3.1:8b-instruct
ollama pull bge-small
```

### ChromaDB Issues

```bash
# Rebuild vector store
python squiz-keyword-auditor/main.py --codebase ./templates --rebuild
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/
```

### Adding New Rules

Edit `squiz-keyword-auditor/scan/rules_config.json` to add or modify validation rules.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

## Author

Built with LangChain, Ollama, and ChromaDB.
