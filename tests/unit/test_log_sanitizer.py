"""
Unit tests for LogSanitizer and secret scrubbing filter.
"""
import logging
from brahmastra.infrastructure.security.log_sanitizer import (
    LogSanitizer,
    install_global_sanitizer,
)


def test_log_sanitizer_masks_openai_key():
    """Verify OpenAI project key is masked preserving prefix/suffix."""
    sanitizer = LogSanitizer()
    fake_key = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz"
    raw_text = f"Connecting with key: {fake_key}"
    cleaned = sanitizer.sanitize(raw_text)

    assert fake_key not in cleaned
    assert "sk-p...[REDACTED_OPENAI_PROJ]...wxyz" in cleaned


def test_log_sanitizer_masks_google_key():
    """Verify Google API key is masked."""
    sanitizer = LogSanitizer()
    fake_key = "AIzaSy" + "1234567890abcdefghijklmnopqrstuv"
    raw_text = f"Request token={fake_key}"
    cleaned = sanitizer.sanitize(raw_text)

    assert fake_key not in cleaned
    assert "[REDACTED_GOOGLE]" in cleaned


def test_log_sanitizer_masks_bearer_token():
    """Verify Bearer token in authorization headers is masked."""
    sanitizer = LogSanitizer()
    raw_text = "Authorization: Bearer my_super_secret_jwt_token_1234567890"
    cleaned = sanitizer.sanitize(raw_text)

    assert "my_super_secret_jwt_token" not in cleaned
    assert "Bearer [REDACTED_TOKEN]" in cleaned


def test_log_sanitizer_logging_filter_integration():
    """Verify logging.Filter intercepts and sanitizes LogRecord."""
    sanitizer = LogSanitizer()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Leaked key sk-proj-1234567890abcdefghijklmnopqrstuvwxyz1234567890",
        args=(),
        exc_info=None,
    )

    allowed = sanitizer.filter(record)
    assert allowed is True
    assert "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz1234567890" not in record.msg
    assert "[REDACTED_OPENAI_PROJ]" in record.msg


def test_install_global_sanitizer():
    """Verify install_global_sanitizer adds filter to root logger."""
    sanitizer = install_global_sanitizer()
    root_logger = logging.getLogger()
    assert any(isinstance(f, LogSanitizer) for f in root_logger.filters)
