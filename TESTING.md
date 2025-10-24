# Testing Checklist

## Pre-requisites
- Python 3.11+ installed
- Ollama installed and running
- Models: llama3.1:8b-instruct, bge-small

## Quick Test
```bash
# Run rules-only test (no Ollama required initially)
python main.py --codebase test-templates --no-llm
```

Expected: Should find errors in invalid-template.html

## Full Test
```bash
# Run with LLM (requires Ollama)
python main.py --codebase test-templates
```

Expected: Should generate AI-powered summary

See detailed testing checklist in comments.
