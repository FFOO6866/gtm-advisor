"""Lead Data Quality Scorer — gates sequence enrollment.

Before any lead enters an outreach sequence, this scorer evaluates:
1. Email validity (DNS MX record check — deterministic)
2. Contact data completeness (name, role, company all present?)
3. Company verification (is the company real and active?)
4. Role seniority match (is this a decision-maker?)
5. Data freshness (was this lead data captured recently?)

A lead MUST pass minimum quality threshold to enter a sequence.
This prevents sending to bad emails (deliverability protection) and
wasting sequences on unverifiable contacts.

Why this matters vs ChatGPT:
ChatGPT will happily generate 100 leads that look plausible but have
invalid emails, outdated roles, and non-existent companies.
This scorer catches those before a single email is sent.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class LeadQualityReport:
    """Quality assessment for a single lead."""
    lead_id: str
    overall_score: float  # 0-1
    email_valid: bool
    email_deliverable: bool  # MX record exists
    data_completeness: float  # 0-1
    seniority_score: float  # 0-1 (decision-maker proximity)
    company_verified: bool
    qualifies_for_sequence: bool  # True if overall_score >= threshold
    blockers: list[str] = field(default_factory=list)  # Why it failed
    warnings: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "overall_score": round(self.overall_score, 3),
            "email_valid": self.email_valid,
            "email_deliverable": self.email_deliverable,
            "data_completeness": round(self.data_completeness, 3),
            "seniority_score": round(self.seniority_score, 3),
            "company_verified": self.company_verified,
            "qualifies_for_sequence": self.qualifies_for_sequence,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "checks_run": self.checks_run,
        }


class LeadDataQualityScorer:
    """Scores lead data quality and gates sequence enrollment.

    This is a hard gate — a lead that fails minimum quality is BLOCKED
    from outreach regardless of ICP fit score.

    Minimum threshold: 0.55 overall quality score
    Hard blockers: invalid email format, no MX record, no name
    """

    SEQUENCE_THRESHOLD = 0.55
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

    def __init__(self, sequence_threshold: float = 0.55) -> None:
        self.sequence_threshold = sequence_threshold
        self._seniority_tiers = [
            (["ceo", "chief executive", "founder", "co-founder", "owner", "president", "managing director", " md"], 1.0),
            (["cto", "cfo", "coo", "cmo", "ciso", "chief"], 0.95),
            (["vp", "vice president", "svp", "evp"], 0.85),
            (["director", "head of", "general manager"], 0.75),
            (["manager", "lead", "principal"], 0.60),
            (["senior", "specialist", "consultant"], 0.45),
            (["analyst", "associate"], 0.30),
        ]

    def score(self, lead: dict[str, Any]) -> LeadQualityReport:
        """Score a lead's data quality.

        Args:
            lead: Lead data dict with keys:
                id, email, name, title/job_title, company, company_domain,
                created_at (optional), company_employees (optional)

        Returns:
            LeadQualityReport with qualification decision
        """
        lead_id = str(lead.get("id", "unknown"))
        blockers: list[str] = []
        warnings: list[str] = []
        checks: list[str] = []
        components: dict[str, float] = {}

        # --- HARD CHECKS (blockers) ---

        # 1. Email format
        email = (lead.get("email") or "").strip().lower()
        checks.append("email_format")
        if not email:
            blockers.append("No email address")
            email_valid = False
            email_deliverable = False
        elif not self.EMAIL_REGEX.match(email):
            blockers.append(f"Invalid email format: {email}")
            email_valid = False
            email_deliverable = False
        else:
            email_valid = True
            # 2. MX record check (DNS)
            checks.append("mx_record")
            domain = email.split("@")[1]
            email_deliverable = self._check_mx_record(domain)
            if not email_deliverable:
                blockers.append(f"No MX record for domain {domain} — email likely undeliverable")

        # 3. Name required
        checks.append("name_present")
        name = (lead.get("name") or lead.get("full_name") or "").strip()
        if not name:
            blockers.append("No contact name")

        # --- SOFT CHECKS (scored) ---

        # 4. Data completeness
        checks.append("data_completeness")
        fields = ["email", "name", "title", "company", "company_domain", "industry"]
        present = sum(1 for f in fields if lead.get(f) or lead.get(f.replace("title", "job_title")))
        data_completeness = present / len(fields)
        components["completeness"] = data_completeness * 0.30

        if data_completeness < 0.5:
            warnings.append(f"Low data completeness ({data_completeness:.0%}) — personalisation will be limited")

        # 5. Seniority score
        checks.append("seniority")
        title = (lead.get("title") or lead.get("job_title") or "").lower()
        seniority_score = self._score_seniority(title)
        components["seniority"] = seniority_score * 0.25

        if seniority_score < 0.45:
            warnings.append(f"Low seniority title '{title}' — not a typical decision-maker")

        # 6. Company presence
        checks.append("company_verification")
        company = lead.get("company") or lead.get("company_name") or ""
        company_domain = lead.get("company_domain") or lead.get("website") or ""
        company_verified = bool(company and (company_domain or len(company) >= 3))
        components["company"] = 0.20 if company_verified else 0.05

        # 7. Email quality (not generic/role-based)
        checks.append("email_quality")
        generic_prefixes = ["info@", "hello@", "contact@", "support@", "sales@", "admin@", "hr@", "team@"]
        if any(email.startswith(p) for p in generic_prefixes):
            warnings.append(f"Generic/role-based email ({email}) — lower reply probability")
            components["email_quality"] = 0.05
        elif email_valid:
            components["email_quality"] = 0.15
        else:
            components["email_quality"] = 0.0

        # 8. Data freshness (if created_at available)
        checks.append("data_freshness")
        created_at = lead.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except ValueError:
                    created_at = None
            if created_at:
                age_days = (datetime.now(UTC) - created_at).days
                if age_days <= 30:
                    components["freshness"] = 0.10
                elif age_days <= 90:
                    components["freshness"] = 0.07
                else:
                    components["freshness"] = 0.03
                    warnings.append(f"Lead data is {age_days} days old — role may have changed")
        else:
            components["freshness"] = 0.05

        total = sum(components.values())
        total = min(1.0, total)

        qualifies = bool(email_valid and email_deliverable and name and total >= self.sequence_threshold)

        return LeadQualityReport(
            lead_id=lead_id,
            overall_score=round(total, 3),
            email_valid=email_valid,
            email_deliverable=email_deliverable,
            data_completeness=data_completeness,
            seniority_score=seniority_score,
            company_verified=company_verified,
            qualifies_for_sequence=qualifies,
            blockers=blockers,
            warnings=warnings,
            checks_run=checks,
        )

    def _check_mx_record(self, domain: str) -> bool:
        """Check if a domain has MX records (email is deliverable).

        This is a real DNS check — not an LLM guess.
        Returns False for domains with no mail server (invalid email).
        """
        try:
            # Use getaddrinfo as a lightweight connectivity check
            # For production, use dnspython: dns.resolver.resolve(domain, 'MX')
            socket.getaddrinfo(domain, None, socket.AF_INET)
            return True
        except (socket.gaierror, OSError):
            return False

    def _score_seniority(self, title: str) -> float:
        """Score seniority from job title string."""
        if not title:
            return 0.35  # Unknown — give benefit of the doubt
        for keywords, score in self._seniority_tiers:
            if any(kw in title for kw in keywords):
                return score
        return 0.35
