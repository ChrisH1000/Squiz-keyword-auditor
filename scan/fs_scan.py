"""File system scanner for finding template files.

This module provides a simple FileScanner that searches a codebase
directory for relevant template files (HTML, .tmpl, server JS). The
scanner returns a list of dictionaries containing the absolute path,
relative path and file content which the rest of the auditor consumes.
"""

import logging
from pathlib import Path
from typing import List, Dict, Union

logger = logging.getLogger(__name__)

# File extensions considered templates for the auditor
SCAN_EXTENSIONS = [".html", ".tmpl", ".js", ".ssjs"]


class FileScanner:
    """Scans a codebase directory for template files.

    The scanner is intentionally simple: it globs for known extensions
    and reads files using UTF-8. Failures to read individual files are
    logged but do not stop the scan.
    """

    def __init__(self, codebase_path: Union[str, Path]):
        """Initialize file scanner.

        Args:
            codebase_path: Path to codebase root
        """
        self.codebase_path = Path(codebase_path)
        if not self.codebase_path.exists():
            raise ValueError(f"Codebase path does not exist: {codebase_path}")

        logger.info(f"Initialized scanner for: {self.codebase_path}")

    def scan(self) -> List[Dict[str, str]]:
        """Scan codebase for template files and return file info.

        Returns:
            List of dicts with keys: path, relative_path, content
        """
        files = []

        for ext in SCAN_EXTENSIONS:
            pattern = f"**/*{ext}"
            logger.info(f"Scanning for {pattern}")

            for file_path in self.codebase_path.glob(pattern):
                if file_path.is_file():
                    try:
                        # Read file content (UTF-8) and capture metadata
                        content = file_path.read_text(encoding="utf-8")
                        relative_path = file_path.relative_to(self.codebase_path)

                        files.append({
                            "path": str(file_path),
                            "relative_path": str(relative_path),
                            "content": content,
                        })
                        logger.debug(f"Loaded: {relative_path}")
                    except Exception as e:
                        # Log and continue on individual file read errors
                        logger.warning(f"Failed to read {file_path}: {e}")

        logger.info(f"Found {len(files)} files to analyze")
        return files

    def get_file(self, relative_path: str) -> Dict[str, str]:
        """Return a single file's content and metadata by relative path.

        This helper is used by external tools or tests to fetch a single
        template without performing a full scan.
        """
        file_path = self.codebase_path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        content = file_path.read_text(encoding="utf-8")

        return {
            "path": str(file_path),
            "relative_path": relative_path,
            "content": content,
        }
