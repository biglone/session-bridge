import re


_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s\"']+)")
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret)\b\s*[:=]\s*([\"']?)([A-Za-z0-9._-]{8,})\2"
)
_QUERY_PATTERN = re.compile(r"(?i)\b(api[_-]?key|access_token|refresh_token|token)=([A-Za-z0-9._-]{8,})")
_OPENAI_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")


def sanitize_text(text: str) -> str:
    if not text:
        return text

    text = _BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    text = _ASSIGNMENT_PATTERN.sub(lambda m: f"{m.group(1)}={m.group(2)}[REDACTED]{m.group(2)}", text)
    text = _QUERY_PATTERN.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = _OPENAI_KEY_PATTERN.sub("sk-[REDACTED]", text)
    return text
