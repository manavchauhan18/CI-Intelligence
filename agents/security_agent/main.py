"""
Security Agent - Detects secrets, vulnerabilities, and insecure patterns.
Hybrid approach: Regex patterns + LLM reasoning.
"""
import re
import logging
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.config import settings
from shared.models import AgentVerdict, SecurityAgentPayload
from shared.llm import llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """Agent that performs security analysis on code changes."""

    # Regex patterns for common secrets and vulnerabilities
    SECRET_PATTERNS = {
        "AWS Key": r'AKIA[0-9A-Z]{16}',
        "Generic API Key": r'api[_-]?key["\s:=]+[a-zA-Z0-9]{20,}',
        "Private Key": r'-----BEGIN (?:RSA|OPENSSH|DSA|EC) PRIVATE KEY-----',
        "Password in Code": r'password["\s:=]+["\'][^"\']{8,}["\']',
        "JWT Token": r'eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*',
        "GitHub Token": r'gh[pousr]_[A-Za-z0-9]{36}',
        "Slack Token": r'xox[baprs]-[0-9]{10,12}-[0-9]{10,12}-[a-zA-Z0-9]{24,}',
    }

    VULNERABILITY_PATTERNS = {
        "SQL Injection Risk": r'execute\([^)]*\+[^)]*\)|"SELECT.*" \+ |\'SELECT.*\' \+ ',
        "Command Injection": r'os\.system\(|subprocess\.call\([^)]*\+|exec\(',
        "Hardcoded Secret": r'secret[_-]?key\s*=\s*["\'][^"\']+["\']',
        "Insecure Random": r'random\.random\(\)|Math\.random\(\)',
        "Eval Usage": r'\beval\(|\bexec\(',
    }

    def __init__(self):
        super().__init__("security_agent")

    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """Perform security analysis."""
        diff = data.get("diff", "")

        # Regex-based detection
        secrets_detected, secret_issues = self._detect_secrets(diff)
        vulnerabilities = self._detect_vulnerabilities(diff)

        # LLM-based deeper analysis
        llm_issues = await self._analyze_with_llm(diff)

        # Combine all issues
        all_issues = secret_issues + vulnerabilities + llm_issues

        # Calculate security score
        security_score = self._calculate_security_score(
            secrets_detected, len(vulnerabilities), len(llm_issues)
        )

        # Determine verdict
        verdict = self._determine_verdict(secrets_detected, all_issues)
        confidence = self._calculate_confidence(secrets_detected, all_issues)

        # Build payload
        payload = SecurityAgentPayload(
            secrets_detected=secrets_detected,
            vulnerabilities=[
                {"type": issue["type"], "line": issue.get("line", "unknown"), "details": issue["details"]}
                for issue in all_issues
            ],
            security_score=security_score,
            issues=[issue["details"] for issue in all_issues]
        ).model_dump()

        return verdict, confidence, payload

    def _detect_secrets(self, diff: str) -> tuple[bool, List[Dict[str, Any]]]:
        """Detect secrets using regex patterns."""
        issues = []

        # Only scan added lines (starting with +)
        lines = diff.split('\n')
        for line_num, line in enumerate(lines, 1):
            if not line.startswith('+'):
                continue

            # Remove the + prefix
            line_content = line[1:]

            # Check each secret pattern
            for secret_type, pattern in self.SECRET_PATTERNS.items():
                if re.search(pattern, line_content, re.IGNORECASE):
                    issues.append({
                        "type": "Secret Exposure",
                        "line": line_num,
                        "details": f"{secret_type} detected in code"
                    })

        return len(issues) > 0, issues

    def _detect_vulnerabilities(self, diff: str) -> List[Dict[str, Any]]:
        """Detect vulnerabilities using regex patterns."""
        issues = []

        lines = diff.split('\n')
        for line_num, line in enumerate(lines, 1):
            if not line.startswith('+'):
                continue

            line_content = line[1:]

            # Check each vulnerability pattern
            for vuln_type, pattern in self.VULNERABILITY_PATTERNS.items():
                if re.search(pattern, line_content, re.IGNORECASE):
                    issues.append({
                        "type": "Vulnerability",
                        "line": line_num,
                        "details": f"Potential {vuln_type}"
                    })

        return issues

    async def _analyze_with_llm(self, diff: str) -> List[Dict[str, Any]]:
        """Use LLM for deeper security analysis."""
        # Truncate diff if too long
        max_diff_length = 3000
        truncated_diff = diff[:max_diff_length]
        if len(diff) > max_diff_length:
            truncated_diff += "\n... (truncated)"

        system_prompt = """You are a security expert analyzing code changes for potential security issues.

Focus on:
1. Authentication/authorization issues
2. Insecure configurations
3. Data exposure risks
4. Injection vulnerabilities
5. Cryptographic issues

Return findings in this format:
ISSUES: [Number of issues found]
FINDINGS:
- [Issue description]
- [Issue description]
(Or "None" if no issues)"""

        user_prompt = f"""Analyze these code changes for security issues:

```diff
{truncated_diff}
```

What security concerns do you see?"""

        try:
            response = await llm_client.complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=800
            )

            return self._parse_llm_security_response(response)

        except Exception as e:
            logger.error(f"LLM security analysis failed: {e}", exc_info=True)
            return []

    def _parse_llm_security_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM security analysis response."""
        issues = []
        lines = response.strip().split('\n')

        in_findings = False
        for line in lines:
            line = line.strip()

            if line.startswith("FINDINGS:"):
                in_findings = True
                continue

            if in_findings and line.startswith("-"):
                finding = line.lstrip("- ").strip()
                if finding.lower() != "none":
                    issues.append({
                        "type": "Security Concern (LLM)",
                        "details": finding
                    })

        return issues

    def _calculate_security_score(
        self,
        secrets_detected: bool,
        num_vulnerabilities: int,
        num_llm_issues: int
    ) -> float:
        """Calculate security score (0.0 = bad, 1.0 = good)."""
        score = 1.0

        # Heavy penalty for secrets
        if secrets_detected:
            score -= 0.5

        # Penalty for vulnerabilities
        score -= num_vulnerabilities * 0.1

        # Penalty for LLM-detected issues
        score -= num_llm_issues * 0.05

        return max(0.0, score)

    def _determine_verdict(
        self,
        secrets_detected: bool,
        all_issues: List[Dict[str, Any]]
    ) -> AgentVerdict:
        """Determine verdict based on security findings."""
        # Always reject if secrets are detected
        if secrets_detected:
            return AgentVerdict.REJECT

        # Reject if critical vulnerabilities
        critical_count = sum(
            1 for issue in all_issues
            if any(x in issue["details"].lower() for x in ["injection", "eval", "exec"])
        )
        if critical_count > 0:
            return AgentVerdict.REJECT

        # Warn if moderate issues
        if len(all_issues) > 2:
            return AgentVerdict.WARN

        if len(all_issues) > 0:
            return AgentVerdict.WARN

        return AgentVerdict.APPROVE

    def _calculate_confidence(
        self,
        secrets_detected: bool,
        all_issues: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence in security analysis."""
        # High confidence when rejecting for secrets
        if secrets_detected:
            return 0.95

        # High confidence for clear vulnerabilities
        if any("injection" in issue["details"].lower() for issue in all_issues):
            return 0.90

        # Moderate confidence for LLM findings
        if all_issues:
            return 0.75

        # High confidence for clean code
        return 0.85


agent = SecurityAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    import asyncio
    asyncio.create_task(agent.start())
    logger.info("Security Agent started")

    yield

    # Shutdown
    await agent.stop()
    logger.info("Security Agent stopped")


app = FastAPI(
    title="Security Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "security_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.security_agent_host,
        port=settings.security_agent_port,
        log_level="info"
    )
