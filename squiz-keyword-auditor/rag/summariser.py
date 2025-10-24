"""LLM-based summary generator for audit reports."""

import logging
from typing import List, Dict
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from ..utils.budget import BudgetManager

logger = logging.getLogger(__name__)


class ReportSummariser:
    """Generates human-readable audit summaries using LLM."""
    
    def __init__(
        self,
        model_name: str = "llama3.1:8b-instruct",
        budget_manager: BudgetManager = None,
    ):
        """Initialize summariser.
        
        Args:
            model_name: Ollama model name
            budget_manager: Optional budget manager
        """
        self.model_name = model_name
        self.budget_manager = budget_manager or BudgetManager()
        
        # Initialize LLM
        logger.info(f"Initializing Ollama chat model: {model_name}")
        self.llm = ChatOllama(model=model_name, temperature=0)
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technical documentation expert. 
Create a concise, actionable audit report summary from the provided findings.
Focus on:
1. Total files scanned
2. Critical errors by category
3. Most common issues
4. Actionable recommendations

Format as clear markdown with sections."""),
            ("human", "Create a summary report for these audit findings:\n\n{findings_json}")
        ])
        
        self.chain = self.prompt | self.llm
    
    def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
        """Generate summary from all findings.
        
        Args:
            all_findings: List of all file findings
            no_llm: If True, skip LLM and generate rules-only summary
            
        Returns:
            Markdown summary text
        """
        if no_llm:
            return self._generate_rules_summary(all_findings)
        
        # Check budget
        if not self.budget_manager.can_call("summary"):
            logger.warning("Budget exceeded, falling back to rules-only summary")
            return self._generate_rules_summary(all_findings)
        
        # Generate stats for context
        stats = self._compute_stats(all_findings)
        
        # Prepare findings for LLM
        findings_text = self._prepare_findings_text(all_findings, stats)
        
        try:
            logger.info("Generating LLM summary...")
            response = self.chain.invoke({"findings_json": findings_text})
            self.budget_manager.record_call("summary")
            
            summary = response.content if hasattr(response, 'content') else str(response)
            return summary
            
        except Exception as e:
            logger.error(f"LLM summary failed: {e}")
            return self._generate_rules_summary(all_findings)
    
    def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
        """Generate summary without LLM using rules only.
        
        Args:
            all_findings: List of all file findings
            
        Returns:
            Markdown summary text
        """
        stats = self._compute_stats(all_findings)
        
        summary = f"""# Squiz Keyword Auditor Report

## Summary
- **Files Scanned**: {stats['total_files']}
- **Files with Errors**: {stats['files_with_errors']}
- **Total Errors**: {stats['total_errors']}
- **Total Warnings**: {stats['total_warnings']}

## Issue Breakdown

### Structure Issues
"""
        
        # Structure issues
        for code, count in stats['structure_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"
        
        summary += "\n### Keyword Issues\n"
        
        # Keyword issues
        for code, count in stats['keyword_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"
        
        summary += f"""
## Top Issues

"""
        # Top issues
        for issue_code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:5]:
            summary += f"1. **{issue_code}**: {count} files affected\n"
        
        summary += """
## Recommendations

1. Fix critical structure issues first (missing comments, IIFE, class structure)
2. Validate all keywords against Squiz Matrix documentation
3. Ensure all client-side DOM manipulation is commented out
4. Review modifier usage for correctness

## Next Steps

Run the auditor with `--no-llm` flag removed for detailed AI-powered analysis.
"""
        
        return summary
    
    def _compute_stats(self, all_findings: List[Dict]) -> Dict:
        """Compute statistics from findings.
        
        Args:
            all_findings: List of all file findings
            
        Returns:
            Stats dict
        """
        stats = {
            'total_files': len(all_findings),
            'files_with_errors': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'structure_issues': {},
            'keyword_issues': {},
            'all_issues': {},
        }
        
        for finding in all_findings:
            issues = finding.get('issues', [])
            if issues:
                stats['files_with_errors'] += 1
            
            for issue in issues:
                code = issue.get('code', 'UNKNOWN')
                severity = issue.get('severity', 'error')
                
                if severity == 'error':
                    stats['total_errors'] += 1
                elif severity == 'warning':
                    stats['total_warnings'] += 1
                
                # Categorize issue
                if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                    stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                else:
                    stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1
                
                stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1
        
        return stats
    
    def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
        """Prepare findings for LLM.
        
        Args:
            all_findings: List of all file findings
            stats: Computed statistics
            
        Returns:
            Text representation of findings
        """
        text = f"""Statistics:
- Total files: {stats['total_files']}
- Files with errors: {stats['files_with_errors']}
- Total errors: {stats['total_errors']}
- Total warnings: {stats['total_warnings']}

Top Issues:
"""
        for code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:10]:
            text += f"- {code}: {count}\n"
        
        text += "\nSample Issues:\n"
        
        # Include sample issues from first few files
        for finding in all_findings[:3]:
            if finding.get('issues'):
                text += f"\nFile: {finding['file']}\n"
                for issue in finding['issues'][:3]:
                    text += f"  - [{issue['severity'].upper()}] {issue['code']}: {issue['message']}\n"
        
        return text
