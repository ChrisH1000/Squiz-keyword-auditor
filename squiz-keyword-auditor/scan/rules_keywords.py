"""Keyword extraction and validation rules."""

import logging
import re
from typing import List, Dict
from ..utils.text import extract_keywords, normalize_keyword, extract_modifiers

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extracts and analyzes Squiz keywords from code."""
    
    def __init__(self, rules_config: Dict):
        """Initialize keyword extractor.
        
        Args:
            rules_config: Rules configuration dict
        """
        self.rules = rules_config.get("keywords", {})
        self.valid_prefixes = self.rules.get("valid_prefixes", [])
    
    def extract_from_file(self, content: str) -> List[Dict]:
        """Extract all keywords from file content.
        
        Args:
            content: File content
            
        Returns:
            List of keyword info dicts
        """
        keywords = extract_keywords(content)
        results = []
        
        for keyword in keywords:
            info = self.analyze_keyword(keyword)
            results.append(info)
        
        logger.debug(f"Extracted {len(results)} keywords")
        return results
    
    def analyze_keyword(self, keyword: str) -> Dict:
        """Analyze a single keyword.
        
        Args:
            keyword: Raw keyword string
            
        Returns:
            Keyword analysis dict
        """
        normalized = normalize_keyword(keyword)
        modifiers = extract_modifiers(keyword)
        
        # Check if keyword starts with valid prefix
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
        """Validate modifier syntax and order.
        
        Args:
            keyword: Full keyword string
            modifiers: List of modifiers
            
        Returns:
            List of issues found
        """
        issues = []
        
        # Check for common mistakes
        if not modifiers:
            return issues
        
        # Check each modifier is valid format (alphanumeric + underscore)
        for modifier in modifiers:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', modifier):
                issues.append({
                    "severity": "error",
                    "code": "INVALID_MODIFIER_FORMAT",
                    "message": f"Invalid modifier format: {modifier}",
                    "fix": f"Modifier names should only contain letters, numbers, and underscores"
                })
        
        # Check for duplicate modifiers
        if len(modifiers) != len(set(modifiers)):
            issues.append({
                "severity": "warning",
                "code": "DUPLICATE_MODIFIER",
                "message": f"Duplicate modifiers found in: {keyword}",
                "fix": "Remove duplicate modifiers"
            })
        
        return issues
