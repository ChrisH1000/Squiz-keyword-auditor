# Project: Squiz Matrix Keyword Auditor (RAG + Static Rules)

**Purpose**
Index official Squiz Matrix “Keyword Replacements” docs and audit a local codebase for:
1) correct keyword usage, and
2) valid server-side JavaScript class-based template structure with required comments.

**Scope**
- Crawl & embed the following docs (or use cached HTML):
  - https://matrix.squiz.net/manuals/keyword-replacements/chapters/common-keywords
  - https://matrix.squiz.net/manuals/keyword-replacements/chapters/global-keywords
  - https://matrix.squiz.net/manuals/keyword-replacements/chapters/frontend-asset-keywords
  - https://matrix.squiz.net/manuals/keyword-replacements/chapters/keyword-modifiers

- Analyse a local project folder (passed via `--codebase`) containing Squiz server-side JS templates and related HTML.

---

## 1) Objectives

- **RAG:** Provide authoritative matches (citations) for any keyword used in code: supported or not, correct syntax, relevant modifiers.
- **Static Validation:** Enforce required **server-side JS** structure & boilerplate comments.
- **Explain & Fix:** Produce short, actionable fixes for each issue (prefer **rule-based** checks; use LLM only to *summarise* findings).
- **Cost-Aware:** Default to **local models (Ollama)**; 1–3 LLM calls per run.

---

## 2) Low-Cost Mode (Defaults)

- **Models:**
  - Chat: `llama3.1:8b-instruct` (via Ollama)
  - Embeddings: `bge-small`
- **Vector Store:** `Chroma` (local file-backed)
- **Chunking:** 1200 chars, overlap 120, `k=3` neighbors
- **Heuristic-first:** Regex + AST-lite checks for structure & keyword forms
- **LLM second:** Single summarisation call per run for the final report (optional)
- **Budget caps:** `max_calls=10` (default)

---

## 3) What “Correct” Looks Like

### A) Required Boilerplate & Structure
The auditor validates that each template file that renders server-side HTML:

1. **Wrapper comments** (top & bottom, verbatim markers):
   - Top must contain:
     - `<!--@@ Keep this DIV and correspondiong close tag on page if you are running client side @@-->`
     - `<!--@@ <div id="*%asset_assetid%"> @@-->`
   - Bottom must contain:
     - `<!--@@ </div> @@-->`

2. **Server-side `<script>` block**:
   - `<script runat="server">` present
   - Uses an **IIFE** `(function(){ ... })()` to contain scope
   - **Class-based structure**:
     - `class TemplateBuilder { constructor() { this.assets = %globals_asset_file_contents:<ID>% } ... buildTemplate() { ... return html.trim(); } }`
     - `const templateBuilder = new TemplateBuilder()`
     - `print(templateBuilder.buildTemplate())` for server-side output
   - Client-side DOM line is commented (allowed):
     - `// document.getElementById('super-content-events-%asset_assetid%').innerHTML = ...`
   - **Preserve flags** comments included:
     - `// runat="server"`
     - `// type="text/javascript"`

3. **Server-side safety**:
   - No `window`/`document` usage except the **commented** client-side line
   - No network fetches, no top-level `await`
   - Returns a **string** from `buildTemplate()`, then `print(...)`

### B) Keyword Replacement Rules
- `%asset_assetid%` used consistently and only in allowed contexts
- `%globals_asset_file_contents:<id>%` syntax valid:
  - `<id>` must be numeric (or supplied per config)
  - Uses correct keyword **and** optional modifiers (e.g., `^escapehtml`, `^json_encode`, where appropriate)
- Checks common, global, and frontend-asset keywords in code:
  - **Valid:** appears in Squiz docs with matching pattern
  - **Deprecated/Unknown:** flag with doc-backed suggestions
- When modifiers are used (e.g., `^replace`, `^escapehtml`, `^striphtml`), ensure valid syntax and ordering (per docs)

---

## 4) Functional Requirements

| Area | Description |
|------|-------------|
| Doc Ingest | Download HTML (flag `--refresh-docs`) or load cached copies from `/data/squiz_docs/` |
| Embedding | Split + embed docs into Chroma; store under `/data/vectorstore/` |
| Code Scan | Walk `--codebase` for `*.html`, `*.tmpl`, `*.js`, `*.ssjs` |
| Rules Engine | Regex/AST-lite validations for structure + keyword syntax |
| RAG Lookup | For each keyword found, retrieve top-3 doc chunks + citations |
| Output | JSONL of findings per file + a Markdown summary (`reports/summary.md`) |
| Budget | Hard cap LLM calls; fail gracefully with partial results if exceeded |

---

## 5) Technical Stack

- Python 3.11
- `langchain`, `chromadb`, `ollama`, `beautifulsoup4`, `readability-lxml`, `httpx`, `regex`, `typer`, `pydantic`, `python-dotenv`

---

## 6) CLI

python squiz-keyword-auditor/main.py
–codebase ../path/to/project
–refresh-docs           # optional: re-fetch docs into cache
–rebuild                # optional: rebuild vector store
–no-llm                 # run rules only, skip summarisation
–model llama3.1:8b-instruct

---

## 7) Output Artifacts

- `reports/findings.jsonl` (one JSON per file with `issues[]`, `citations[]`)
- `reports/summary.md` (short human-readable audit with suggested fixes)
- Console exit code: `0` (no errors ≥ warn), `1` (errors present)

**Finding JSON shape**
```json
{
  "file": "templates/events.tmpl",
  "structure": {
    "has_top_comment": true,
    "has_open_div": true,
    "has_bottom_comment": false,
    "has_runat_server": true,
    "has_iife": true,
    "class_name": "TemplateBuilder",
    "has_constructor_assets": true,
    "has_buildTemplate": true,
    "prints_result": true,
    "client_dom_line_commented": true
  },
  "keywords": [
    {
      "raw": "%globals_asset_file_contents:1087883%",
      "normalized": "%globals_asset_file_contents:<id>%",
      "valid": true,
      "modifiers": [],
      "citations": [
        {"title": "Global Keywords", "url": "...", "loc": "p.2"}
      ]
    },
    {
      "raw": "%asset_assetid%",
      "valid": true,
      "citations": [...]
    }
  ],
  "issues": [
    {"severity": "error", "code": "MISSING_BOTTOM_COMMENT", "message": "Missing <!--@@ </div> @@--> closing comment", "fix": "Add closing marker after </script>."}
  ]
}
```

## 8) Acceptance Criteria
	•	✅ Runs with no paid APIs (local models by default)
	•	✅ Correctly indexes & cites the 4 Squiz docs
	•	✅ Detects structure violations (any of the required elements missing/malformed)
	•	✅ Detects invalid/unknown keywords & bad modifier syntax with citations
	•	✅ Produces reports/findings.jsonl and reports/summary.md
	•	✅ Obeys budget limits; --no-llm mode completes with rules-only results

## 9) Developer notes

/squiz-keyword-auditor/
  ├─ main.py                    # CLI: ingest -> scan -> rules -> (rag) -> report
  ├─ ingest/
  │   ├─ fetch_docs.py          # cache HTML; --refresh-docs
  │   ├─ split_embed.py         # build Chroma store; --rebuild
  ├─ scan/
  │   ├─ fs_scan.py             # file walker & loader
  │   ├─ rules_structure.py     # server-side JS + comments checks
  │   ├─ rules_keywords.py      # regex for %keywords% + modifiers
  │   └─ rules_config.json      # expected markers & patterns
  ├─ rag/
  │   ├─ retriever.py           # top-3 chunks + citations
  │   └─ summariser.py          # 1 LLM call to write summary.md
  ├─ utils/
  │   ├─ budget.py              # BudgetManager
  │   ├─ cache.py               # simple disk cache
  │   └─ text.py                # helpers (strip, normalise)
  └─ reports/

  ## 10) Test Plan (Smoke)
	•	Happy path: template with exact snippet compiles 0 errors
	•	Missing markers: remove bottom <!--@@ </div> @@--> → error flagged
	•	Bad keyword: use %globals_asset_file_content% (typo) → invalid w/ citation
	•	Modifier misuse: %asset_name^json_encode^escapehtml% (order?) → warning + fix
	•	Client-side pollution: uncomment DOM line → warn (server-side safety)
	•	No-LLM: --no-llm completes with JSON findings; summary skipped

  ---

## `/squiz-keyword-auditor/scan/rules_config.json`

```json
{
  "required_comments": {
    "top": [
      "<!--@@ Keep this DIV and correspondiong close tag on page if you are running client side @@-->",
      "<!--@@ <div id=\"super-content-events-%asset_assetid%\"> @@-->"
    ],
    "bottom": [
      "<!--@@ </div> @@-->"
    ]
  },
  "script": {
    "open_tag": "<script runat=\"server\">",
    "requires_iife": true,
    "requires_class_name": "TemplateBuilder",
    "requires_constructor_assets_pattern": "%globals_asset_file_contents:",
    "requires_build_method": "buildTemplate",
    "requires_print": "print(templateBuilder.buildTemplate())",
    "client_dom_line_pattern": "document.getElementById\\('super-content-events-%asset_assetid% '\\)\\.innerHTML",
    "client_dom_line_must_be_commented": true,
    "forbid_globals": ["window\\.", "(?<!//\\s)document\\."]
  },
  "keywords": {
    "valid_prefixes": [
      "%asset_", "%globals_", "%frontend_asset_"
    ],
    "modifiers_prefix": "^",
    "examples": [
      "%asset_assetid%",
      "%globals_asset_file_contents:<id>%",
      "%asset_name%",
      "%asset_url%",
      "%frontend_asset_types%"
    ]
  }
}