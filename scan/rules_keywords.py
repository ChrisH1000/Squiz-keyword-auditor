"""Keyword extraction and validation rules.

This module is responsible for identifying Squiz Matrix-style
keywords in template content and performing light syntax checks on
any modifiers. It intentionally separates extraction from validation
so the RAG-based validation can be performed by `KeywordRetriever`.
"""

import logging
import re
from typing import List, Dict
from utils.text import extract_keywords, normalize_keyword, extract_modifiers

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extracts and analyzes Squiz keywords from code.

    The extractor uses utility helpers from `utils.text` to find
    keyword tokens and to normalise them for lookup. It also exposes
    a simple modifier-syntax checker used to raise warnings/errors
    about invalid modifier usage.
    """

    def __init__(self, rules_config: Dict):
        """Initialize keyword extractor from rules config.

        Args:
            rules_config: Rules configuration dict that may include
                          valid keyword prefixes and other settings.
        """
        self.rules = rules_config.get("keywords", {})
        self.valid_prefixes = self.rules.get("valid_prefixes", [])

    def extract_from_file(self, content: str) -> List[Dict]:
        """Extract all keywords from a file content string.

        Returns a list of dictionaries containing the raw token,
        a normalised form, extracted modifiers and placeholders for
        future validation/citations.
        """
        keywords = extract_keywords(content)
        results = []

        for keyword in keywords:
            info = self.analyze_keyword(keyword)
            results.append(info)

        logger.debug(f"Extracted {len(results)} keywords")
        return results

    def analyze_keyword(self, keyword: str) -> Dict:
        """Analyze a single keyword token and return structured info.

        The returned dict includes:
            - raw: original token
            - normalized: token stripped of modifiers and surrounding %
            - modifiers: list of modifier tokens (if any)
            - has_valid_prefix: quick check against known prefixes
            - valid/citations: placeholders to be filled by RAG
        """
        normalized = normalize_keyword(keyword)
        modifiers = extract_modifiers(keyword)

        # Quick prefix check to mark obviously-unknown keywords
        has_valid_prefix = any(
            keyword.startswith(prefix) for prefix in self.valid_prefixes
        )

        return {
            "raw": keyword,
            "normalized": normalized,
            "modifiers": modifiers,
            "has_valid_prefix": has_valid_prefix,
            "valid": None,  # Will be determined by RAG lookup
            "citations": [],  # Will be populated by RAG
        }

    def validate_modifier_syntax(self, keyword: str, modifiers: List[str]) -> List[Dict]:
        """Validate modifier syntax and return a list of issues.

        Checks performed:
          - Each modifier matches a simple identifier regex
          - Duplicates are warned about

        Returns a list of issue dicts with severity/code/message/fix
        suitable for inclusion in the final report.
        """
        issues = []

        # No modifiers -> nothing to validate
        if not modifiers:
            return issues

        # Ensure each modifier is a valid identifier
        for modifier in modifiers:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', modifier):
                issues.append({
                    "severity": "error",
                    "code": "INVALID_MODIFIER_FORMAT",
                    "message": f"Invalid modifier format: {modifier}",
                    "fix": f"Modifier names should only contain letters, numbers, and underscores"
                })

        # Warn if duplicate modifiers are present
        if len(modifiers) != len(set(modifiers)):
            issues.append({
                "severity": "warning",
                "code": "DUPLICATE_MODIFIER",
                "message": f"Duplicate modifiers found in: {keyword}",
                "fix": "Remove duplicate modifiers"
            })

        return issues
