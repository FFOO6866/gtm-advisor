"""PDPA Compliance for Singapore.

Implements Personal Data Protection Act (PDPA) requirements:
- Consent management
- Data categorization
- Purpose limitation
- Access controls
- Retention policies

Reference: https://www.pdpc.gov.sg/

Principle: No personal data processing without consent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
import re
import hashlib


class DataCategory(Enum):
    """Categories of data under PDPA."""
    PUBLIC = "public"  # Publicly available (company info, job titles)
    BUSINESS = "business"  # Business contact info with consent
    PERSONAL = "personal"  # Personal identifiable information
    SENSITIVE = "sensitive"  # Financial, health, etc.


class ConsentStatus(Enum):
    """Status of consent for data processing."""
    NOT_REQUIRED = "not_required"  # Public/business data
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ProcessingPurpose(Enum):
    """Purposes for data processing."""
    MARKETING = "marketing"
    SALES = "sales"
    ANALYTICS = "analytics"
    PERSONALIZATION = "personalization"
    SERVICE_DELIVERY = "service_delivery"
    LEGAL_OBLIGATION = "legal_obligation"


@dataclass
class ConsentRecord:
    """Record of consent for data processing."""
    id: str
    data_subject_id: str  # Hashed email or identifier
    purposes: list[ProcessingPurpose]
    granted_at: datetime
    expires_at: datetime | None
    source: str  # How consent was obtained
    ip_address: str | None = None
    withdrawn_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        """Check if consent is still valid."""
        if self.withdrawn_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "data_subject_id": self.data_subject_id,
            "purposes": [p.value for p in self.purposes],
            "granted_at": self.granted_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "source": self.source,
            "is_valid": self.is_valid,
            "withdrawn_at": self.withdrawn_at.isoformat() if self.withdrawn_at else None,
        }


@dataclass
class DataField:
    """Definition of a data field and its category."""
    name: str
    category: DataCategory
    requires_consent: bool
    retention_days: int | None = None  # None = indefinite
    can_export: bool = True
    can_share: bool = False
    pii_type: str | None = None  # email, phone, nric, etc.


# Standard field definitions for GTM data
STANDARD_FIELDS = {
    # Company fields (public/business)
    "company_name": DataField("company_name", DataCategory.PUBLIC, False),
    "company_domain": DataField("company_domain", DataCategory.PUBLIC, False),
    "company_industry": DataField("company_industry", DataCategory.PUBLIC, False),
    "company_size": DataField("company_size", DataCategory.PUBLIC, False),
    "company_revenue": DataField("company_revenue", DataCategory.BUSINESS, False),
    "company_address": DataField("company_address", DataCategory.PUBLIC, False),

    # Contact fields (require consent for marketing)
    "contact_email": DataField(
        "contact_email",
        DataCategory.PERSONAL,
        requires_consent=True,
        pii_type="email",
        retention_days=365,
    ),
    "contact_phone": DataField(
        "contact_phone",
        DataCategory.PERSONAL,
        requires_consent=True,
        pii_type="phone",
        retention_days=365,
    ),
    "contact_name": DataField(
        "contact_name",
        DataCategory.PERSONAL,
        requires_consent=True,
        pii_type="name",
        retention_days=365,
    ),
    "contact_title": DataField("contact_title", DataCategory.BUSINESS, False),
    "contact_linkedin": DataField("contact_linkedin", DataCategory.BUSINESS, False),

    # Sensitive fields
    "nric": DataField(
        "nric",
        DataCategory.SENSITIVE,
        requires_consent=True,
        pii_type="nric",
        can_export=False,
        can_share=False,
        retention_days=90,
    ),
    "financial_info": DataField(
        "financial_info",
        DataCategory.SENSITIVE,
        requires_consent=True,
        can_export=False,
        can_share=False,
    ),
}


class PDPAChecker:
    """Check PDPA compliance for data operations.

    Example:
        checker = PDPAChecker()

        # Check if can process email for marketing
        if checker.can_process(
            field="contact_email",
            purpose=ProcessingPurpose.MARKETING,
            data_subject_id="user@example.com",
        ):
            # proceed
            pass

        # Mask PII for display
        masked = checker.mask_pii(data, ["contact_email", "contact_phone"])

        # Check data for PII
        pii_found = checker.detect_pii(text)
    """

    def __init__(self):
        self._consent_records: dict[str, list[ConsentRecord]] = {}
        self._field_definitions = STANDARD_FIELDS.copy()

    def define_field(self, field: DataField) -> None:
        """Define or override a field definition."""
        self._field_definitions[field.name] = field

    def get_field(self, field_name: str) -> DataField | None:
        """Get field definition."""
        return self._field_definitions.get(field_name)

    def record_consent(
        self,
        data_subject_email: str,
        purposes: list[ProcessingPurpose],
        source: str,
        expires_in_days: int = 365,
        ip_address: str | None = None,
    ) -> ConsentRecord:
        """Record consent from a data subject."""
        import uuid

        # Hash the email for privacy
        subject_id = self._hash_identifier(data_subject_email)

        record = ConsentRecord(
            id=str(uuid.uuid4()),
            data_subject_id=subject_id,
            purposes=purposes,
            granted_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            source=source,
            ip_address=ip_address,
        )

        if subject_id not in self._consent_records:
            self._consent_records[subject_id] = []
        self._consent_records[subject_id].append(record)

        return record

    def withdraw_consent(
        self,
        data_subject_email: str,
        purposes: list[ProcessingPurpose] | None = None,
    ) -> bool:
        """Withdraw consent (all or specific purposes)."""
        subject_id = self._hash_identifier(data_subject_email)
        records = self._consent_records.get(subject_id, [])

        for record in records:
            if purposes:
                # Withdraw specific purposes
                record.purposes = [p for p in record.purposes if p not in purposes]
                if not record.purposes:
                    record.withdrawn_at = datetime.utcnow()
            else:
                # Withdraw all
                record.withdrawn_at = datetime.utcnow()

        return True

    def has_consent(
        self,
        data_subject_email: str,
        purpose: ProcessingPurpose,
    ) -> ConsentStatus:
        """Check if consent exists for a purpose."""
        subject_id = self._hash_identifier(data_subject_email)
        records = self._consent_records.get(subject_id, [])

        for record in records:
            if record.withdrawn_at:
                return ConsentStatus.WITHDRAWN
            if record.expires_at and datetime.utcnow() > record.expires_at:
                continue  # Check other records
            if purpose in record.purposes:
                return ConsentStatus.GRANTED

        if records:
            # Had consent but expired or withdrawn
            return ConsentStatus.EXPIRED

        return ConsentStatus.UNKNOWN

    def can_process(
        self,
        field: str,
        purpose: ProcessingPurpose,
        data_subject_id: str | None = None,
    ) -> bool:
        """Check if data can be processed for a purpose."""
        field_def = self._field_definitions.get(field)

        if not field_def:
            # Unknown field - be conservative
            return False

        # Public data doesn't need consent
        if field_def.category == DataCategory.PUBLIC:
            return True

        # Business data for business purposes
        if field_def.category == DataCategory.BUSINESS:
            if purpose in [ProcessingPurpose.SALES, ProcessingPurpose.SERVICE_DELIVERY]:
                return True

        # Personal/sensitive data requires consent
        if field_def.requires_consent:
            if not data_subject_id:
                return False

            consent = self.has_consent(data_subject_id, purpose)
            return consent == ConsentStatus.GRANTED

        return True

    def mask_pii(
        self,
        data: dict[str, Any],
        fields_to_mask: list[str] | None = None,
    ) -> dict[str, Any]:
        """Mask PII fields in data."""
        masked = data.copy()

        fields = fields_to_mask or list(self._field_definitions.keys())

        for field_name in fields:
            if field_name not in masked:
                continue

            field_def = self._field_definitions.get(field_name)
            if not field_def or field_def.category == DataCategory.PUBLIC:
                continue

            value = masked[field_name]
            if not value:
                continue

            # Mask based on PII type
            if field_def.pii_type == "email":
                masked[field_name] = self._mask_email(str(value))
            elif field_def.pii_type == "phone":
                masked[field_name] = self._mask_phone(str(value))
            elif field_def.pii_type == "nric":
                masked[field_name] = self._mask_nric(str(value))
            elif field_def.pii_type == "name":
                masked[field_name] = self._mask_name(str(value))
            else:
                masked[field_name] = "***"

        return masked

    def detect_pii(self, text: str) -> list[dict[str, Any]]:
        """Detect potential PII in text."""
        findings = []

        # Email pattern
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        for email in emails:
            findings.append({
                "type": "email",
                "value": email,
                "masked": self._mask_email(email),
                "category": DataCategory.PERSONAL.value,
            })

        # Singapore phone numbers
        phones = re.findall(r'(?:\+65\s?)?[689]\d{3}\s?\d{4}', text)
        for phone in phones:
            findings.append({
                "type": "phone",
                "value": phone,
                "masked": self._mask_phone(phone),
                "category": DataCategory.PERSONAL.value,
            })

        # Singapore NRIC
        nrics = re.findall(r'[STFG]\d{7}[A-Z]', text, re.IGNORECASE)
        for nric in nrics:
            findings.append({
                "type": "nric",
                "value": nric,
                "masked": self._mask_nric(nric),
                "category": DataCategory.SENSITIVE.value,
            })

        return findings

    def redact_pii(self, text: str) -> str:
        """Redact PII from text."""
        # Redact emails
        text = re.sub(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            '[EMAIL REDACTED]',
            text
        )

        # Redact Singapore phone numbers
        text = re.sub(
            r'(?:\+65\s?)?[689]\d{3}\s?\d{4}',
            '[PHONE REDACTED]',
            text
        )

        # Redact NRIC
        text = re.sub(
            r'[STFG]\d{7}[A-Z]',
            '[NRIC REDACTED]',
            text,
            flags=re.IGNORECASE
        )

        return text

    def get_retention_status(
        self,
        field: str,
        collected_at: datetime,
    ) -> dict[str, Any]:
        """Check if data should be retained or deleted."""
        field_def = self._field_definitions.get(field)

        if not field_def or not field_def.retention_days:
            return {
                "field": field,
                "status": "indefinite",
                "should_delete": False,
            }

        expires_at = collected_at + timedelta(days=field_def.retention_days)
        should_delete = datetime.utcnow() > expires_at

        return {
            "field": field,
            "collected_at": collected_at.isoformat(),
            "retention_days": field_def.retention_days,
            "expires_at": expires_at.isoformat(),
            "should_delete": should_delete,
            "days_remaining": max(0, (expires_at - datetime.utcnow()).days),
        }

    def _hash_identifier(self, identifier: str) -> str:
        """Hash an identifier for privacy."""
        return hashlib.sha256(identifier.lower().encode()).hexdigest()[:16]

    def _mask_email(self, email: str) -> str:
        """Mask email address."""
        parts = email.split("@")
        if len(parts) != 2:
            return "***@***.***"
        local = parts[0]
        domain = parts[1]
        masked_local = local[0] + "*" * (len(local) - 1) if local else "***"
        return f"{masked_local}@{domain}"

    def _mask_phone(self, phone: str) -> str:
        """Mask phone number."""
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 4:
            return "*" * (len(digits) - 4) + digits[-4:]
        return "****"

    def _mask_nric(self, nric: str) -> str:
        """Mask NRIC."""
        if len(nric) >= 4:
            return nric[0] + "*" * (len(nric) - 2) + nric[-1]
        return "****"

    def _mask_name(self, name: str) -> str:
        """Mask name."""
        parts = name.split()
        masked_parts = []
        for part in parts:
            if len(part) > 1:
                masked_parts.append(part[0] + "*" * (len(part) - 1))
            else:
                masked_parts.append("*")
        return " ".join(masked_parts)

    def generate_compliance_report(self) -> dict[str, Any]:
        """Generate PDPA compliance report."""
        total_consents = sum(len(records) for records in self._consent_records.values())
        active_consents = sum(
            1 for records in self._consent_records.values()
            for record in records
            if record.is_valid
        )

        # Categorize fields
        field_categories = {}
        for cat in DataCategory:
            field_categories[cat.value] = [
                f.name for f in self._field_definitions.values()
                if f.category == cat
            ]

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_data_subjects": len(self._consent_records),
            "total_consent_records": total_consents,
            "active_consents": active_consents,
            "field_categories": field_categories,
            "sensitive_fields": [
                f.name for f in self._field_definitions.values()
                if f.category == DataCategory.SENSITIVE
            ],
            "retention_policies": {
                f.name: f.retention_days
                for f in self._field_definitions.values()
                if f.retention_days
            },
        }
