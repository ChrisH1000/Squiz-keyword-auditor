"""File system scanner for finding template files."""

import logging
from pathlib import Path
from typing import List, Dict, Union

logger = logging.getLogger(__name__)

# File extensions to scan
SCAN_EXTENSIONS = [".html", ".tmpl", ".js", ".ssjs"]


class FileScanner:
    """Scans codebase for relevant template files."""

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
        """Scan codebase for template files.

        Returns:
            List of file info dicts with 'path', 'relative_path', 'content'
        """
        files = []

        for ext in SCAN_EXTENSIONS:
            pattern = f"**/*{ext}"
            logger.info(f"Scanning for {pattern}")

            for file_path in self.codebase_path.glob(pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        relative_path = file_path.relative_to(self.codebase_path)

                        files.append({
                            "path": str(file_path),
                            "relative_path": str(relative_path),
                            "content": content,
                        })
                        logger.debug(f"Loaded: {relative_path}")
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")

        logger.info(f"Found {len(files)} files to analyze")
        return files

    def get_file(self, relative_path: str) -> Dict[str, str]:
        """Get a specific file.

        Args:
            relative_path: Relative path within codebase

        Returns:
            File info dict
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
