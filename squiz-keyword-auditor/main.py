#!/usr/bin/env python3
"""Squiz Matrix Keyword Auditor - Main CLI entry point."""

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

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()

# Initialize Typer app
app = typer.Typer(
    name="squiz-keyword-auditor",
    help="Audit Squiz Matrix templates for keyword usage and server-side JS structure",
    add_completion=False,
)


def load_rules_config() -> dict:
    """Load rules configuration."""
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
    """Run the Squiz keyword auditor."""
    
    console.print("[bold blue]Squiz Matrix Keyword Auditor[/bold blue]\n")
    
    # Get configuration from environment
    cache_dir = os.getenv("CACHE_DIR", "./squiz-keyword-auditor/data/squiz_docs")
    vector_dir = os.getenv("CHROMA_PERSIST_DIR", "./squiz-keyword-auditor/data/vectorstore")
    embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-small")
    llm_model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")
    chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
    retrieval_k = int(os.getenv("RETRIEVAL_K", "3"))
    max_llm_calls = max_calls or int(os.getenv("MAX_LLM_CALLS", "10"))
    
    # Initialize budget manager
    budget = BudgetManager(max_calls=max_llm_calls)
    
    # Load rules configuration
    console.print("[yellow]Loading rules configuration...[/yellow]")
    rules_config = load_rules_config()
    
    try:
        # Step 1: Fetch documentation
        console.print("[yellow]Step 1: Fetching Squiz documentation...[/yellow]")
        with DocFetcher(cache_dir) as fetcher:
            docs = fetcher.fetch_all(refresh=refresh_docs)
        console.print(f"[green]✓[/green] Fetched {len(docs)} documentation pages\n")
        
        # Step 2: Build vector store
        console.print("[yellow]Step 2: Building vector store...[/yellow]")
        vector_builder = VectorStoreBuilder(
            persist_dir=vector_dir,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        vector_store = vector_builder.build(docs, rebuild=rebuild)
        console.print(f"[green]✓[/green] Vector store ready\n")
        
        # Step 3: Scan codebase
        console.print(f"[yellow]Step 3: Scanning codebase: {codebase}[/yellow]")
        scanner = FileScanner(codebase)
        files = scanner.scan()
        console.print(f"[green]✓[/green] Found {len(files)} files\n")
        
        if not files:
            console.print("[red]No files found to audit![/red]")
            raise typer.Exit(code=1)
        
        # Step 4: Analyze files
        console.print("[yellow]Step 4: Analyzing files...[/yellow]")
        
        # Initialize validators and extractors
        structure_validator = StructureValidator(rules_config)
        keyword_extractor = KeywordExtractor(rules_config)
        keyword_retriever = KeywordRetriever(vector_store, k=retrieval_k)
        
        all_findings = []
        
        for file_info in files:
            console.print(f"  Analyzing: {file_info['relative_path']}")
            
            content = file_info['content']
            
            # Validate structure
            structure = structure_validator.validate_file(content)
            structure_issues = structure_validator.generate_issues(structure)
            
            # Extract and validate keywords
            keywords = keyword_extractor.extract_from_file(content)
            validated_keywords = keyword_retriever.validate_keywords(keywords)
            
            # Check for invalid keywords
            keyword_issues = []
            for kw in validated_keywords:
                if not kw.get('valid'):
                    keyword_issues.append({
                        "severity": "error",
                        "code": "INVALID_KEYWORD",
                        "message": f"Unknown or invalid keyword: {kw['raw']}",
                        "fix": f"Check Squiz Matrix documentation for correct keyword syntax"
                    })
                
                # Check modifier syntax
                if kw.get('modifiers'):
                    modifier_issues = keyword_extractor.validate_modifier_syntax(
                        kw['raw'], kw['modifiers']
                    )
                    keyword_issues.extend(modifier_issues)
            
            # Combine all issues
            all_issues = structure_issues + keyword_issues
            
            # Create finding
            finding = {
                "file": file_info['relative_path'],
                "structure": structure,
                "keywords": validated_keywords,
                "issues": all_issues,
            }
            
            all_findings.append(finding)
        
        console.print(f"[green]✓[/green] Analysis complete\n")
        
        # Step 5: Generate reports
        console.print("[yellow]Step 5: Generating reports...[/yellow]")
        
        # Ensure reports directory exists
        reports_dir = Path("./squiz-keyword-auditor/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Write JSONL findings
        findings_file = reports_dir / "findings.jsonl"
        with open(findings_file, 'w') as f:
            for finding in all_findings:
                f.write(json.dumps(finding) + '\n')
        console.print(f"[green]✓[/green] Findings written to {findings_file}")
        
        # Generate summary
        if not no_llm:
            summariser = ReportSummariser(model_name=llm_model, budget_manager=budget)
            summary = summariser.generate_summary(all_findings, no_llm=no_llm)
        else:
            # Use rules-only summary
            from rag.summariser import ReportSummariser
            temp_summariser = ReportSummariser()
            summary = temp_summariser._generate_rules_summary(all_findings)
        
        # Write summary
        summary_file = reports_dir / "summary.md"
        summary_file.write_text(summary)
        console.print(f"[green]✓[/green] Summary written to {summary_file}\n")
        
        # Step 6: Display results
        console.print("[bold]Audit Results:[/bold]")
        console.print(summary)
        
        # Exit code based on errors
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
        console.print(f"\n[red]Error: {e}[/red]")
        logger.exception("Fatal error during audit")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
