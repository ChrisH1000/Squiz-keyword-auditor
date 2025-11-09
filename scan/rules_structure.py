"""Structure validation rules for server-side JS templates.

This module implements checks to validate a server-side JavaScript
template follows the expected structure used by the project. The
StructureValidator inspects the raw file content and returns a
compact results dict that other code can convert into user-facing
issues.
"""

import logging
import re
from typing import List, Dict
from utils.text import escape_regex

logger = logging.getLogger(__name__)


class StructureValidator:
    """Validates server-side JavaScript template structure.

    The validator is driven by a rules configuration dict which
    declares the required comment blocks and script rules. The
    returned structure dictionary contains boolean flags and
    extracted metadata used by `generate_issues` to produce user
    friendly errors and fixes.
    """

    def __init__(self, rules_config: Dict):
        """Initialize structure validator.

        Args:
            rules_config: Rules configuration dict. Expected keys include
                - required_comments: mapping for top/bottom/open_div_pattern
                - script: mapping for script-related checks
        """
        self.rules = rules_config
        # Comments to look for in the template (top/bottom markers)
        self.required_comments = rules_config.get("required_comments", {})
        # Rules related to the <script runat="server"> block
        self.script_rules = rules_config.get("script", {})

    def validate_file(self, content: str) -> Dict:
        """Validate file structure and extract helpful metadata.

        The result dict contains flags (booleans) describing which
        checks passed and additional captured values such as the
        div id found inside the marker comment and the ID used by a
        getElementById call.

        Args:
            content: File content as a single string

        Returns:
            Dict containing validation flags and extracted values
        """
        results = {
            "has_top_comment": False,
            "has_open_div": False,
            "div_id": None,  # Captured div ID from comment
            "has_bottom_comment": False,
            "has_runat_server": False,
            "has_iife": False,
            "class_name": None,
            "has_constructor_assets": False,
            "has_buildTemplate": False,
            "prints_result": False,
            # None = not found, True = commented, False = uncommented
            "client_dom_line_commented": None,
            "client_dom_id": None,  # Captured ID from getElementById
            # None = not checked, True = matches, False = mismatch
            "div_id_matches": None,
        }

        # Top and bottom comment presence (simple string checks)
        results["has_top_comment"] = self._check_comments(
            content, self.required_comments.get("top", [])
        )
        results["has_bottom_comment"] = self._check_comments(
            content, self.required_comments.get("bottom", [])
        )

        # If an open_div_pattern is configured, use it to capture the div id
        div_pattern = self.required_comments.get("open_div_pattern")
        if div_pattern:
            div_match = re.search(div_pattern, content)
            if div_match:
                results["has_open_div"] = True
                # The pattern is expected to contain a capture group for the id
                results["div_id"] = div_match.group(1)

        # Check script tag existence (presence of runat="server")
        results["has_runat_server"] = self.script_rules.get("open_tag", "") in content

        # Optionally require an IIFE wrapper in the client-side code
        if self.script_rules.get("requires_iife"):
            results["has_iife"] = self._check_iife(content)

        # Optionally require a class with a known name
        class_name = self.script_rules.get("requires_class_name")
        if class_name:
            results["class_name"] = class_name if self._check_class(content, class_name) else None

        # Constructor assets initialization check (string containment)
        assets_pattern = self.script_rules.get("requires_constructor_assets_pattern")
        if assets_pattern:
            results["has_constructor_assets"] = assets_pattern in content

        # buildTemplate method presence (accept common spacing variants)
        build_method = self.script_rules.get("requires_build_method")
        if build_method:
            results["has_buildTemplate"] = f"buildTemplate()" in content or f"buildTemplate ()" in content

        # Print statement check used to ensure the template prints output
        print_statement = self.script_rules.get("requires_print")
        if print_statement:
            results["prints_result"] = print_statement in content

        # Inspect the client-side DOM line (getElementById) for commenting and id extraction
        dom_pattern = self.script_rules.get("client_dom_line_pattern")
        if dom_pattern:
            dom_result = self._check_dom_line(content, dom_pattern)
            results["client_dom_line_commented"] = dom_result["commented"]
            results["client_dom_id"] = dom_result["id"]

            # If required, check whether the div id captured from the comment
            # matches the id used in the getElementById call
            if self.script_rules.get("require_matching_div_id"):
                if results["div_id"] and results["client_dom_id"]:
                    results["div_id_matches"] = (results["div_id"] == results["client_dom_id"])

        return results

    def _check_comments(self, content: str, required_comments: List[str]) -> bool:
        """Check whether the required comment strings are present.

        This is a straightforward substring check (not regex). The
        configuration can supply the exact strings to look for, which
        allows the project to require specific opening/closing markers.
        """
        for comment in required_comments:
            # If any required comment is missing, return False
            if comment not in content:
                return False
        return True

    def _check_iife(self, content: str) -> bool:
        """Detect a minimal IIFE (immediately-invoked function expression).

        We search for common start sequences for an IIFE: (function(...) { ...
        This is intentionally lenient because code formatting may vary.
        """
        iife_patterns = [
            r'\(function\s*\([^)]*\)\s*\{',
            r'\(\s*function\s*\([^)]*\)\s*\{',
        ]

        for pattern in iife_patterns:
            if re.search(pattern, content):
                return True
        return False

    def _check_class(self, content: str, class_name: str) -> bool:
        """Check for a class definition with the expected name.

        This uses a simple regex to look for the ``class ClassName {`` pattern.
        """
        pattern = rf'class\s+{re.escape(class_name)}\s*\{{'
        return bool(re.search(pattern, content))

    def _check_dom_line(self, content: str, pattern: str) -> Dict:
        """Check if a DOM manipulation line is present, whether it's commented, and extract the ID.

        The provided pattern should capture the id used in getElementById as
        the first capture group. The function returns a dict with keys:
            - commented: None/True/False
            - id: captured id or None
        """
        result = {"commented": None, "id": None}

        # Try to find the first occurrence of the pattern in the file
        match = re.search(pattern, content)
        if not match:
            return result

        # Capture the id value from the regex groups, if present
        if match.groups():
            result["id"] = match.group(1)

        # Determine whether the matching line is commented out (//)
        lines = content.split('\n')
        for line in lines:
            if re.search(pattern, line):
                # Strip whitespace to check for leading //
                stripped = line.strip()
                if stripped.startswith('//'):
                    result["commented"] = True
                else:
                    result["commented"] = False
                break

        return result

    def generate_issues(self, structure: Dict) -> List[Dict]:
        """Convert structure validation results into a list of issues.

        Each issue contains a severity, a machine-friendly code, a
        human-readable message and a suggested fix. The consumer can
        serialize these issues into reports or print them to the user.
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
                "message": "Missing div comment with %asset_assetid%",
                "fix": "Add <!--@@ <div id=\"your-id-%asset_assetid%\"> @@--> (use any ID containing %asset_assetid%)"
            })

        # If the ID used in the template comment does not match the DOM id
        if structure.get("div_id_matches") is False:
            issues.append({
                "severity": "error",
                "code": "DIV_ID_MISMATCH",
                "message": f"Div ID '{structure['div_id']}' doesn't match getElementById ID '{structure['client_dom_id']}'",
                "fix": f"Update getElementById to use '{structure['div_id']}' or update the div comment to use '{structure['client_dom_id']}'"
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
