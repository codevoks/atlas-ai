from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

GUARDRAIL_VERSION = "phase10-deterministic-security-v1"
DEFAULT_POLICY_CONFIG_VERSION = "phase10-default-policy-v1"


class GuardrailAction(StrEnum):
    ALLOW = "allow"
    DETECT = "detect"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    code: str
    severity: str
    action: GuardrailAction
    message: str
    evidence: str


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    action: GuardrailAction
    findings: list[GuardrailFinding]
    sanitized_text: str

    @property
    def blocked(self) -> bool:
        return any(finding.action is GuardrailAction.BLOCK for finding in self.findings)

    @property
    def detected(self) -> bool:
        return bool(self.findings)


class Redactor:
    _patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(
                r"\b(?:sk|sk-proj|sk-ant|sk-live|pk-live)-[A-Za-z0-9_-]{8,}\b",
                re.IGNORECASE,
            ),
            "[REDACTED_API_KEY]",
        ),
        (
            re.compile(
                r"\b(?:aws_access_key_id|aws_secret_access_key|api[_ -]?key|password|secret)"
                r"\s*[:=]\s*[^\s,;]{6,}",
                re.IGNORECASE,
            ),
            "[REDACTED_SECRET]",
        ),
        (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
            "[REDACTED_EMAIL]",
        ),
    )

    def redact_text(self, value: str, *, max_chars: int = 280) -> str:
        redacted = value
        for pattern, replacement in self._patterns:
            redacted = pattern.sub(replacement, redacted)
        normalized = " ".join(redacted.split())
        return normalized[:max_chars]


class InputValidator:
    _prompt_patterns: tuple[tuple[re.Pattern[str], str, str], ...] = (
        (
            re.compile(
                r"\b(ignore|override|bypass)\b.{0,80}\b(instruction|policy|guardrail|system)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "indirect_prompt_injection",
            "medium",
        ),
        (
            re.compile(
                r"\b(exfiltrate|leak|dump|reveal)\b.{0,80}\b(secret|password|token|api[_ -]?key)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            "secret_exfiltration_instruction",
            "high",
        ),
    )
    _secret_patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(r"\b(?:sk|sk-proj|sk-ant|sk-live)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
            "secret_like_value",
        ),
        (
            re.compile(
                r"\b(?:aws_secret_access_key|api[_ -]?key|password|secret)\s*[:=]",
                re.IGNORECASE,
            ),
            "secret_label",
        ),
    )
    _ssrf_patterns: tuple[re.Pattern[str], ...] = (
        re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])", re.IGNORECASE),
        re.compile(r"https?://169\.254\.169\.254", re.IGNORECASE),
        re.compile(r"\bfile://", re.IGNORECASE),
    )

    def __init__(self, redactor: Redactor | None = None) -> None:
        self._redactor = redactor or Redactor()

    def scan_text(
        self, value: str, *, boundary: str, block_on_secret: bool = True
    ) -> GuardrailDecision:
        findings: list[GuardrailFinding] = []
        sanitized = self._redactor.redact_text(value)
        for pattern, code, severity in self._prompt_patterns:
            match = pattern.search(value)
            if match is not None:
                findings.append(
                    GuardrailFinding(
                        code=code,
                        severity=severity,
                        action=GuardrailAction.BLOCK,
                        message=f"Unsafe instruction detected at {boundary}.",
                        evidence=self._redactor.redact_text(match.group(0)),
                    )
                )
        for pattern, code in self._secret_patterns:
            match = pattern.search(value)
            if match is not None:
                findings.append(
                    GuardrailFinding(
                        code=code,
                        severity="high" if block_on_secret else "medium",
                        action=GuardrailAction.BLOCK if block_on_secret else GuardrailAction.DETECT,
                        message=f"Secret-like content detected at {boundary}.",
                        evidence=self._redactor.redact_text(match.group(0)),
                    )
                )
        for pattern in self._ssrf_patterns:
            match = pattern.search(value)
            if match is not None:
                findings.append(
                    GuardrailFinding(
                        code="ssrf_candidate",
                        severity="high",
                        action=GuardrailAction.BLOCK,
                        message=f"Unsafe local or metadata URL detected at {boundary}.",
                        evidence=self._redactor.redact_text(match.group(0)),
                    )
                )
        action = (
            GuardrailAction.BLOCK
            if any(item.action is GuardrailAction.BLOCK for item in findings)
            else GuardrailAction.DETECT
            if findings
            else GuardrailAction.ALLOW
        )
        return GuardrailDecision(action=action, findings=findings, sanitized_text=sanitized)


class OutputValidator:
    def __init__(self, redactor: Redactor | None = None) -> None:
        self._input = InputValidator(redactor)

    def scan_output(self, value: str, *, boundary: str) -> GuardrailDecision:
        return self._input.scan_text(value, boundary=boundary, block_on_secret=True)


class EgressPolicy:
    _allowed_schemes = {"https"}

    def validate_url(self, url: str) -> GuardrailDecision:
        parsed = urlparse(url)
        findings: list[GuardrailFinding] = []
        redactor = Redactor()
        if parsed.scheme.lower() not in self._allowed_schemes:
            findings.append(
                GuardrailFinding(
                    code="egress_scheme_blocked",
                    severity="high",
                    action=GuardrailAction.BLOCK,
                    message="Only HTTPS egress is allowed.",
                    evidence=redactor.redact_text(url),
                )
            )
        host = parsed.hostname or ""
        if host in {"localhost", "0.0.0.0"}:  # noqa: S104 - validating an unsafe host literal
            findings.append(_blocked_host_finding(url))
        else:
            try:
                address = ipaddress.ip_address(host.strip("[]"))
            except ValueError:
                address = None
            if address is not None and (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
            ):
                findings.append(_blocked_host_finding(url))
        return GuardrailDecision(
            action=GuardrailAction.BLOCK if findings else GuardrailAction.ALLOW,
            findings=findings,
            sanitized_text=redactor.redact_text(url),
        )


def _blocked_host_finding(url: str) -> GuardrailFinding:
    return GuardrailFinding(
        code="egress_host_blocked",
        severity="high",
        action=GuardrailAction.BLOCK,
        message="Local, private, link-local, reserved, or metadata egress targets are blocked.",
        evidence=Redactor().redact_text(url),
    )


def findings_to_safe_metadata(findings: list[GuardrailFinding]) -> dict[str, object]:
    return {
        "guardrail_version": GUARDRAIL_VERSION,
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity,
                "action": finding.action.value,
                "message": finding.message,
                "evidence": finding.evidence,
            }
            for finding in findings
        ],
    }
