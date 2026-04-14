from codex_session_bridge.redaction import sanitize_text


def test_sanitize_text_redacts_common_secret_patterns() -> None:
    raw = (
        "Authorization: Bearer abc.def.ghi\n"
        "api_key=abc1234567890\n"
        "access_token: 'token-value-123456'\n"
        "sk-1234567890abcdefghijklmnop\n"
        "url?token=abcdefghi123456\n"
    )
    out = sanitize_text(raw)
    assert "abc.def.ghi" not in out
    assert "abc1234567890" not in out
    assert "token-value-123456" not in out
    assert "sk-1234567890abcdefghijklmnop" not in out
    assert "abcdefghi123456" not in out
    assert out.count("[REDACTED]") >= 4
