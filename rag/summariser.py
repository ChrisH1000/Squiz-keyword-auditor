"""LLM-based summary generator for audit reports.

Provides a lazy-initialising summariser that produces either an LLM-
generated summary (when Ollama is available) or a deterministic
rules-only markdown summary used for offline/testing runs.

Optional imports are guarded so the module can be imported even when
Ollama or LangChain components aren't installed.
"""

import logging
from typing import List, Dict

try:
    from langchain_ollama import ChatOllama
    from langchain_core.prompts import ChatPromptTemplate
except Exception:
    ChatOllama = None
    ChatPromptTemplate = None

from utils.budget import BudgetManager

logger = logging.getLogger(__name__)


class ReportSummariser:
    """Generate a markdown summary for audit findings using LLM or rules.

    The class initialises LLM components lazily, and exposes a
    deterministic `_generate_rules_summary` method for offline runs.
    """

    def __init__(self, model_name: str = "llama3.1:8b-instruct", budget_manager: BudgetManager = None):
        self.model_name = model_name
        self.budget_manager = budget_manager or BudgetManager()
        self.llm = None
        """LLM-based summary generator for audit reports.

        This module provides a compact, single implementation of ReportSummariser
        that supports both LLM-driven summaries and a deterministic rules-only
        fallback. It replaces a previously corrupted/duplicated version.
        """

        import logging
        from typing import List, Dict

        try:
            from langchain_ollama import ChatOllama
            from langchain_core.prompts import ChatPromptTemplate
        except Exception:
            ChatOllama = None
            ChatPromptTemplate = None

        from utils.budget import BudgetManager

        logger = logging.getLogger(__name__)


        class ReportSummariser:
            """LLM-backed or rules-only report summariser.

            The class initialises LLM resources lazily and ensures a stable
            rules-only fallback is always available via `_generate_rules_summary`.
            """

            def __init__(self, model_name: str = "llama3.1:8b-instruct", budget_manager: BudgetManager = None):
                self.model_name = model_name
                self.budget_manager = budget_manager or BudgetManager()
                self.llm = None
                self.prompt = None
                self.chain = None

            def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
                if no_llm:
                    return self._generate_rules_summary(all_findings)

                if not self.budget_manager.can_call("summary"):
                    logger.warning("Budget exceeded; using rules-only summary")
                    return self._generate_rules_summary(all_findings)

                if self.llm is None:
                    if ChatOllama is None or ChatPromptTemplate is None:
                        logger.error("Ollama not available; using rules-only summary")
                        return self._generate_rules_summary(all_findings)

                    logger.info(f"Initializing Ollama chat model: {self.model_name}")
                    self.llm = ChatOllama(model=self.model_name, temperature=0)
                    self.prompt = ChatPromptTemplate.from_messages([
                        ("system", """You are a technical documentation expert.
        Create a concise, actionable audit report summary from the provided findings.
        Focus on: total files scanned, critical errors by category, most common issues, and actionable recommendations.
        Format as clear markdown with sections."""),
                        ("human", "Create a summary report for these audit findings:\n\n{findings_json}")
                    ])
                    self.chain = self.prompt | self.llm

                stats = self._compute_stats(all_findings)
                findings_text = self._prepare_findings_text(all_findings, stats)

                try:
                    logger.info("Generating LLM summary...")
                    response = self.chain.invoke({"findings_json": findings_text})
                    self.budget_manager.record_call("summary")
                    return response.content if hasattr(response, "content") else str(response)
                except Exception as e:
                    logger.error("LLM summary failed: %s", e)
                    return self._generate_rules_summary(all_findings)

            def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
                stats = self._compute_stats(all_findings)

                parts = [
                    "# Squiz Keyword Auditor Report",
                    "",
                    "## Summary",
                    f"- **Files Scanned**: {stats['total_files']}",
                    f"- **Files with Errors**: {stats['files_with_errors']}",
                    f"- **Total Errors**: {stats['total_errors']}",
                    f"- **Total Warnings**: {stats['total_warnings']}",
                    "",
                    "## Issue Breakdown",
                    "",
                    "### Structure Issues",
                ]

                for code, count in stats['structure_issues'].items():
                    parts.append(f"- `{code}`: {count} occurrences")

                parts.append("\n### Keyword Issues")
                for code, count in stats['keyword_issues'].items():
                    parts.append(f"- `{code}`: {count} occurrences")

                parts.append("\n## Top Issues")
                for issue_code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    parts.append(f"1. **{issue_code}**: {count} files affected")

                parts.extend([
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

                return "\n".join(parts)

            def _compute_stats(self, all_findings: List[Dict]) -> Dict:
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

                        if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                            stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                        else:
                            stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                        stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

                return stats

            def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
                lines = [
                    "Statistics:",
                    f"- Total files: {stats['total_files']}",
                    f"- Files with errors: {stats['files_with_errors']}",
                    f"- Total errors: {stats['total_errors']}",
                    f"- Total warnings: {stats['total_warnings']}",
                    "",
                    "Top Issues:",
                ]

                for code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:10]:
                    lines.append(f"- {code}: {count}")

                lines.append("\nSample Issues:")
                for finding in all_findings[:3]:
                    if finding.get('issues'):
                        lines.append(f"\nFile: {finding.get('file', '<unknown>')}")
                        for issue in finding['issues'][:3]:
                            lines.append(f"  - [{issue.get('severity','ERROR').upper()}] {issue.get('code','UNKNOWN')}: {issue.get('message','')}")

                return "\n".join(lines)
        # Lazy-initialised fields
        self.llm = None
        self.prompt = None
        self.chain = None

    def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
        """Return a markdown summary for the provided findings.

        If `no_llm` is True, returns a deterministic rules-only summary and
        does not touch any external services.
        """
        if no_llm:
            return self._generate_rules_summary(all_findings)

        if not self.budget_manager.can_call("summary"):
            logger.warning("Budget exceeded; falling back to rules-only summary")
            return self._generate_rules_summary(all_findings)

        # Initialise Ollama components lazily. If optional imports are not
        # available, fall back to the rules-only path.
        if self.llm is None:
            if ChatOllama is None or ChatPromptTemplate is None:
                logger.error("Ollama or prompt template unavailable; using rules-only summary")
                return self._generate_rules_summary(all_findings)

            logger.info(f"Initializing Ollama chat model: {self.model_name}")
            self.llm = ChatOllama(model=self.model_name, temperature=0)
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a technical documentation expert.
Create a concise, actionable audit report summary from the provided findings.
Focus on: total files scanned, critical errors by category, most common issues, and actionable recommendations.
Format as clear markdown with sections."""),
                ("human", "Create a summary report for these audit findings:\n\n{findings_json}")
            ])
            self.chain = self.prompt | self.llm

        stats = self._compute_stats(all_findings)
        findings_text = self._prepare_findings_text(all_findings, stats)

        try:
            logger.info("Generating LLM summary...")
            response = self.chain.invoke({"findings_json": findings_text})
            self.budget_manager.record_call("summary")

            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.error("LLM summary failed: %s", e)
            return self._generate_rules_summary(all_findings)

    def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
        """Create a deterministic markdown summary without calling an LLM."""
        stats = self._compute_stats(all_findings)

        lines = [
            "# Squiz Keyword Auditor Report",
            "",
            "## Summary",
            f"- **Files Scanned**: {stats['total_files']}",
            f"- **Files with Errors**: {stats['files_with_errors']}",
            f"- **Total Errors**: {stats['total_errors']}",
            f"- **Total Warnings**: {stats['total_warnings']}",
            "",
            "## Issue Breakdown",
            "",
            "### Structure Issues",
        ]

        for code, count in stats['structure_issues'].items():
            lines.append(f"- `{code}`: {count} occurrences")

        lines.append("\n### Keyword Issues")
        for code, count in stats['keyword_issues'].items():
            lines.append(f"- `{code}`: {count} occurrences")

        lines.append("\n## Top Issues")
        for issue_code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"1. **{issue_code}**: {count} files affected")

        lines.extend([
            "",
            "## Recommendations",
            "",
            "1. Fix critical structure issues first (missing comments, IIFE, class structure)",
            "2. Validate all keywords against Squiz Matrix documentation",
            "3. Ensure all client-side DOM manipulation is commented out",
            "4. Review modifier usage for correctness",
            "",
            "## Next Steps",
            "",
            "Run the auditor without the `--no-llm` flag for an AI-powered summary if Ollama is available.",
        ])

        return "\n".join(lines)

    def _compute_stats(self, all_findings: List[Dict]) -> Dict:
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

                if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                    stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                else:
                    stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

        return stats

    def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
        text_lines = [
            "Statistics:",
            f"- Total files: {stats['total_files']}",
            f"- Files with errors: {stats['files_with_errors']}",
            f"- Total errors: {stats['total_errors']}",
            f"- Total warnings: {stats['total_warnings']}",
            "",
            "Top Issues:",
        ]

        for code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:10]:
            text_lines.append(f"- {code}: {count}")

        text_lines.append("\nSample Issues:")
        for finding in all_findings[:3]:
            if finding.get('issues'):
                text_lines.append(f"\nFile: {finding.get('file', '<unknown>')}")
                for issue in finding['issues'][:3]:
                    text_lines.append(f"  - [{issue.get('severity','ERROR').upper()}] {issue.get('code','UNKNOWN')}: {issue.get('message','')}")

        return "\n".join(text_lines)
"""LLM-based summary generator for audit reports.

This module provides a small, lazy-initialising summariser that can
produce either an LLM-crafted summary (when Ollama is available) or a
deterministic rules-only markdown report suitable for offline runs.

The previous file contained duplicate/corrupted content which caused
an AttributeError when the CLI attempted to call the rules-only
generator. This file replaces that content with a single clean class
definition.
"""

import logging
from typing import List, Dict

try:
    # Optional imports; allow running without Ollama installed
    from langchain_ollama import ChatOllama
    from langchain_core.prompts import ChatPromptTemplate
except Exception:
    ChatOllama = None
    ChatPromptTemplate = None

from utils.budget import BudgetManager

logger = logging.getLogger(__name__)


class ReportSummariser:
    """Generate a human-readable audit summary using an LLM or rules.

    The class initialises LLM components lazily so creating an instance
    doesn't require Ollama to be running. Callers can request a
    rules-only summary using the `no_llm` flag.
    """

    def __init__(self, model_name: str = "llama3.1:8b-instruct", budget_manager: BudgetManager = None):
        self.model_name = model_name
        self.budget_manager = budget_manager or BudgetManager()

        # Lazy-initialised LLM artifacts
        self.llm = None
        self.prompt = None
        self.chain = None

    def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
        """Return a markdown summary for the provided findings.

        If `no_llm` is True, a deterministic rules-only summary is returned
        without touching any external services.
        """
        if no_llm:
            return self._generate_rules_summary(all_findings)

        if not self.budget_manager.can_call("summary"):
            logger.warning("Budget exceeded; falling back to rules-only summary")
            return self._generate_rules_summary(all_findings)

        # Initialise Ollama chat chain lazily. If imports are missing,
        # or Ollama isn't available, fall back to rules-only output.
        if self.llm is None:
            if ChatOllama is None or ChatPromptTemplate is None:
                logger.error("Ollama or prompt template unavailable; using rules-only summary")
                return self._generate_rules_summary(all_findings)

            logger.info(f"Initializing Ollama chat model: {self.model_name}")
            self.llm = ChatOllama(model=self.model_name, temperature=0)
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a technical documentation expert.
Create a concise, actionable audit report summary from the provided findings.
Focus on: total files scanned, critical errors by category, most common issues, and actionable recommendations.
Format as clear markdown with sections."""),
                ("human", "Create a summary report for these audit findings:\n\n{findings_json}")
            ])
            self.chain = self.prompt | self.llm

        stats = self._compute_stats(all_findings)
        findings_text = self._prepare_findings_text(all_findings, stats)

        try:
            logger.info("Generating LLM summary...")
            response = self.chain.invoke({"findings_json": findings_text})
            self.budget_manager.record_call("summary")

            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.error("LLM summary failed: %s", e)
            return self._generate_rules_summary(all_findings)

    def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
        """Deterministic markdown summary used when LLM isn't available."""
        stats = self._compute_stats(all_findings)

        lines = [
            "# Squiz Keyword Auditor Report",
            "",
            "## Summary",
            f- "- **Files Scanned**: {stats['total_files']}",
            f- "- **Files with Errors**: {stats['files_with_errors']}",
            f- "- **Total Errors**: {stats['total_errors']}",
            f- "- **Total Warnings**: {stats['total_warnings']}",
            "",
            "## Issue Breakdown",
            "",
            "### Structure Issues",
        ]

        for code, count in stats['structure_issues'].items():
            lines.append(f"- `{code}`: {count} occurrences")

        lines.append("\n### Keyword Issues")
        for code, count in stats['keyword_issues'].items():
            lines.append(f"- `{code}`: {count} occurrences")

        lines.append("\n## Top Issues")
        for issue_code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"1. **{issue_code}**: {count} files affected")

        lines.extend([
            "",
            "## Recommendations",
            "",
            "1. Fix critical structure issues first (missing comments, IIFE, class structure)",
            "2. Validate all keywords against Squiz Matrix documentation",
            "3. Ensure all client-side DOM manipulation is commented out",
            "4. Review modifier usage for correctness",
            "",
            "## Next Steps",
            "",
            "Run the auditor with `--no-llm` flag removed for detailed AI-powered analysis.",
        ])

        return "\n".join(lines)

    def _compute_stats(self, all_findings: List[Dict]) -> Dict:
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

                if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                    stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                else:
                    stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

        return stats

    def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
        text = [
            f"Statistics:",
            f"- Total files: {stats['total_files']}",
            f"- Files with errors: {stats['files_with_errors']}",
            f"- Total errors: {stats['total_errors']}",
            f"- Total warnings: {stats['total_warnings']}",
            "",
            "Top Issues:",
        ]

        for code, count in sorted(stats['all_issues'].items(), key=lambda x: x[1], reverse=True)[:10]:
            text.append(f"- {code}: {count}")

        text.append("\nSample Issues:")
        for finding in all_findings[:3]:
            if finding.get('issues'):
                text.append(f"\nFile: {finding.get('file', '<unknown>')}")
                for issue in finding['issues'][:3]:
                    text.append(f"  - [{issue.get('severity','ERROR').upper()}] {issue.get('code','UNKNOWN')}: {issue.get('message','')}")

        return "\n".join(text)
"""LLM-based summary generator for audit reports.

This module wraps a small LLM pipeline (ChatOllama + prompt template)
to generate a concise markdown summary of audit findings. It also
provides a rules-only fallback so the project can work without LLMs
or when a budget limit is reached.
"""

import logging
from typing import List, Dict
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from utils.budget import BudgetManager

logger = logging.getLogger(__name__)


class ReportSummariser:
    """Generates human-readable audit summaries using an LLM.

    LLM resources are initialized lazily — creating an instance does not
    require Ollama to be running unless `generate_summary` is called
    with `no_llm=False`.
    """

    def __init__(
        self,
        model_name: str = "llama3.1:8b-instruct",
        budget_manager: BudgetManager = None,
    ):
        """Create a summariser instance.

        Args:
            model_name: Ollama model identifier used for chat completions
            budget_manager: Optional BudgetManager to limit LLM calls
        """
        self.model_name = model_name
        self.budget_manager = budget_manager or BudgetManager()

        # Defer LLM/prompt initialization until needed
        self.llm = None
        self.prompt = None
        self.chain = None

    def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
        """Generate a markdown summary for the provided findings.

        If `no_llm` is True, a deterministic rules-only summary is
        returned without initializing any external LLM clients.
        """
        if no_llm:
            return self._generate_rules_summary(all_findings)

        # Enforce budget limits for LLM usage
        if not self.budget_manager.can_call("summary"):
            logger.warning("Budget exceeded, falling back to rules-only summary")
            return self._generate_rules_summary(all_findings)

        # Lazily initialize LLM components so tests and no-LLM callers
        # don't require Ollama to be running during object construction
        if self.llm is None:
            logger.info(f"Initializing Ollama chat model: {self.model_name}")
            self.llm = ChatOllama(model=self.model_name, temperature=0)
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

        stats = self._compute_stats(all_findings)
        findings_text = self._prepare_findings_text(all_findings, stats)

        try:
            logger.info("Generating LLM summary...")
            response = self.chain.invoke({"findings_json": findings_text})
            self.budget_manager.record_call("summary")

            # ChatOllama returns an object with a .content attribute; handle both
            summary = response.content if hasattr(response, 'content') else str(response)
            return summary

        except Exception as e:
            logger.error(f"LLM summary failed: {e}")
            return self._generate_rules_summary(all_findings)

    def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
        """Produce a concise markdown report without calling an LLM.

        This function aggregates issue counts and renders a deterministic
        markdown summary suitable for offline runs and testing.
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

        for code, count in stats['structure_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"

        summary += "\n### Keyword Issues\n"
        for code, count in stats['keyword_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"

        summary += f"""
## Top Issues

"""

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
        """Compute aggregate statistics from the findings list."""
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

                if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                    stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                else:
                    stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

        return stats

    def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
        """Convert findings and stats into a compact text blob for the LLM."""
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

        for finding in all_findings[:3]:
            if finding.get('issues'):
                text += f"\nFile: {finding['file']}\n"
                for issue in finding['issues'][:3]:
                    text += f"  - [{issue['severity'].upper()}] {issue['code']}: {issue['message']}\n"

        return text
"""LLM-based summary generator for audit reports.

This module wraps a small LLM pipeline (ChatOllama + prompt template)
to generate a concise markdown summary of audit findings. It also
provides a rules-only fallback so the project can work without LLMs
or when a budget limit is reached.
"""

import logging
from typing import List, Dict
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from utils.budget import BudgetManager

logger = logging.getLogger(__name__)


class ReportSummariser:
    """Generates human-readable audit summaries using an LLM.

    The class exposes a single public method `generate_summary` which
    will either call the LLM or produce a rules-based summary if the
    budget is exceeded or `no_llm=True` is passed.
    """

    def __init__(
        self,
        model_name: str = "llama3.1:8b-instruct",
        budget_manager: BudgetManager = None,
    ):
        """Create a summariser instance.

        Args:
            model_name: Ollama model identifier used for chat completions
            budget_manager: Optional BudgetManager to limit LLM calls
        """
        self.model_name = model_name
        self.budget_manager = budget_manager or BudgetManager()

        # Initialize the Ollama chat client with deterministic settings
        logger.info(f"Initializing Ollama chat model: {model_name}")
        self.llm = ChatOllama(model=model_name, temperature=0)

        # Prompt template instructs the model how to format the report
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

        # Compose pipeline: prompt -> llm
        self.chain = self.prompt | self.llm

    def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
        """Generate a markdown summary for the provided findings.

        The method first checks whether a rules-only summary was requested
        or whether the budget allows an LLM call. It falls back to the
        rules-only generator in case of budget exhaustion or LLM failures.
        """
        if no_llm:
            return self._generate_rules_summary(all_findings)

        # Enforce budget limits for LLM usage
        if not self.budget_manager.can_call("summary"):
            logger.warning("Budget exceeded, falling back to rules-only summary")
            return self._generate_rules_summary(all_findings)

        stats = self._compute_stats(all_findings)
        findings_text = self._prepare_findings_text(all_findings, stats)

        try:
            logger.info("Generating LLM summary...")
            response = self.chain.invoke({"findings_json": findings_text})
            self.budget_manager.record_call("summary")

            # ChatOllama returns an object with a .content attribute; handle both
            summary = response.content if hasattr(response, 'content') else str(response)
            return summary

        except Exception as e:
            # On any failure, return a deterministic rules-based summary
            logger.error(f"LLM summary failed: {e}")
            return self._generate_rules_summary(all_findings)

    def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
        """Produce a concise markdown report without calling an LLM.

        This function aggregates the issues counts and renders a
        human-readable markdown summary suitable for offline use.
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

        # List structure issues and keyword issues with counts
        for code, count in stats['structure_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"

        summary += "\n### Keyword Issues\n"
        for code, count in stats['keyword_issues'].items():
            summary += f"- `{code}`: {count} occurrences\n"

        summary += f"""
## Top Issues

"""

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
        """Compute aggregate statistics from the findings list.

        Returns a dict containing total counts and categorized issue counts
        used by both the LLM prompt and the rules-only summary generator.
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

                # Heuristic categorization of structure vs keyword issues
                if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                    stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                else:
                    stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

        return stats

    def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
        """Convert findings and stats into a compact text blob for the LLM.

        The function includes a short list of top issues and sample issues
        so the model has concrete examples to summarize.
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

        # Add a few example issues from the first few files for context
        for finding in all_findings[:3]:
            if finding.get('issues'):
                text += f"\nFile: {finding['file']}\n"
                for issue in finding['issues'][:3]:
                    text += f"  - [{issue['severity'].upper()}] {issue['code']}: {issue['message']}\n"

        return text
"""LLM-based summary generator for audit reports."""

import logging
from typing import List, Dict
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from utils.budget import BudgetManager

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
        """LLM-based summary generator for audit reports.

        This module wraps a small LLM pipeline (ChatOllama + prompt template)
        to generate a concise markdown summary of audit findings. It also
        provides a rules-only fallback so the project can work without LLMs
        or when a budget limit is reached.
        """

        import logging
        from typing import List, Dict
        from langchain_ollama import ChatOllama
        from langchain_core.prompts import ChatPromptTemplate

        from utils.budget import BudgetManager

        logger = logging.getLogger(__name__)


        class ReportSummariser:
            """Generates human-readable audit summaries using an LLM.

            The class exposes a single public method `generate_summary` which
            will either call the LLM or produce a rules-based summary if the
            budget is exceeded or `no_llm=True` is passed.
            """

            def __init__(
                self,
                model_name: str = "llama3.1:8b-instruct",
                budget_manager: BudgetManager = None,
            ):
                """Create a summariser instance.

                Args:
                    model_name: Ollama model identifier used for chat completions
                    budget_manager: Optional BudgetManager to limit LLM calls
                """
                self.model_name = model_name
                self.budget_manager = budget_manager or BudgetManager()

                # Initialize the Ollama chat client with deterministic settings
                logger.info(f"Initializing Ollama chat model: {model_name}")
                self.llm = ChatOllama(model=model_name, temperature=0)

                # Prompt template instructs the model how to format the report
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

                # Compose pipeline: prompt -> llm
                self.chain = self.prompt | self.llm

            def generate_summary(self, all_findings: List[Dict], no_llm: bool = False) -> str:
                """Generate a markdown summary for the provided findings.

                The method first checks whether a rules-only summary was requested
                or whether the budget allows an LLM call. It falls back to the
                rules-only generator in case of budget exhaustion or LLM failures.
                """
                if no_llm:
                    return self._generate_rules_summary(all_findings)

                # Enforce budget limits for LLM usage
                if not self.budget_manager.can_call("summary"):
                    logger.warning("Budget exceeded, falling back to rules-only summary")
                    return self._generate_rules_summary(all_findings)

                stats = self._compute_stats(all_findings)
                findings_text = self._prepare_findings_text(all_findings, stats)

                try:
                    logger.info("Generating LLM summary...")
                    response = self.chain.invoke({"findings_json": findings_text})
                    self.budget_manager.record_call("summary")

                    # ChatOllama returns an object with a .content attribute; handle both
                    summary = response.content if hasattr(response, 'content') else str(response)
                    return summary

                except Exception as e:
                    # On any failure, return a deterministic rules-based summary
                    logger.error(f"LLM summary failed: {e}")
                    return self._generate_rules_summary(all_findings)

            def _generate_rules_summary(self, all_findings: List[Dict]) -> str:
                """Produce a concise markdown report without calling an LLM.

                This function aggregates the issues counts and renders a
                human-readable markdown summary suitable for offline use.
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

                # List structure issues and keyword issues with counts
                for code, count in stats['structure_issues'].items():
                    summary += f"- `{code}`: {count} occurrences\n"

                summary += "\n### Keyword Issues\n"
                for code, count in stats['keyword_issues'].items():
                    summary += f"- `{code}`: {count} occurrences\n"

                summary += f"""
        ## Top Issues

        """

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
                """Compute aggregate statistics from the findings list.

                Returns a dict containing total counts and categorized issue counts
                used by both the LLM prompt and the rules-only summary generator.
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

                        # Heuristic categorization of structure vs keyword issues
                        if code.startswith('MISSING_') or code.startswith('UNCOMMENTED_'):
                            stats['structure_issues'][code] = stats['structure_issues'].get(code, 0) + 1
                        else:
                            stats['keyword_issues'][code] = stats['keyword_issues'].get(code, 0) + 1

                        stats['all_issues'][code] = stats['all_issues'].get(code, 0) + 1

                return stats

            def _prepare_findings_text(self, all_findings: List[Dict], stats: Dict) -> str:
                """Convert findings and stats into a compact text blob for the LLM.

                The function includes a short list of top issues and sample issues
                so the model has concrete examples to summarize.
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

                # Add a few example issues from the first few files for context
                for finding in all_findings[:3]:
                    if finding.get('issues'):
                        text += f"\nFile: {finding['file']}\n"
                        for issue in finding['issues'][:3]:
                            text += f"  - [{issue['severity'].upper()}] {issue['code']}: {issue['message']}\n"

                return text
