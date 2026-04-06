"""Kairos Scoring Methodology — The 'Why Us vs ChatGPT' Document.

This module documents the intellectual property at the core of Kairos:
a multi-layer scoring stack that combines real data with deterministic algorithms.

This is NOT a prompt. It is a methodology.

Why SMEs choose Kairos over ChatGPT / Claude:
-------------------------------------------------------
1. PERSISTENT CONTEXT    — remembers your company, leads, history
2. LIVE DATA             — EODHD (today's market), NewsAPI (today's news), ACRA (company registry)
3. ACTIONABLE EXECUTION  — sends emails, updates CRM, manages sequences — ChatGPT can't
4. CONTINUOUS OPERATION  — runs while you sleep (signal monitor, sequence runner)
5. PROPRIETARY SCORING   — deterministic lead/signal/market models, not LLM opinions
6. SINGAPORE COMPLIANCE  — PDPA audit trail, consent, right-to-deletion
7. MEASURABLE ROI        — attribution from outreach → meeting → pipeline
8. SINGAPORE CONTEXT     — PSG grants, ACRA data, MAS regulations baked in
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScoringLayer:
    name: str
    description: str
    data_sources: list[str]
    algorithm: str
    output: str
    why_not_llm: str


@dataclass
class CompetitiveAdvantage:
    dimension: str
    gtm_advisor: str
    chatgpt: str
    evidence: str


class WhyUsMethodology:
    """Documents the Kairos methodology and competitive differentiation.

    Use this in onboarding, sales, and support to explain the product's value.
    """

    SCORING_STACK: list[ScoringLayer] = [
        ScoringLayer(
            name="ICP Fit Score",
            description="Deterministic match between a lead's firmographics and the client's Ideal Customer Profile",
            data_sources=["ACRA company registry", "Lead enrichment data", "Client ICP definition"],
            algorithm="Weighted multi-criteria scoring: industry(25%) + size(20%) + location(15%) + stage(10%) + tech(15%) + signals(15%)",
            output="Score 0-1 with component breakdown and reasoning text",
            why_not_llm="LLM scoring is non-deterministic — same lead scores differently each run. Our algorithm always gives the same answer for the same inputs.",
        ),
        ScoringLayer(
            name="Market Context Score",
            description="Is RIGHT NOW a good time to run outreach in this industry?",
            data_sources=["EODHD Singapore economic indicators (live)", "NewsAPI sector sentiment (last 7 days)"],
            algorithm="Macro score (EODHD GDP/PMI/confidence) × 0.40 + Sentiment score (NewsAPI positive/negative ratio) × 0.60",
            output="OpportunityWindow: GREEN / AMBER / RED with detailed reasoning",
            why_not_llm="ChatGPT has a knowledge cutoff. It cannot tell you that Singapore PMI dropped this week or that sector news turned negative yesterday.",
        ),
        ScoringLayer(
            name="Signal Relevance Score",
            description="How actionable is this market signal for THIS specific client?",
            data_sources=["Perplexity real-time web research", "NewsAPI", "EODHD financial news"],
            algorithm="Trigger quality(25%) + Industry match(30%) + Competitor mention(25%) + Recency(20%) + Singapore bonus",
            output="ScoredSignal with urgency classification and recommended action",
            why_not_llm="ChatGPT will call every signal 'potentially relevant'. Our scorer gives precise relevance scores and urgency tiers so you act on the right signals.",
        ),
        ScoringLayer(
            name="Lead Data Quality Score",
            description="Is this lead's data good enough to send outreach without hurting deliverability?",
            data_sources=["DNS MX record lookup (real-time)", "Email format validation", "Role seniority parsing"],
            algorithm="Email deliverable(hard gate) + Completeness(30%) + Seniority(25%) + Company verified(20%) + Email quality(15%) + Freshness(10%)",
            output="LeadQualityReport with qualification decision and blockers list",
            why_not_llm="ChatGPT generates leads that look real but have invalid emails. A single bad batch send can blacklist your domain permanently. We verify before we send.",
        ),
        ScoringLayer(
            name="Playbook Fit Score",
            description="Which outreach strategy maximises win probability given current context?",
            data_sources=["Lead count and quality distribution", "Competitor signal freshness", "Market opportunity rating", "Singapore PSG eligibility"],
            algorithm="Rule-based selector scoring 6 playbook types on contextual fit",
            output="PlaybookRecommendation with primary + secondary option and configuration hints",
            why_not_llm="ChatGPT will suggest 'try personalised outreach' for every situation. Our scorer picks the specific playbook with the highest win probability for your exact context.",
        ),
    ]

    COMPETITIVE_ADVANTAGES: list[CompetitiveAdvantage] = [
        CompetitiveAdvantage(
            dimension="Data freshness",
            gtm_advisor="Live EODHD + NewsAPI + Perplexity data pulled at scoring time",
            chatgpt="Knowledge cutoff — cannot access data from the last few months",
            evidence="Ask ChatGPT about Singapore PMI last week. It will say it doesn't know.",
        ),
        CompetitiveAdvantage(
            dimension="Persistent memory",
            gtm_advisor="Company workspace persists — leads, sequences, signals, history all saved",
            chatgpt="Context window only — starts fresh every conversation",
            evidence="Open a new ChatGPT conversation and ask about your leads from yesterday.",
        ),
        CompetitiveAdvantage(
            dimension="Autonomous execution",
            gtm_advisor="Sends emails, updates HubSpot CRM, runs sequences while you sleep",
            chatgpt="Outputs text. Cannot send emails, cannot write to any external system.",
            evidence="Ask ChatGPT to send an email to a lead on your behalf.",
        ),
        CompetitiveAdvantage(
            dimension="Continuous monitoring",
            gtm_advisor="Signal monitor runs hourly — detects competitor funding before you check email",
            chatgpt="Requires you to prompt it every time you want new information",
            evidence="ChatGPT cannot alert you when a competitor raises funding.",
        ),
        CompetitiveAdvantage(
            dimension="Deterministic scoring",
            gtm_advisor="Same lead always scores the same — auditable, explainable, comparable",
            chatgpt="Non-deterministic — ask it to score the same lead twice, get different answers",
            evidence="Try scoring the same company in two ChatGPT sessions.",
        ),
        CompetitiveAdvantage(
            dimension="Compliance",
            gtm_advisor="PDPA consent tracking, audit trail, right-to-deletion, Singapore-specific",
            chatgpt="No compliance layer. No audit trail. No consent management.",
            evidence="ChatGPT has no PDPA awareness or unsubscribe management.",
        ),
        CompetitiveAdvantage(
            dimension="ROI measurement",
            gtm_advisor="Attribution from outreach email → reply → meeting → pipeline value",
            chatgpt="Cannot measure anything — produces text, not tracked outcomes",
            evidence="ChatGPT cannot tell you whether its advice generated revenue.",
        ),
        CompetitiveAdvantage(
            dimension="Singapore context",
            gtm_advisor="PSG grant plays, ACRA company data, MAS regulatory signals built-in",
            chatgpt="Generic global knowledge — no PSG grant cycles, no ACRA lookups",
            evidence="Ask ChatGPT to look up a company in ACRA. It cannot.",
        ),
    ]

    @classmethod
    def get_elevator_pitch(cls) -> str:
        return (
            "Kairos is not a chatbot. It's an always-on AI workforce that monitors "
            "your market every hour, scores your leads against live economic data, and "
            "executes personalised outreach sequences on your behalf — with human approval "
            "before every send. ChatGPT gives you advice. Kairos takes action."
        )

    @classmethod
    def get_sme_objection_handlers(cls) -> dict[str, str]:
        return {
            "Can't I just use ChatGPT for free?": (
                "ChatGPT gives you a one-time answer. Kairos gives you a running system. "
                "ChatGPT can't send an email, can't check if your lead's email is valid, "
                "can't monitor when your competitor raises funding at 2am, and can't prove "
                "it generated a single SGD of pipeline. We can."
            ),
            "Isn't this just AI-generated spam?": (
                "Every email is personalised using live company data and requires your approval "
                "before sending. Our Lead Data Quality Scorer blocks invalid emails before they "
                "reach the queue. You review every batch — we just do the preparation work."
            ),
            "Will this comply with PDPA?": (
                "Yes. We track consent source and date for every contact, maintain a suppression "
                "list for unsubscribes, log every send action with the approving user, and provide "
                "a right-to-deletion endpoint. All data can be hosted in Singapore."
            ),
            "How is this different from HubSpot or Apollo?": (
                "HubSpot and Apollo are tools you configure. Kairos is a workforce that works. "
                "It monitors signals, scores opportunities, designs the playbook, drafts the emails, "
                "and manages the sequences — with you approving actions, not configuring workflows. "
                "Plus it's built for Singapore SMEs with ACRA data and PSG grant context."
            ),
            "What if the AI sends a bad email?": (
                "It can't — without your approval. Every outreach batch enters an Approval Queue. "
                "You preview every email before it sends. You can edit, reject, or approve "
                "individually. The AI does the preparation; you maintain control."
            ),
        }

    @classmethod
    def to_dict(cls) -> dict[str, Any]:
        return {
            "elevator_pitch": cls.get_elevator_pitch(),
            "scoring_layers": [
                {
                    "name": layer.name,
                    "description": layer.description,
                    "data_sources": layer.data_sources,
                    "algorithm": layer.algorithm,
                    "output": layer.output,
                    "why_not_llm": layer.why_not_llm,
                }
                for layer in cls.SCORING_STACK
            ],
            "competitive_advantages": [
                {
                    "dimension": adv.dimension,
                    "gtm_advisor": adv.gtm_advisor,
                    "chatgpt": adv.chatgpt,
                    "evidence": adv.evidence,
                }
                for adv in cls.COMPETITIVE_ADVANTAGES
            ],
            "objection_handlers": cls.get_sme_objection_handlers(),
        }
