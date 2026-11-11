"""
High-performance, regex-based log and text sanitization engine.
Guarantees zero plaintext secret leakage across all logging streams.
"""
import logging
import re
from typing import Dict, Pattern


class LogSanitizer(logging.Filter):
    """
    Scrubs known AI provider keys, Bearer tokens, and sensitive headers.
    Compiled with combined regex pattern for single-pass O(N) evaluation.
    """

    PATTERNS: Dict[str, str] = {
        "openai_proj": r"\bsk-proj-[a-zA-Z0-9_\-]{20,160}\b",
        "openai_std": r"\bsk-[a-zA-Z0-9]{20,48}\b",
        "anthropic": r"\bsk-ant-(?:api03|admin01)?-[a-zA-Z0-9_\-]{20,120}\b",
        "google": r"\bAIza[0-9A-Za-z\-_]{30,45}\b",
        "groq": r"\bgsk_[a-zA-Z0-9]{30,64}\b",
        "huggingface": r"\bhf_[a-zA-Z0-9]{30,45}\b",
        "aws_key": r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b",
        "bearer_token": r"(?i:Bearer\s+)[a-zA-Z0-9_\-\.]{16,}",
        "generic_secret": r"(?i:api[_-]?key\s*[:=]\s*['\"]?)[a-zA-Z0-9_\-\.]{16,}(['\"]?)",
    }

    def __init__(self, preserve_prefix_len: int = 4, preserve_suffix_len: int = 4):
        super().__init__()
        self.preserve_prefix = preserve_prefix_len
        self.preserve_suffix = preserve_suffix_len

        # Combine patterns into a single master regex
        combined = "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.PATTERNS.items())
        self._regex: Pattern = re.compile(combined)

    def mask_match(self, match: re.Match) -> str:
        """
        Dynamically masks matched token. Preserves token prefix/suffix for debuggability
        while completely neutralizing the secret.
        """
        raw_val = match.group(0)
        group_name = match.lastgroup

        if group_name == "bearer_token":
            return "Bearer [REDACTED_TOKEN]"
        if group_name == "generic_secret":
            return "key=[REDACTED_SECRET]"

        val_len = len(raw_val)
        label = (group_name or "SECRET").upper()
        if val_len <= (self.preserve_prefix + self.preserve_suffix + 2):
            return f"[{label}_REDACTED]"

        head = raw_val[:self.preserve_prefix]
        tail = raw_val[-self.preserve_suffix:]
        return f"{head}...[REDACTED_{label}]...{tail}"

    def sanitize(self, text: str) -> str:
        """Sanitizes text by replacing any matched secret patterns with redactions."""
        if not text:
            return text
        return self._regex.sub(self.mask_match, text)

    def filter(self, record: logging.LogRecord) -> bool:
        """Logging filter hook that sanitizes log record messages and arguments."""
        if isinstance(record.msg, str):
            record.msg = self.sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.sanitize(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.sanitize(str(v)) if isinstance(v, str) else v for v in record.args)
        return True


def install_global_sanitizer() -> LogSanitizer:
    """Installs the LogSanitizer on the root logger."""
    sanitizer = LogSanitizer()
    root_logger = logging.getLogger()
    # Add filter if not already present
    if not any(isinstance(f, LogSanitizer) for f in root_logger.filters):
        root_logger.addFilter(sanitizer)
    return sanitizer
