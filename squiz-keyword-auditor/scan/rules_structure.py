"""Structure validation rules for server-side JS templates."""

import logging
import re
from typing import List, Dict, Tuple, Optional
from utils.text import escape_regex

logger = logging.getLogger(__name__)


class StructureValidator:
    """Validates server-side JavaScript template structure."""

    def __init__(self, rules_config: Dict):
        """Initialize structure validator.

        Args:
            rules_config: Rules configuration dict
        """
        self.rules = rules_config
        self.required_comments = rules_config.get("required_comments", {})
        self.script_rules = rules_config.get("script", {})

    def validate_file(self, content: str) -> Dict:
        """Validate file structure.

        Args:
            content: File content

        Returns:
            Structure validation results
        """
        results = {
            "has_top_comment": False,
            "has_open_div": False,
            "has_bottom_comment": False,
            "has_runat_server": False,
            "has_iife": False,
            "class_name": None,
            "has_constructor_assets": False,
            "has_buildTemplate": False,
            "prints_result": False,
            "client_dom_line_commented": None,  # None = not found, True = commented, False = uncommented
        }

        # Check top comments
        results["has_top_comment"] = self._check_comments(
            content, self.required_comments.get("top", [])
        )

        # Check bottom comments
        results["has_bottom_comment"] = self._check_comments(
            content, self.required_comments.get("bottom", [])
        )

        # Check div tag
        results["has_open_div"] = "super-content-events-%asset_assetid%" in content

        # Check script tag with runat="server"
        results["has_runat_server"] = self.script_rules.get("open_tag", "") in content

        # Check for IIFE pattern
        if self.script_rules.get("requires_iife"):
            results["has_iife"] = self._check_iife(content)

        # Check for class-based structure
        class_name = self.script_rules.get("requires_class_name")
        if class_name:
            results["class_name"] = class_name if self._check_class(content, class_name) else None

        # Check constructor with assets pattern
        assets_pattern = self.script_rules.get("requires_constructor_assets_pattern")
        if assets_pattern:
            results["has_constructor_assets"] = assets_pattern in content

        # Check buildTemplate method
        build_method = self.script_rules.get("requires_build_method")
        if build_method:
            results["has_buildTemplate"] = f"buildTemplate()" in content or f"buildTemplate ()" in content

        # Check print statement
        print_statement = self.script_rules.get("requires_print")
        if print_statement:
            results["prints_result"] = print_statement in content

        # Check client DOM line
        dom_pattern = self.script_rules.get("client_dom_line_pattern")
        if dom_pattern:
            results["client_dom_line_commented"] = self._check_dom_line(content, dom_pattern)

        return results

    def _check_comments(self, content: str, required_comments: List[str]) -> bool:
        """Check if required comments are present.

        Args:
            content: File content
            required_comments: List of required comment strings

        Returns:
            True if all comments found
        """
        for comment in required_comments:
            # Handle regex escaping for special chars in comments
            if comment not in content:
                return False
        return True

    def _check_iife(self, content: str) -> bool:
        """Check for IIFE pattern.

        Args:
            content: File content

        Returns:
            True if IIFE found
        """
        # Look for (function() { ... })() pattern
        iife_patterns = [
            r'\(function\s*\([^)]*\)\s*\{',
            r'\(\s*function\s*\([^)]*\)\s*\{',
        ]

        for pattern in iife_patterns:
            if re.search(pattern, content):
                return True
        return False

    def _check_class(self, content: str, class_name: str) -> bool:
        """Check for class definition.

        Args:
            content: File content
            class_name: Expected class name

        Returns:
            True if class found
        """
        # Look for class ClassName { pattern
        pattern = rf'class\s+{re.escape(class_name)}\s*\{{'
        return bool(re.search(pattern, content))

    def _check_dom_line(self, content: str, pattern: str) -> Optional[bool]:
        """Check if DOM manipulation line is commented.

        Args:
            content: File content
            pattern: Pattern to search for

        Returns:
            True if commented, False if not commented, None if not found
        """
        # Look for the pattern
        if not re.search(pattern, content):
            return None

        # Check if it's commented
        # Look for // before the pattern on the same line
        lines = content.split('\n')
        for line in lines:
            if re.search(pattern, line):
                # Check if line starts with // (after stripping whitespace)
                stripped = line.strip()
                if stripped.startswith('//'):
                    return True
                else:
                    return False

        return None

    def generate_issues(self, structure: Dict) -> List[Dict]:
        """Generate issues from structure validation results.

        Args:
            structure: Structure validation results

        Returns:
            List of issue dicts
        """
        issues = []

        if not structure["has_top_comment"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_TOP_COMMENT",
                "message": "Missing required top comment markers",
                "fix": "Add the required opening comment block at the top of the file"
            })

        if not structure["has_open_div"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_OPEN_DIV",
                "message": "Missing super-content-events div",
                "fix": "Add <!--@@ <div id=\"super-content-events-%asset_assetid%\"> @@-->"
            })

        if not structure["has_bottom_comment"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_BOTTOM_COMMENT",
                "message": "Missing <!--@@ </div> @@--> closing comment",
                "fix": "Add closing marker after </script>"
            })

        if not structure["has_runat_server"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_RUNAT_SERVER",
                "message": "Missing <script runat=\"server\"> tag",
                "fix": "Use <script runat=\"server\"> for server-side execution"
            })

        if not structure["has_iife"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_IIFE",
                "message": "Missing IIFE wrapper function",
                "fix": "Wrap code in (function() { ... })()"
            })

        if not structure["class_name"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_CLASS",
                "message": f"Missing {self.script_rules.get('requires_class_name')} class definition",
                "fix": "Define class TemplateBuilder with constructor and buildTemplate method"
            })

        if not structure["has_constructor_assets"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_CONSTRUCTOR_ASSETS",
                "message": "Constructor missing assets initialization with %globals_asset_file_contents:% pattern",
                "fix": "Initialize this.assets in constructor with %globals_asset_file_contents:<id>%"
            })

        if not structure["has_buildTemplate"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_BUILD_METHOD",
                "message": "Missing buildTemplate() method",
                "fix": "Add buildTemplate() method that returns HTML string"
            })

        if not structure["prints_result"]:
            issues.append({
                "severity": "error",
                "code": "MISSING_PRINT",
                "message": "Missing print(templateBuilder.buildTemplate()) statement",
                "fix": "Add print(templateBuilder.buildTemplate()) to output HTML"
            })

        if structure["client_dom_line_commented"] is False:
            issues.append({
                "severity": "warning",
                "code": "UNCOMMENTED_DOM_LINE",
                "message": "Client-side DOM manipulation line is not commented",
                "fix": "Comment out the document.getElementById line with //"
            })

        return issues
