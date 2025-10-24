"""Text processing utilities."""

import re
from typing import List, Optional


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized whitespace
    """
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Replace multiple newlines with double newline
    text = re.sub(r'\n\n+', '\n\n', text)
    return text.strip()


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text.
    
    Args:
        text: HTML text
        
    Returns:
        Text without HTML tags
    """
    return re.sub(r'<[^>]+>', '', text)


def extract_keywords(text: str) -> List[str]:
    """Extract Squiz keyword patterns from text.
    
    Args:
        text: Text to search
        
    Returns:
        List of found keywords
    """
    # Pattern to match %keyword% style replacements
    pattern = r'%[a-zA-Z_][a-zA-Z0-9_]*(?::[^%]+)?(?:\^[a-zA-Z_]+)*%'
    return re.findall(pattern, text)


def normalize_keyword(keyword: str) -> str:
    """Normalize a keyword for comparison.
    
    Replaces numeric IDs and variable parts with placeholders.
    
    Args:
        keyword: Raw keyword string
        
    Returns:
        Normalized keyword pattern
    """
    # Replace numeric IDs with <id> placeholder
    normalized = re.sub(r':\d+', ':<id>', keyword)
    return normalized


def extract_modifiers(keyword: str) -> List[str]:
    """Extract modifiers from a keyword.
    
    Args:
        keyword: Keyword with potential modifiers
        
    Returns:
        List of modifier names
    """
    # Extract everything after ^ characters
    modifiers = []
    parts = keyword.split('^')
    if len(parts) > 1:
        # Skip first part (the keyword itself)
        for part in parts[1:]:
            # Remove trailing %
            modifier = part.rstrip('%')
            if modifier:
                modifiers.append(modifier)
    return modifiers


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_code_snippet(code: str) -> str:
    """Clean and normalize code snippet.
    
    Args:
        code: Code snippet
        
    Returns:
        Cleaned code
    """
    # Remove excessive blank lines
    lines = code.split('\n')
    cleaned_lines = []
    prev_blank = False
    
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        cleaned_lines.append(line)
        prev_blank = is_blank
    
    return '\n'.join(cleaned_lines).strip()


def escape_regex(text: str) -> str:
    """Escape special regex characters.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for regex
    """
    return re.escape(text)


def find_line_number(full_text: str, search_text: str) -> Optional[int]:
    """Find the line number where text appears.
    
    Args:
        full_text: Full text to search
        search_text: Text to find
        
    Returns:
        Line number (1-indexed) or None if not found
    """
    lines = full_text.split('\n')
    for i, line in enumerate(lines, 1):
        if search_text in line:
            return i
    return None
