"""GTM Clarification Service.

Generates structured clarifying questions before analysis to ensure the
agents have sufficient context. Based on the agentic-os ObjectiveClarificationService
pattern — ask first, then plan, then execute.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from packages.core.src.types import IndustryVertical

logger = structlog.get_logger()


class ClarificationQuestion(BaseModel):
    """A single clarifying question."""

    id: str = Field(..., description="Unique identifier, e.g. 'target_segment'")
    question: str = Field(..., description="The question text shown to the user")
    purpose: str = Field(..., description="Why this question matters for the analysis")
    required: bool = Field(default=True)
    input_type: str = Field(default="text", description="text | select | multiselect")
    options: list[str] | None = Field(default=None, description="For select/multiselect types")
    placeholder: str | None = Field(default=None, description="Example answer for text inputs")


class ClarificationResponse(BaseModel):
    """User answer to a clarification question."""

    question_id: str
    answer: str | list[str]


class ClarificationSession(BaseModel):
    """A set of questions for a specific analysis context."""

    company_name: str
    industry: IndustryVertical
    questions: list[ClarificationQuestion]
    readiness_score: float = Field(default=0.0, description="0-1: how complete the context is")


# ─────────────────────────────────────────────────────────────────────────────
# Industry-specific required questions
# ─────────────────────────────────────────────────────────────────────────────

_UNIVERSAL_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "primary_goal",
        "question": "What is the single most important outcome you want from this GTM analysis?",
        "purpose": "Focuses the analysis on your top priority",
        "required": True,
        "input_type": "select",
        "options": [
            "Find new customers quickly",
            "Understand my competitive landscape",
            "Identify the right market segment to target",
            "Build a repeatable sales playbook",
            "Expand into new verticals or geographies",
        ],
    },
    {
        "id": "target_customer_size",
        "question": "What size companies are your ideal customers?",
        "purpose": "Filters leads to the right company size",
        "required": True,
        "input_type": "select",
        "options": ["Solopreneurs / freelancers", "SMEs (10–200 employees)", "Mid-market (200–1000)", "Enterprise (1000+)", "Mixed"],
    },
    {
        "id": "current_traction",
        "question": "How many paying customers do you have today?",
        "purpose": "Calibrates the analysis for your current stage",
        "required": True,
        "input_type": "select",
        "options": ["0 (pre-revenue)", "1–10", "11–50", "51–200", "200+"],
    },
    {
        "id": "sales_cycle",
        "question": "How long is your typical sales cycle?",
        "purpose": "Shapes the campaign cadence and lead prioritisation",
        "required": False,
        "input_type": "select",
        "options": ["< 1 week (transactional)", "1–4 weeks", "1–3 months", "3–6 months", "> 6 months"],
    },
]

_INDUSTRY_QUESTIONS: dict[str, list[dict[str, Any]]] = {
    IndustryVertical.FINTECH: [
        {
            "id": "mas_license",
            "question": "Do you hold or require any MAS licence (e.g. MPI, CMS, CMP)?",
            "purpose": "Determines regulatory positioning and eligible customer segments",
            "required": True,
            "input_type": "select",
            "options": ["Yes — MPI", "Yes — CMS", "Yes — CMP / other", "Exempt / not required", "In progress"],
        },
        {
            "id": "b2b_or_b2c",
            "question": "Are you primarily B2B (financial institutions) or B2C (retail consumers)?",
            "purpose": "Shapes the entire lead generation and campaign strategy",
            "required": True,
            "input_type": "select",
            "options": ["B2B only", "B2C only", "Both"],
        },
    ],
    IndustryVertical.SAAS: [
        {
            "id": "pricing_model",
            "question": "What is your primary pricing model?",
            "purpose": "Informs the sales motion and ICP selection",
            "required": True,
            "input_type": "select",
            "options": ["Per seat / user", "Usage-based", "Flat monthly subscription", "Annual enterprise contract", "Freemium"],
        },
        {
            "id": "psg_eligible",
            "question": "Is your solution listed on the IMDA Tech Partners listing or PSG-approved?",
            "purpose": "PSG eligibility is a strong selling point for Singapore SME buyers",
            "required": False,
            "input_type": "select",
            "options": ["Yes — PSG approved", "Yes — IMDA listed", "No", "Not sure"],
        },
    ],
    IndustryVertical.HEALTHTECH: [
        {
            "id": "hsa_regulated",
            "question": "Is your product regulated by HSA as a medical device or SaMD?",
            "purpose": "Determines go-to-market timeline and regulatory messaging",
            "required": True,
            "input_type": "select",
            "options": ["Yes — Class A/B", "Yes — Class C/D", "No", "Pending registration"],
        },
    ],
    IndustryVertical.ECOMMERCE: [
        {
            "id": "platform",
            "question": "Which e-commerce platform(s) do you sell on?",
            "purpose": "Identifies integration partners and channel strategy",
            "required": False,
            "input_type": "multiselect",
            "options": ["Shopify", "WooCommerce", "Lazada", "Shopee", "Own website", "TikTok Shop", "Other"],
        },
    ],
}


class GTMClarificationService:
    """Generates context-appropriate clarifying questions before analysis starts.

    Usage:
        svc = GTMClarificationService()
        session = await svc.generate_questions("TechCorp", IndustryVertical.SAAS, ["find customers"])
        score = svc.evaluate_completeness(responses)
    """

    def generate_questions(
        self,
        company_name: str,
        industry: IndustryVertical,
        goals: list[str] | None = None,
        existing_context: dict[str, Any] | None = None,
    ) -> ClarificationSession:
        """Generate questions tailored to this company and industry.

        Questions are ordered: required universal → industry-specific → optional.
        Already-answered questions (from existing_context) are excluded.
        """
        existing = existing_context or {}
        all_questions: list[ClarificationQuestion] = []

        # Universal questions (skip if already in existing_context)
        for q_data in _UNIVERSAL_QUESTIONS:
            if q_data["id"] not in existing:
                all_questions.append(ClarificationQuestion(**q_data))

        # Industry-specific questions
        industry_qs = _INDUSTRY_QUESTIONS.get(industry, [])
        for q_data in industry_qs:
            if q_data["id"] not in existing:
                all_questions.append(ClarificationQuestion(**q_data))

        # Goal-specific additions
        if goals and any("competitor" in g.lower() for g in goals):
            all_questions.append(
                ClarificationQuestion(
                    id="known_competitors_detail",
                    question="List up to 3 competitors you are most worried about and why.",
                    purpose="Focuses competitive analysis on your real threats",
                    required=False,
                    input_type="text",
                    placeholder="e.g. CompanyX — they have similar pricing, CompanyY — they have better brand",
                )
            )

        # Sort: required first, then optional
        all_questions.sort(key=lambda q: (0 if q.required else 1))

        logger.debug(
            "clarification_questions_generated",
            company=company_name,
            industry=industry.value,
            count=len(all_questions),
        )

        return ClarificationSession(
            company_name=company_name,
            industry=industry,
            questions=all_questions,
            readiness_score=self._compute_readiness(existing, all_questions),
        )

    def evaluate_completeness(
        self,
        responses: list[ClarificationResponse],
        session: ClarificationSession,
    ) -> float:
        """Compute readiness score 0-1 based on how many required questions were answered.

        Returns:
            float: 0.0 = no required answers, 1.0 = all required questions answered
        """
        answered_ids = {r.question_id for r in responses if r.answer}
        required_qs = [q for q in session.questions if q.required]

        if not required_qs:
            return 1.0

        answered_required = sum(1 for q in required_qs if q.id in answered_ids)
        return answered_required / len(required_qs)

    def responses_to_context(
        self,
        responses: list[ClarificationResponse],
    ) -> dict[str, Any]:
        """Convert clarification responses into a context dict for agents."""
        return {r.question_id: r.answer for r in responses}

    def _compute_readiness(
        self,
        existing_context: dict[str, Any],
        questions: list[ClarificationQuestion],
    ) -> float:
        """Compute how ready the context is based on existing answers."""
        required_qs = [q for q in questions if q.required]
        if not required_qs:
            return 1.0
        answered = sum(1 for q in required_qs if q.id in existing_context)
        return answered / len(required_qs)
