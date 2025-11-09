#!/usr/bin/env python3
"""Squiz Matrix Keyword Auditor - Main CLI entry point.

This script wires together the auditor pipeline:
- fetch Squiz documentation and cache it
- build or load a persistent vector store of documentation chunks
- scan a provided codebase for templates
- validate structure and keywords for each file
- generate reports (JSONL + markdown summary)

The CLI is implemented with Typer and supports flags to control
document refresh, vector rebuilds and whether to use the LLM.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from dotenv import load_dotenv
import os

# Import our modules
from ingest.fetch_docs import DocFetcher
from ingest.split_embed import VectorStoreBuilder
from scan.fs_scan import FileScanner
from scan.rules_keywords import KeywordExtractor
from scan.rules_structure import StructureValidator
from rag.retriever import KeywordRetriever
from rag.summariser import ReportSummariser
from utils.budget import BudgetManager

# Load environment variables from .env
load_dotenv()

# Setup logging to use rich for prettier tracebacks
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# Rich console for nicer CLI output
console = Console()

# Typer CLI app
app = typer.Typer(
    name="squiz-keyword-auditor",
    help="Audit Squiz Matrix templates for keyword usage and server-side JS structure",
    add_completion=False,
)


def load_rules_config() -> dict:
    """Load rules configuration JSON used by extractors/validators.

    The configuration drives structure and keyword validation behavior
    and is deliberately read at runtime so it can be edited without
    changing code.
    """
    config_path = Path(__file__).parent / "scan" / "rules_config.json"
    with open(config_path) as f:
        return json.load(f)


@app.command()
def main(
    codebase: str = typer.Option(
        ...,
        "--codebase",
        help="Path to codebase to audit"
    ),
    refresh_docs: bool = typer.Option(
        False,
        "--refresh-docs",
        help="Re-download documentation (ignore cache)"
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Rebuild vector store from scratch"
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Skip LLM summarization (rules only)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Ollama model name (default from .env)"
    ),
    max_calls: int = typer.Option(
        None,
        "--max-calls",
        help="Maximum LLM calls (default from .env)"
    ),
):
    """Run the Squiz keyword auditor pipeline.

    The function follows clear steps (fetch -> build -> scan -> analyze -> report)
    and uses the rules configuration to control validations. Errors are
    collected and written to a reports directory for inspection.
    """

    console.print("[bold blue]Squiz Matrix Keyword Auditor[/bold blue]\n")

    # Load runtime configuration from environment variables (with defaults)
    cache_dir = os.getenv("CACHE_DIR", "./data/squiz_docs")
    vector_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/vectorstore")
    embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-small")
    llm_model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")
    chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
    retrieval_k = int(os.getenv("RETRIEVAL_K", "3"))
    max_llm_calls = max_calls or int(os.getenv("MAX_LLM_CALLS", "10"))

    # Budget manager tracks LLM usage across the run
    budget = BudgetManager(max_calls=max_llm_calls)

    # Load rules configuration for validators/extractors
    console.print("[yellow]Loading rules configuration...[/yellow]")
    rules_config = load_rules_config()

    try:
        # Step 1: Fetch documentation (cached) - this populates the docs list
        console.print("[yellow]Step 1: Fetching Squiz documentation...[/yellow]")
        with DocFetcher(cache_dir) as fetcher:
            docs = fetcher.fetch_all(refresh=refresh_docs)
        console.print(f"[green]✓[/green] Fetched {len(docs)} documentation pages\n")

        # Step 2: Build or load vector store used for RAG retrievals
        console.print("[yellow]Step 2: Building vector store...[/yellow]")
        vector_builder = VectorStoreBuilder(
            persist_dir=vector_dir,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        vector_store = vector_builder.build(docs, rebuild=rebuild)
        console.print(f"[green]✓[/green] Vector store ready\n")

        # Step 3: Discover files to analyze in the provided codebase
        console.print(f"[yellow]Step 3: Scanning codebase: {codebase}[/yellow]")
        scanner = FileScanner(codebase)
        files = scanner.scan()
        console.print(f"[green]✓[/green] Found {len(files)} files\n")

        if not files:
            console.print("[red]No files found to audit![/red]")
            raise typer.Exit(code=1)

        # Step 4: Analyze files using structure validator and keyword checks
        console.print("[yellow]Step 4: Analyzing files...[/yellow]")

        # Initialize pipeline components using loaded rules
        structure_validator = StructureValidator(rules_config)
        keyword_extractor = KeywordExtractor(rules_config)
        keyword_retriever = KeywordRetriever(vector_store, k=retrieval_k)

        all_findings = []

        for file_info in files:
            console.print(f"  Analyzing: {file_info['relative_path']}")

            content = file_info['content']

            # Validate file structure and generate structural issues
            structure = structure_validator.validate_file(content)
            structure_issues = structure_validator.generate_issues(structure)

            # Extract keywords and validate via RAG lookups
            keywords = keyword_extractor.extract_from_file(content)
            validated_keywords = keyword_retriever.validate_keywords(keywords)

            # Convert invalid keywords and modifier problems into issue dicts
            keyword_issues = []
            for kw in validated_keywords:
                if not kw.get('valid'):
                    keyword_issues.append({
                        "severity": "error",
                        "code": "INVALID_KEYWORD",
                        "message": f"Unknown or invalid keyword: {kw['raw']}",
                        "fix": f"Check Squiz Matrix documentation for correct keyword syntax"
                    })

                # Validate modifier syntax and append any issues
                if kw.get('modifiers'):
                    modifier_issues = keyword_extractor.validate_modifier_syntax(
                        kw['raw'], kw['modifiers']
                    )
                    keyword_issues.extend(modifier_issues)

            # Combine all issues for the file and append to findings
            all_issues = structure_issues + keyword_issues

            finding = {
                "file": file_info['relative_path'],
                "structure": structure,
                "keywords": validated_keywords,
                "issues": all_issues,
            }

            all_findings.append(finding)

        console.print(f"[green]✓[/green] Analysis complete\n")

        # Step 5: Persist results and create a human-readable summary
        console.print("[yellow]Step 5: Generating reports...[/yellow]")

        reports_dir = Path("./reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        findings_file = reports_dir / "findings.jsonl"
        with open(findings_file, 'w') as f:
            for finding in all_findings:
                f.write(json.dumps(finding) + '\n')
        console.print(f"[green]✓[/green] Findings written to {findings_file}")

        # Use the LLM summariser (or use a local rules-only fallback)
        if not no_llm:
            summariser = ReportSummariser(model_name=llm_model, budget_manager=budget)
            summary = summariser.generate_summary(all_findings, no_llm=no_llm)
        else:
            # Produce a deterministic rules-only summary here to avoid
            # depending on internal/private summariser methods which may
            # be in an inconsistent state during development.
            def _rules_only_summary(findings: list) -> str:
                total_files = len(findings)
                files_with_errors = sum(1 for f in findings if f.get('issues'))
                total_errors = sum(1 for f in findings for i in f.get('issues', []) if i.get('severity') == 'error')
                total_warnings = sum(1 for f in findings for i in f.get('issues', []) if i.get('severity') == 'warning')

                structure_issues = {}
                keyword_issues = {}
                all_issues = {}

                for f in findings:
                    for issue in f.get('issues', []):
                        code = issue.get('code', 'UNKNOWN')
                        severity = issue.get('severity', 'error')
                        if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                            structure_issues[code] = structure_issues.get(code, 0) + 1
                        else:
                            keyword_issues[code] = keyword_issues.get(code, 0) + 1
                        all_issues[code] = all_issues.get(code, 0) + 1

                summary_lines = [
                    "# Squiz Keyword Auditor Report",
                    "",
                    "## Summary",
                    f"- **Files Scanned**: {total_files}",
                    f"- **Files with Errors**: {files_with_errors}",
                    f"- **Total Errors**: {total_errors}",
                    f"- **Total Warnings**: {total_warnings}",
                    "",
                    "## Issue Breakdown",
                    "",
                    "### Structure Issues",
                ]

                for code, count in structure_issues.items():
                    summary_lines.append(f"- `{code}`: {count} occurrences")

                summary_lines.append("\n### Keyword Issues")
                for code, count in keyword_issues.items():
                    summary_lines.append(f"- `{code}`: {count} occurrences")

                summary_lines.append("\n## Top Issues")
                for issue_code, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True)[:5]:
                    summary_lines.append(f"1. **{issue_code}**: {count} files affected")

                summary_lines.extend([
                    "",
                    "## Recommendations",
                    "1. Fix critical structure issues first (missing comments, IIFE, class structure)",
                    "2. Validate all keywords against Squiz Matrix documentation",
                    "3. Ensure all client-side DOM manipulation is commented out",
                    "4. Review modifier usage for correctness",
                    "",
                    "## Next Steps",
                    "Run the auditor without the `--no-llm` flag for an AI-powered summary if Ollama is available.",
                ])

                return "\n".join(summary_lines)

            summary = _rules_only_summary(all_findings)

        summary_file = reports_dir / "summary.md"
        summary_file.write_text(summary)
        console.print(f"[green]✓[/green] Summary written to {summary_file}\n")

        console.print("[bold]Audit Results:[/bold]")
        console.print(summary)

        # Exit non-zero if any errors were found
        has_errors = any(
            any(issue['severity'] == 'error' for issue in finding['issues'])
            for finding in all_findings
        )

        if has_errors:
            console.print("\n[red]✗ Audit found errors[/red]")
            raise typer.Exit(code=1)
        else:
            console.print("\n[green]✓ No errors found![/green]")
            raise typer.Exit(code=0)

    except Exception as e:
        # Any unhandled exception is logged and the CLI exits with code 1
        console.print(f"\n[red]Error: {e}[/red]")
        logger.exception("Fatal error during audit")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
