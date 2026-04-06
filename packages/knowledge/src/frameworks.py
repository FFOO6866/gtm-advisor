"""Static marketing frameworks distilled from reference literature.

Layer 1 of the Kairos knowledge synthesis pipeline.  These are
hand-curated, structured representations of the most important frameworks from
the 14 reference books.  They are always available — no PDF parsing, no
embeddings, no network calls.

Every agent can import these constants directly and reference them in prompts
or decision logic without touching the RAG pipeline.

Sources synthesised:
- Kotler & Keller — Marketing Management 14e (STP, 4Ps, Brand Equity)
- Cialdini — Influence: The Psychology of Persuasion (6 Principles)
- Heath & Heath — Made to Stick (SUCCESs framework)
- Ogilvy on Advertising (copywriting principles)
- New Rules of Marketing & PR — David Meerman Scott
- Just Listen — Mark Goulston (objection handling)
- Digital Marketing Strategy — Kingsnorth (RACE framework)
- Marketing Strategy — various B2B GTM models
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Cialdini's 6 Principles of Persuasion
# ---------------------------------------------------------------------------

CIALDINI_PRINCIPLES: dict[str, dict] = {
    "reciprocity": {
        "description": (
            "People feel obligated to give back to others who have given to them first. "
            "When you do something for someone first — give a gift, provide a favour, or "
            "share valuable information — they feel a psychological debt that compels them "
            "to reciprocate."
        ),
        "application": (
            "Lead with value before asking for anything. Provide free insights, audits, "
            "calculators, or content that genuinely helps the prospect. For Singapore SMEs: "
            "offer a complimentary GTM health-check, a free PSG grant eligibility assessment, "
            "or a tailored market report before pitching your solution."
        ),
        "example": (
            "A Singapore SaaS vendor targeting F&B SMEs sends a free 'Digital Readiness "
            "Report' benchmarking the prospect against industry peers. The report is "
            "personalised, data-rich, and costs the vendor ~15 minutes of analysis. "
            "Prospects who receive it are 3x more likely to take a demo call."
        ),
        "best_for": ["cold outreach", "content marketing", "trial offers", "freemium"],
        "sg_angle": (
            "Frame value delivery around PSG-eligible tools, EnterpriseSG programmes, "
            "or MAS regulatory guidance — things Singapore SME decision-makers actively seek."
        ),
    },
    "commitment_consistency": {
        "description": (
            "Once people commit to a position, publicly or privately, they tend to behave "
            "consistently with that commitment. Small initial commitments make larger subsequent "
            "commitments far more likely (the foot-in-the-door technique)."
        ),
        "application": (
            "Start with micro-commitments: a webinar signup, a quiz, a short survey, a 15-minute "
            "discovery call. Each 'yes' primes the prospect to say yes to bigger asks. "
            "Use onboarding sequences that celebrate early actions to create consistent behaviour. "
            "Get prospects to articulate their goals in their own words — they will then feel "
            "compelled to act on those goals."
        ),
        "example": (
            "A B2B HR-tech company in Singapore gets prospects to complete a 3-question "
            "'HR Efficiency Quiz.' The quiz result page shows a personalised score and asks "
            'if the prospect "agrees" that improving in those areas is a priority. Once they '
            "click 'Yes, this is a priority,' subsequent emails reference that commitment, "
            "dramatically increasing demo conversion rates."
        ),
        "best_for": ["lead nurturing", "onboarding sequences", "trial-to-paid conversion"],
        "sg_angle": (
            "Reference Singapore-specific compliance commitments (e.g., 'You mentioned MOM "
            "compliance is a priority — here is how we automate that')."
        ),
    },
    "social_proof": {
        "description": (
            "People look to the behaviour and choices of others, especially similar others, "
            "to determine the correct course of action. Testimonials, case studies, star "
            "ratings, and 'X companies are using this' signals all leverage social proof."
        ),
        "application": (
            "Lead with industry-specific case studies. For Singapore B2B: name-drop "
            "recognisable local brands or verticals (F&B, fintech, logistics, healthcare). "
            "Show logos. Use exact metrics (not 'improved efficiency' but '37% reduction in "
            "manual reporting hours'). Highlight awards, press mentions, and EnterpriseSG "
            "or MAS endorsements where applicable."
        ),
        "example": (
            "An inventory management SaaS adds a banner: '47 Singapore F&B chains, including "
            "Jumbo Group suppliers, have cut wastage by 28% with [Product].' This converts "
            "significantly better than generic 'trusted by thousands of businesses' messaging."
        ),
        "best_for": ["landing pages", "proposal decks", "case studies", "ads"],
        "sg_angle": (
            "Singapore buyers are highly relationship-driven. Peer referrals from the same "
            "industry association (e.g., SRA, ABS, SFIC) carry outsized weight. "
            "Mention shared networks explicitly."
        ),
    },
    "authority": {
        "description": (
            "People follow the lead of credible, knowledgeable experts. Authority signals "
            "include credentials, publications, speaking engagements, media features, "
            "certifications, and confident, specific communication."
        ),
        "application": (
            "Establish thought leadership before selling. Publish research, speak at "
            "industry events (e.g., Singapore FinTech Festival, F&B Asia), contribute to "
            "industry publications (The Business Times, e27, Tech in Asia). "
            "In outreach, reference specific expertise: 'We work exclusively with Series A–C "
            "fintechs navigating MAS DTSP licensing' signals authority far more than generic claims."
        ),
        "example": (
            "A GRC software vendor targeting Singapore banks creates a detailed white paper "
            "on MAS Notice 655 compliance requirements. Every cold email references this paper. "
            "The authority signal (demonstrating deep regulatory knowledge) triples reply rates "
            "compared to feature-led outreach."
        ),
        "best_for": ["thought leadership", "enterprise sales", "regulated industries"],
        "sg_angle": (
            "MAS, EDB, EnterpriseSG, and government body endorsements or partnerships are "
            "enormous authority signals in Singapore. Any government certification or pilot "
            "programme participation should be prominently featured."
        ),
    },
    "liking": {
        "description": (
            "People prefer to say yes to those they know, like, and trust. Liking is "
            "generated by similarity, familiarity, compliments, association with positive "
            "things, and genuine personal interest in the other person."
        ),
        "application": (
            "Personalise outreach beyond just using the prospect's first name. Reference "
            "their LinkedIn posts, company milestones, industry news affecting them, or "
            "shared connections. Mirror their language. For Singapore: acknowledge local "
            "context (CNY plans, National Day campaigns, Budget implications for their sector)."
        ),
        "example": (
            "A sales rep references that the target CEO spoke at a recent Singapore Business "
            "Federation event and shares a specific insight from that talk in the cold email. "
            "The email does not feel like outreach — it feels like a peer conversation. "
            "Reply rate increases from 4% to 19%."
        ),
        "best_for": ["cold outreach", "enterprise relationship selling", "community building"],
        "sg_angle": (
            "Singapore's business community is small and relationship-dense. Shared "
            "alumni networks (NUS, NTU, SMU, INSEAD), industry associations, and hawker "
            "lunch circuits all matter. Reference mutual connections early."
        ),
    },
    "scarcity": {
        "description": (
            "People want more of what they can have less of. Scarcity — whether of time, "
            "quantity, or access — dramatically increases perceived value and urgency to act. "
            "Loss aversion (Kahneman) amplifies this: people are more motivated to avoid "
            "losing something than to gain something of equal value."
        ),
        "application": (
            "Create genuine scarcity, not fake urgency. Limited cohort sizes, exclusive "
            "beta access, limited advisory slots, time-boxed pricing aligned with genuine "
            "events (Q4 budget cycles, PSG grant tranche closing, FY-end). "
            "Frame as what they will lose by not acting, not just what they will gain."
        ),
        "example": (
            "A Singapore RegTech vendor ties their proposal to the SME Digitalisation Grant "
            "tranche deadline: 'The current PSG tranche closes 31 March. Companies that miss "
            "this window will need to fund 100% of implementation cost themselves — a "
            "difference of SGD 30,000 on average.' This converts decision-deferring prospects "
            "into active buyers."
        ),
        "best_for": ["closing", "trial urgency", "pricing conversations", "grant-linked offers"],
        "sg_angle": (
            "PSG grant tranches, EnterpriseSG programme windows, and Singapore Budget "
            "incentive timelines create real, credible scarcity that Singapore SME buyers "
            "understand and respond to."
        ),
    },
}

# ---------------------------------------------------------------------------
# Messaging Frameworks
# ---------------------------------------------------------------------------

MESSAGING_FRAMEWORKS: dict[str, dict] = {
    "AIDA": {
        "stages": ["Attention", "Interest", "Desire", "Action"],
        "description": (
            "The classic awareness-to-conversion funnel model. Originally from advertising "
            "theory (E. St. Elmo Lewis, 1898), refined for digital marketing. Every "
            "piece of communication should move the audience through all four stages."
        ),
        "stage_guidance": {
            "Attention": (
                "Lead with a bold, relevant hook — a surprising statistic, a provocative "
                "question, or a striking visual. Must stop the scroll or beat the delete reflex."
            ),
            "Interest": (
                "Demonstrate relevance to the reader's specific situation. Use their "
                "industry, their role, their current problem. Do not pivot to your solution yet."
            ),
            "Desire": (
                "Show the transformed future state. Use before/after, case study metrics, "
                "or vivid outcome descriptions. Connect emotionally to the gain."
            ),
            "Action": (
                "One clear, low-friction CTA. Never give two options — it splits attention. "
                "'Book a 20-min call' beats 'Visit our website or book a call or email us.'"
            ),
        },
        "best_for": "Email marketing, landing pages, LinkedIn ads, outreach sequences",
        "example": (
            "Attention: 'Singapore manufacturers lose SGD 2.3M annually to unplanned downtime.' "
            "Interest: 'If your team still uses spreadsheets for maintenance scheduling, you are "
            "likely in the top quartile of that cost.' "
            "Desire: 'Acme Manufacturing reduced downtime by 41% in 90 days using predictive "
            "maintenance alerts.' "
            "Action: 'See if your plant qualifies for a free efficiency audit — 20 minutes, "
            "no slides, immediate insights.'"
        ),
        "sg_sme_adaptation": (
            "Singapore SMEs respond to tangible ROI framing. Open with a Singapore-specific "
            "data point (MAS, EnterpriseSG, industry association data preferred over global stats)."
        ),
    },
    "PAS": {
        "stages": ["Problem", "Agitate", "Solution"],
        "description": (
            "Dan Kennedy's direct-response copywriting framework. Identifies and amplifies the "
            "pain before presenting the solution. Highly effective for cold outreach because it "
            "demonstrates empathy and understanding before selling."
        ),
        "stage_guidance": {
            "Problem": (
                "Name the specific problem the prospect has, in their own language. "
                "Avoid jargon. Be precise — 'manual invoice reconciliation' beats 'finance inefficiency.'"
            ),
            "Agitate": (
                "Explore the downstream consequences of that problem. What does it cost them "
                "(time, money, risk, stress, reputation)? The goal is to make the status quo "
                "feel MORE uncomfortable than the change required to fix it."
            ),
            "Solution": (
                "Present your solution as the specific, credible answer to the agitated pain. "
                "Not 'we offer X feature' but 'companies like yours eliminate this problem by...'"
            ),
        },
        "best_for": "Cold email, cold LinkedIn messages, landing page hero sections, webinar pitches",
        "example": (
            "Problem: 'Most Singapore logistics SMEs spend 12+ hours per week manually "
            "reconciling delivery records across WhatsApp, email, and spreadsheets.' "
            "Agitate: 'That is 600+ hours per year your ops team cannot spend on route "
            "optimisation, customer relationships, or scaling new verticals. And one "
            "missed delivery dispute can cost SGD 5,000+ in penalties and reputational damage.' "
            "Solution: 'RouteSync consolidates all delivery data into one dashboard. "
            "3Flow Logistics (Jurong) cut reconciliation time by 85% in their first month.'"
        ),
        "sg_sme_adaptation": (
            "Agitate around MOM compliance risk, government audit exposure, and competitive "
            "pressure from larger players — all potent pain points for Singapore SMEs."
        ),
    },
    "FAB": {
        "stages": ["Features", "Advantages", "Benefits"],
        "description": (
            "Converts product specifications into customer value. Features describe what the "
            "product IS or DOES. Advantages explain why the feature matters in the abstract. "
            "Benefits answer the customer's real question: 'What's in it for me?'"
        ),
        "stage_guidance": {
            "Features": (
                "The objective specifications: 'Our platform processes invoices in real time.' "
                "Do not lead with features — they are table stakes."
            ),
            "Advantages": (
                "Why this feature is better than alternatives: 'Unlike batch-processing systems, "
                "real-time processing means zero overnight reconciliation lag.'"
            ),
            "Benefits": (
                "The customer outcome: 'Your finance team leaves at 6pm instead of 9pm, "
                "and month-end close takes 2 days instead of 5.'"
            ),
        },
        "best_for": "Product demos, RFP responses, sales deck feature slides, one-pagers",
        "example": (
            "Feature: 'AI-powered contract analysis with MAS clause library.' "
            "Advantage: 'Automatically flags clauses that violate MAS FAA Section 36 requirements.' "
            "Benefit: 'Your compliance team reviews exceptions only — a process that took "
            "3 lawyers 2 weeks now takes 1 analyst 4 hours, with fewer human errors.'"
        ),
        "sg_sme_adaptation": (
            "Connect benefits to Singapore-specific regulatory outcomes, grant eligibility, "
            "and measurable cost savings in SGD."
        ),
    },
    "STAR": {
        "stages": ["Situation", "Task", "Action", "Result"],
        "description": (
            "Structured case study and testimonial framework. Provides the narrative context "
            "that makes results credible and memorable. Originally from behavioural interview "
            "methodology, now widely used in B2B marketing storytelling."
        ),
        "stage_guidance": {
            "Situation": (
                "Set the scene: company size, industry, the specific challenge. "
                "Be specific enough to trigger identification ('that sounds like us')."
            ),
            "Task": (
                "What they needed to achieve — their goal or mandate."
            ),
            "Action": (
                "How your solution addressed the task. Specific steps, not generic claims."
            ),
            "Result": (
                "Quantified outcomes with timeframe. '37% reduction in X within 90 days' "
                "is infinitely more compelling than 'significant improvement in X.'"
            ),
        },
        "best_for": "Case studies, testimonial videos, proposal appendices, sales references",
        "example": (
            "Situation: 'TechRetail Pte Ltd, a 60-person Singapore electronics retailer, "
            "was processing SGD 2M/month in inventory manually across 3 warehouses.' "
            "Task: 'The ops director needed to reduce shrinkage and speed up order fulfilment "
            "ahead of the holiday peak season.' "
            "Action: 'Deployed [Platform] in 3 weeks, integrated with their existing POS "
            "system, trained 12 warehouse staff.' "
            "Result: 'Shrinkage fell 52% in Q4. Fulfilment SLA hit 99.1% through peak. "
            "ROI achieved in month 2.'"
        ),
        "sg_sme_adaptation": (
            "Use recognisable Singapore company types (hawker chain, logistics hub, "
            "MAS-regulated entity) and cite SGD figures for immediate local relevance."
        ),
    },
    "BAB": {
        "stages": ["Before", "After", "Bridge"],
        "description": (
            "Transformation storytelling framework. Shows the painful before state, paints "
            "the desirable after state, then positions your product as the bridge. "
            "Particularly powerful because it leads with aspiration, not features."
        ),
        "stage_guidance": {
            "Before": (
                "Describe the current painful reality in vivid, relatable terms. "
                "Use the prospect's own language (listen to how they describe their problem)."
            ),
            "After": (
                "Paint the vision of the transformed state. Make it specific and aspirational. "
                "What does their world look like after the problem is solved?"
            ),
            "Bridge": (
                "Position your solution as the specific mechanism that creates the transformation. "
                "Keep this brief — desire should outweigh explanation."
            ),
        },
        "best_for": "Transformation stories, homepage hero copy, executive presentations, webinar openers",
        "example": (
            "Before: 'Your sales team chases 200 cold leads per month and converts 2. "
            "Your AEs spend 6 hours per week on manual CRM data entry instead of selling.' "
            "After: 'Imagine a pipeline where every lead is pre-qualified, every contact record "
            "is auto-enriched, and your AEs spend 6 hours per day in meaningful conversations.' "
            "Bridge: 'Kairos identifies and scores your ideal prospects using live market "
            "signals, pre-enriches them with firmographic data, and queues personalised outreach "
            "— automatically.'"
        ),
        "sg_sme_adaptation": (
            "Before state should reference recognisable Singapore business realities: "
            "tight margins, labour shortage pressures, regulatory compliance burden."
        ),
    },
    "SOAR": {
        "stages": ["Strengths", "Opportunities", "Aspirations", "Results"],
        "description": (
            "Positive-focused strategic framework (alternative to SWOT). Instead of dwelling "
            "on weaknesses and threats, SOAR focuses on building from strength and opportunity. "
            "Particularly useful for messaging to growth-oriented SME owners."
        ),
        "stage_guidance": {
            "Strengths": "What the customer already does well — acknowledge their foundation.",
            "Opportunities": "Where the market is moving that benefits them.",
            "Aspirations": "What they want to become — the 3-year vision.",
            "Results": "What measurable outcomes will confirm they have arrived.",
        },
        "best_for": "Executive workshops, strategic account reviews, visionary pitch decks",
        "example": (
            "Used in GTM strategy workshops: 'Your team has deep domain expertise in halal "
            "certification (Strength). ASEAN halal food exports are growing 14% YoY (Opportunity). "
            "You want to become the go-to halal F&B supplier for ASEAN hotel chains (Aspiration). "
            "Success looks like 5 new hotel chain contracts worth SGD 3M by 2026 (Results).'"
        ),
        "sg_sme_adaptation": (
            "Aspirations should reference Singapore's ASEAN hub position — "
            "regional expansion is a common SME aspiration. Connect to EDB, Trade SG, and "
            "SG-FTAs as opportunity enablers."
        ),
    },
}

# ---------------------------------------------------------------------------
# Ogilvy Copywriting Principles
# ---------------------------------------------------------------------------

OGILVY_PRINCIPLES: list[dict] = [
    {
        "principle": "The headline is worth 80 cents of every dollar",
        "description": (
            "On average, 5x as many people read the headline as read the body copy. "
            "If you have not sold the prospect with your headline, you have wasted 80% of your money. "
            "Every headline must either promise a benefit, deliver news, arouse curiosity, or "
            "offer a fast, easy way to get something the reader wants."
        ),
        "application": (
            "For cold email: the subject line IS the headline. A/B test it obsessively. "
            "For landing pages: the H1 must do the selling. Do not be clever — be clear."
        ),
        "example": (
            "Weak: 'Introducing Our New Inventory Management Platform.' "
            "Strong: 'Singapore Retailers: Cut Shrinkage 30% or Pay Nothing.' "
            "The second leads with a specific promise, a named audience, and a risk reversal."
        ),
    },
    {
        "principle": "Do not treat your audience as morons — they are your spouse",
        "description": (
            "Write to your audience as you would write to a highly intelligent adult who happens "
            "not to know your product or industry yet. Condescension kills trust. "
            "Respect their intelligence while removing all assumed knowledge."
        ),
        "application": (
            "Avoid buzzwords, acronyms, and jargon without explanation. Write at a Grade 8–10 "
            "reading level. Use short sentences. Assume the reader is smart but busy, not dumb."
        ),
        "example": (
            "Instead of 'Our AI-powered ML-driven SaaS leverages predictive analytics to optimise "
            "your operational throughput KPIs,' write: 'Our software predicts machine failures "
            "before they happen. You schedule maintenance on your terms, not the machine's.'"
        ),
    },
    {
        "principle": "Big ideas are the currency of advertising",
        "description": (
            "Unless your campaign is built around a big idea, it will pass like a ship in the night. "
            "A big idea can be summarised in one sentence and immediately understood as relevant and "
            "interesting. Big ideas tend to endure and can be expressed across all media."
        ),
        "application": (
            "Before writing any campaign, ask: 'What is the single, big, true thing we want people "
            "to associate with our brand?' Then build every piece of communication from that idea. "
            "Do not launch campaigns without a big idea — you will waste budget on noise."
        ),
        "example": (
            "Big idea for a Singapore HR-tech platform: 'Your people actually want to work here.' "
            "Every email, ad, and content piece flows from this — featuring employee stories, "
            "retention stats, and culture metrics. The idea is memorable, emotional, and differentiated."
        ),
    },
    {
        "principle": "Specificity is the soul of credibility",
        "description": (
            "Vague claims are ignored. Specific claims are believed. '37%' is more persuasive "
            "than 'significantly.' 'The Rolls-Royce of invoice automation' is more memorable "
            "than 'a leading accounts payable solution.' Ogilvy was famous for researching "
            "products until he found a genuinely specific, true claim."
        ),
        "application": (
            "Replace every vague adjective with a specific number or name. 'Fast' becomes "
            "'processes in 3 seconds.' 'Trusted' becomes 'used by 214 Singapore SMEs.' "
            "'Affordable' becomes 'SGD 299/month, less than one hour of your finance team's time.'"
        ),
        "example": (
            "Ogilvy's famous Rolls-Royce ad headline: 'At 60 miles an hour the loudest noise in "
            "the new Rolls-Royce comes from the electric clock.' Apply this: instead of "
            "'exceptional customer support,' write: 'Median first-response time: 7 minutes. "
            "Across 3,000 tickets in 2024, we missed SLA twice.'"
        ),
    },
    {
        "principle": "Testimonials and facts outperform claims",
        "description": (
            "Third-party endorsement is always more credible than self-promotion. "
            "Ogilvy consistently found that ads featuring real customer stories, "
            "research findings, and specific facts outperformed pure brand claims by large margins."
        ),
        "application": (
            "Lead with proof, not claims. Every major claim should have supporting evidence: "
            "a customer quote, a case study metric, a third-party study, or regulatory citation. "
            "The ratio should be 80% proof, 20% claim."
        ),
        "example": (
            "Instead of 'Our platform accelerates your sales cycle,' write: "
            "'\"We closed 4 deals in the time it used to take us to close 1.\" "
            "— Marcus Tan, VP Sales, FinTech Ventures Pte Ltd (80-person Series B, Singapore).'"
        ),
    },
    {
        "principle": "Give the reader useful information and they will read your ad",
        "description": (
            "Editorial-style advertising — advertorials, how-to guides, educational content "
            "— outperforms pure promotional advertising. If your ad teaches something valuable, "
            "readers engage with it as content, not as an interruption."
        ),
        "application": (
            "Content marketing before it had a name. For B2B: white papers, how-to guides, "
            "benchmark reports, and calculators earn more attention than product promotion. "
            "The content does the selling by demonstrating expertise and generating reciprocity."
        ),
        "example": (
            "A B2B payroll SaaS publishes 'The Singapore SME HR Compliance Checklist: "
            "MOM, CPF, and SDL requirements for 2025.' This piece ranks organically, "
            "generates 500+ downloads per month, and converts at 8% to demo requests — "
            "higher than any paid ad campaign."
        ),
    },
    {
        "principle": "Never run an advertisement you would be ashamed for your family to see",
        "description": (
            "Ethical advertising builds long-term brand equity. Deceptive claims, "
            "manipulative tactics, and dishonest urgency corrode trust faster than any "
            "short-term conversion gain is worth. Brand reputation compounds over time."
        ),
        "application": (
            "All scarcity must be genuine. All testimonials must be real. All metrics must "
            "be achievable. All claims must be provable. For Singapore: PDPA compliance in "
            "all data-driven outreach is non-negotiable."
        ),
        "example": (
            "Do not create fake 'limited spots' if spots are unlimited. Do not claim "
            "'most loved by Singapore businesses' without data. Do not use opt-out "
            "dark patterns on subscription cancellation flows."
        ),
    },
]

# ---------------------------------------------------------------------------
# Made to Stick — SUCCESs Framework (Heath & Heath)
# ---------------------------------------------------------------------------

MADE_TO_STICK_SUCCESS: dict[str, dict] = {
    "Simple": {
        "description": (
            "Find the core of the idea — the single most important thing — and express "
            "it without burying it in supporting detail. Simple does not mean dumbed-down; "
            "it means ruthlessly prioritised. A Commander's Intent is simple: even if the "
            "battle plan falls apart, everyone knows the core objective."
        ),
        "application": (
            "Before writing any message: 'What is the ONE thing I want this person to "
            "remember?' Strip everything else. Use the 'curse of knowledge' check: can "
            "someone outside your industry understand this immediately?"
        ),
        "example": (
            "Kairos's simple core idea: 'Real GTM strategy, not generic AI advice.' "
            "Every feature, message, and campaign should reinforce this single idea. "
            "When a message has three equally prominent ideas, it has no ideas."
        ),
        "anti_pattern": "Burying the lead. Writing a 500-word email when 50 words would do.",
    },
    "Unexpected": {
        "description": (
            "Violate expectations to generate interest. Curiosity is created by gaps "
            "in knowledge — open a gap, then fill it. The best hooks create a puzzle "
            "the audience wants solved. Counterintuitive facts are more memorable than "
            "confirmatory ones."
        ),
        "application": (
            "Lead with a surprising, counterintuitive, or unexpected fact. Contrast with "
            "what your audience assumes to be true. Create cliffhangers in email subject "
            "lines and first sentences. Use mystery to pull readers forward."
        ),
        "example": (
            "Subject line: 'The Singapore startup that lost money by closing more deals.' "
            "This creates a curiosity gap — how does closing more deals cause a loss? "
            "The email then explains CAC payback problems, leading naturally to the solution."
        ),
        "anti_pattern": "Opening emails with 'I hope this finds you well' or 'My name is X and I work at Y.'",
    },
    "Concrete": {
        "description": (
            "Abstract ideas are forgettable. Concrete images are sticky. "
            "When concepts are grounded in sensory, human-scale terms, they transfer "
            "accurately and are remembered long after abstract counterparts are forgotten. "
            "'Kerning' means nothing to a non-designer; 'the space between letters' means everything."
        ),
        "application": (
            "Translate every abstract benefit into a concrete, human-scale image. "
            "Not 'operational efficiency' but 'your ops manager leaves at 5:30pm on Fridays.' "
            "Use numbers, names, and specific scenarios."
        ),
        "example": (
            "Concrete: 'In the time it takes you to read this email, three Singapore SME "
            "owners have manually keyed the same invoice data into three different systems.' "
            "Abstract: 'Manual data entry is inefficient.' Which is more memorable?"
        ),
        "anti_pattern": "Synergy. Leverage. Ecosystem. Holistic. These words are anti-concrete.",
    },
    "Credible": {
        "description": (
            "Ideas need credentials — but not necessarily the traditional kind. "
            "Statistics help, but vivid details are often more convincing than big numbers "
            "(the 'sinister attribution error' is actually a cognitive shortcut to credibility). "
            "Testable credentials — 'try it before you buy it' — are the most credible of all."
        ),
        "application": (
            "Use specificity as a credibility proxy. '14.3%' beats '~15%.' "
            "Name real customers (with permission). Cite third-party sources. "
            "Offer risk-free trials (the ultimate credibility test: 'we are so confident, "
            "you can validate before paying')."
        ),
        "example": (
            "Credible: 'Our NPS is 72 (industry average: 31). "
            "Source: Qualtrics benchmark report, Q1 2025. "
            "We will let you talk to 3 Singapore reference customers before signing.' "
            "Less credible: 'Our customers love us! 5 stars!'"
        ),
        "anti_pattern": "Self-reported awards, vague 'thousands of customers,' unnamed Fortune 500 clients.",
    },
    "Emotional": {
        "description": (
            "People care about people, not abstractions. When you make people feel something "
            "— worry, pride, hope, excitement — ideas stick. The research shows: even in "
            "supposedly rational B2B buying, emotion drives 70–80% of decisions, "
            "and logic is used post-hoc to justify emotional choices."
        ),
        "application": (
            "Connect your message to identity: 'What kind of leader do you want to be?' "
            "Use specific, named individuals in case studies (not 'a logistics company' "
            "but 'James, the ops director at a 40-person 3PL in Jurong'). "
            "Appeal to aspiration and fear of being left behind."
        ),
        "example": (
            "Emotional: 'Wei Lin was the only one in her finance team still working at "
            "9pm on a Friday — again. Three months after adopting [Platform], she took "
            "her kids to Sentosa on a Friday afternoon for the first time in two years.' "
            "This is more persuasive than '60% reduction in overtime hours.'"
        ),
        "anti_pattern": "Generic stock photos of diverse people smiling at laptops. Buzzword-laden value props.",
    },
    "Stories": {
        "description": (
            "Stories are simulation machines: they allow audiences to mentally rehearse "
            "situations and solutions, priming action. A story with a clear protagonist, "
            "a real conflict, and a resolved ending is the most powerful delivery mechanism "
            "for any idea. People remember stories 22x better than facts alone."
        ),
        "application": (
            "Structure every case study as a story: protagonist (named customer), conflict "
            "(the problem they had before), resolution (how your solution helped), "
            "transformation (their new reality). Use the STAR or BAB framework to scaffold. "
            "In outreach sequences, tell a single story across 3–5 touches."
        ),
        "example": (
            "A 5-email nurture sequence tells one story: "
            "Email 1 — introduces Marcus, a frustrated Singapore CFO. "
            "Email 2 — describes his specific problem (month-end reconciliation nightmare). "
            "Email 3 — shows what he tried and why it failed. "
            "Email 4 — introduces the turning point (discovers your platform at a CFO roundtable). "
            "Email 5 — shares his outcome and invites the prospect to their own turning point."
        ),
        "anti_pattern": "Generic 'company X achieved Y%' bullets with no human narrative.",
    },
}

# ---------------------------------------------------------------------------
# STP Framework (Kotler & Keller — Marketing Management 14e)
# ---------------------------------------------------------------------------

STP_FRAMEWORK: dict[str, dict] = {
    "segmentation": {
        "description": (
            "Dividing a market into distinct groups of buyers who have different needs, "
            "characteristics, or behaviours that might require separate products or marketing mixes. "
            "Effective segmentation requires measurability, accessibility, substantiality, "
            "differentiability, and actionability (Kotler's 5 criteria)."
        ),
        "bases": {
            "demographic": {
                "description": "Age, gender, income, occupation, education, generation, religion, social class",
                "b2b_equivalent": "Company size (employees/revenue), industry (SIC/NAICS), ownership type",
                "sg_application": "Singapore: SME (< SGD 100M revenue), MNC subsidiary, government-linked company",
            },
            "geographic": {
                "description": "Country, region, city, climate, urban/suburban/rural density",
                "b2b_equivalent": "HQ location, office footprint, regional vs. domestic",
                "sg_application": "CBD vs. industrial (Jurong/Tampines), Singapore-only vs. ASEAN-expanding",
            },
            "psychographic": {
                "description": "Lifestyle, values, personality, risk tolerance, innovation appetite",
                "b2b_equivalent": "Culture (risk-averse vs. experimental), tech maturity, growth stage",
                "sg_application": "Traditional family business vs. second-generation startup, PSG-aware vs. grant-naïve",
            },
            "behavioral": {
                "description": "Purchase occasion, usage rate, loyalty, buyer-readiness stage, benefits sought",
                "b2b_equivalent": "Buying trigger (compliance, growth, pain), procurement cycle, incumbent vendor",
                "sg_application": "Currently on manual spreadsheets, actively evaluating, just switched (avoid), FY-end budget spending",
            },
            "firmographic": {
                "description": "B2B-specific: industry vertical, company size, revenue, funding, tech stack",
                "b2b_equivalent": "Primary B2B segmentation base",
                "sg_application": "SSIC code (SG Standard Industrial Classification), UEN entity type, BizFile registered capital",
            },
        },
        "best_practice": (
            "Use 2–3 bases simultaneously for B2B micro-segmentation. "
            "Example: Fintech (vertical) + Series A–B (funding stage) + Singapore-headquartered (geo) "
            "is a precise, actionable segment."
        ),
    },
    "targeting": {
        "description": (
            "Evaluating and selecting which market segment(s) to enter and serve. "
            "Kotler's targeting strategies range from serving all segments with one "
            "undifferentiated offering to ultra-specific individual marketing."
        ),
        "strategies": {
            "undifferentiated": {
                "description": "One product, one message for all — mass marketing",
                "when_to_use": "Homogeneous market with universal needs",
                "sg_b2b_fit": "Rarely appropriate. Only for utility-grade products (e.g., basic email hosting)",
            },
            "differentiated": {
                "description": "Different products/messages for different segments",
                "when_to_use": "Multiple distinct segments with meaningfully different needs",
                "sg_b2b_fit": "Series A fintech vs. F&B chain vs. logistics 3PL all need different GTM",
            },
            "concentrated": {
                "description": "One product, deep focus on one segment",
                "when_to_use": "Limited resources; niche with high willingness to pay",
                "sg_b2b_fit": "Ideal for Singapore SME SaaS startups: own one vertical deeply first",
            },
            "micromarketing": {
                "description": "Local marketing or individual marketing (1:1)",
                "when_to_use": "ABM (account-based marketing) for enterprise; hyperlocal for SME",
                "sg_b2b_fit": "ABM for top 50 target accounts; personalised at-scale for SME outreach",
            },
        },
        "evaluation_criteria": [
            "Segment size and growth rate",
            "Structural attractiveness (Porter's 5 Forces within segment)",
            "Company objectives and resources required",
            "Competitive intensity within segment",
            "Alignment with company's existing strengths",
        ],
    },
    "positioning": {
        "description": (
            "Creating a distinctive, valued place in the minds of the target customers. "
            "Positioning is not what you do to a product — it is what you do to the mind "
            "of the prospect (Ries & Trout). Effective positioning owns one idea or attribute."
        ),
        "approaches": {
            "by_attribute": {
                "description": "Associate with a specific product attribute or feature",
                "example": "'The only HR platform built specifically for Singapore MOM compliance'",
            },
            "by_benefit": {
                "description": "Lead with the customer outcome, not the product attribute",
                "example": "'Close your books 3 days faster every month'",
            },
            "by_use_application": {
                "description": "Associate with a specific use case or occasion",
                "example": "'The GTM platform for Singapore SaaS companies hitting SGD 3M ARR'",
            },
            "by_user": {
                "description": "Associate with a specific user type or identity",
                "example": "'Built by ex-EnterpriseSG advisors, for Singapore founders going regional'",
            },
            "by_competitor": {
                "description": "Position explicitly against a known alternative",
                "example": "'Salesforce for large enterprises. Kairos for Singapore SMEs.'",
            },
            "by_price_quality": {
                "description": "Own the high-value or value-for-money position",
                "example": "'Enterprise-grade GTM intelligence at SME-friendly pricing'",
            },
        },
        "positioning_statement_template": (
            "For [target segment] who [have this problem/need], "
            "[Brand] is the [frame of reference/category] that [point of difference] "
            "because [reason to believe]."
        ),
        "sg_positioning_principles": [
            "Singapore buyers are highly credentials-driven — authority positioning works well",
            "Local proof points (Singapore clients, Singapore case studies) outperform global ones",
            "PSG/EnterpriseSG alignment is a genuine differentiator when true",
            "ASEAN expansion angle resonates with growth-stage Singapore companies",
        ],
    },
}

# ---------------------------------------------------------------------------
# B2B GTM Motion Frameworks
# ---------------------------------------------------------------------------

GTM_FRAMEWORKS: dict[str, dict] = {
    "product_led_growth": {
        "description": (
            "The product itself is the primary driver of acquisition, retention, and expansion. "
            "Users discover value before paying, converting from free/trial to paid through "
            "in-product experience. Growth is viral, bottom-up, and relatively low-CAC."
        ),
        "key_mechanics": [
            "Free tier or freemium with genuine value (not crippled functionality)",
            "Self-serve onboarding — value demonstrated without sales touch",
            "In-product upgrade prompts triggered by usage milestones",
            "Viral loops: sharing, collaboration, public outputs",
            "Product Qualified Leads (PQLs) trigger sales outreach at optimal moment",
        ],
        "metrics": {
            "primary": ["Time-to-value (TTV)", "Product Qualified Lead (PQL) rate", "Free-to-paid conversion %"],
            "secondary": ["DAU/MAU ratio", "Feature adoption depth", "Viral coefficient (K-factor)"],
        },
        "best_for": "Developer tools, collaboration software, productivity apps; SMB/mid-market",
        "sg_sme_fit": (
            "High fit when the product can deliver immediate, tangible value in a free tier. "
            "Singapore SME buyers are cost-sensitive — free trials reduce purchasing friction significantly. "
            "PSG subsidy can lower effective cost to near-PLG levels for qualifying solutions."
        ),
        "when_not_to_use": "Complex enterprise implementations; regulated data requiring security review before trial",
    },
    "sales_led": {
        "description": (
            "Revenue growth is primarily driven by a sales organisation — SDRs generate pipeline, "
            "AEs close, CSMs expand. Product experience matters but it is delivered through "
            "demos, POCs, and guided implementations rather than self-serve. "
            "High ACV, long sales cycle, complex buying committees."
        ),
        "key_mechanics": [
            "Outbound SDR motion (cold outreach, sequencing, multi-touch)",
            "Inbound lead qualification and routing",
            "Discovery → Demo → Proposal → Negotiation → Close process",
            "Multi-stakeholder management (champion, economic buyer, blockers)",
            "Proof of Concept (POC) or paid pilot to de-risk for buyer",
        ],
        "metrics": {
            "primary": ["Pipeline coverage (3–5x quota)", "Win rate", "Average Sales Cycle (days)", "ACV"],
            "secondary": ["SDR to AE conversion %", "Stage conversion rates", "Forecast accuracy"],
        },
        "best_for": "Enterprise software, complex platform deals, regulated industries; ACV > SGD 30,000",
        "sg_sme_fit": (
            "Relevant for selling to mid-market Singapore companies (50–200 employees, SGD 10M+ revenue). "
            "Singapore buyers respect a consultative sale. Government buyers (GLC, statutory boards) "
            "require formal sales process with procurement protocols."
        ),
        "when_not_to_use": "Sub-SGD 5,000 ACV — CAC economics break down at low ACV with high-touch sales",
    },
    "marketing_led": {
        "description": (
            "Demand generation and brand-building drive a predictable inbound pipeline. "
            "Content marketing, SEO, paid acquisition, events, and PR generate awareness "
            "and intent, which converts to MQLs that sales then works. "
            "Typically complementary to sales-led rather than a pure alternative."
        ),
        "key_mechanics": [
            "Content engine: blog, white papers, webinars, podcasts",
            "SEO for high-intent, category-defining keywords",
            "Paid search and social (LinkedIn for B2B Singapore)",
            "Events: hosting or speaking at industry forums",
            "PR: thought leadership in The Business Times, e27, Tech in Asia",
            "Lead magnets: calculators, benchmarks, templates",
        ],
        "metrics": {
            "primary": ["MQL volume", "MQL-to-SQL conversion %", "CAC by channel", "Content-influenced pipeline"],
            "secondary": ["Organic traffic share", "Brand search volume", "Share of Voice vs. competitors"],
        },
        "best_for": "Mid-market SaaS; companies with content expertise and 6+ month runway for SEO to mature",
        "sg_sme_fit": (
            "LinkedIn is the dominant B2B channel in Singapore. "
            "Content in English targeted at Singapore SME owners and C-suite performs well. "
            "Local events (community meetups, industry dinners) have outsized ROI due to Singapore's "
            "small, high-density business community."
        ),
        "when_not_to_use": "Early-stage with < 6 months runway — takes time to compound; not for immediate revenue",
    },
    "community_led": {
        "description": (
            "Community — of customers, practitioners, or advocates — drives acquisition, "
            "retention, and expansion. Members recruit members. The community itself "
            "creates value independent of the product. Brand becomes a rallying point "
            "for a shared identity or mission."
        ),
        "key_mechanics": [
            "Community platforms (Slack, Discord, Circle, WhatsApp groups)",
            "User-generated content and peer case studies",
            "Community events, meetups, and conferences",
            "Ambassador and champion programmes",
            "Co-creation: community input on roadmap",
        ],
        "metrics": {
            "primary": ["Community-sourced pipeline %", "Member NPS", "Community-influenced retention"],
            "secondary": ["Active member rate", "Member-to-member referrals", "Community-generated content volume"],
        },
        "best_for": "Developer tools, practitioner platforms, mission-driven brands",
        "sg_sme_fit": (
            "Singapore's tight-knit business community makes community-led approaches potent. "
            "Industry associations (SRA, ABS, SCCCI, SiTF) serve as ready-made communities. "
            "Partner-with-associations strategies can work exceptionally well for Singapore SME reach."
        ),
        "when_not_to_use": "Products lacking a practitioner identity or shared mission; purely transactional tools",
    },
    "partner_led": {
        "description": (
            "Channel partners — resellers, system integrators, consultants, or technology partners "
            "— become the primary GTM vehicle. Partners bring their existing customer relationships, "
            "local market credibility, and domain expertise. "
            "Revenue scales without proportional headcount growth."
        ),
        "key_mechanics": [
            "Partner recruitment and onboarding programme",
            "Deal registration to protect partner investment",
            "Partner enablement: training, sales playbooks, demo environments",
            "Co-marketing funds (MDF) and joint campaigns",
            "Tiered partner programme with financial incentives",
        ],
        "metrics": {
            "primary": ["Partner-sourced pipeline %", "Partner-influenced revenue", "Partner ACV per partner"],
            "secondary": ["Active partner count", "Partner time-to-first-deal", "Partner retention rate"],
        },
        "best_for": "Products requiring local implementation expertise; markets with strong SI ecosystem",
        "sg_sme_fit": (
            "Extremely relevant for Singapore. PSG pre-approved vendor status means "
            "government-endorsed channel credibility. IT resellers, business consultancies, "
            "and accounting firms serve as natural GTM partners for SME-focused software. "
            "IMDA pre-approved solutions accelerate enterprise procurement."
        ),
        "when_not_to_use": "Products that require proprietary data from customers that partners cannot share",
    },
}

# ---------------------------------------------------------------------------
# Sales Qualification Frameworks
# ---------------------------------------------------------------------------

SALES_QUALIFICATION: dict[str, dict] = {
    "BANT": {
        "description": (
            "IBM's classic qualification framework. Determines whether a prospect is "
            "worth investing sales resources in based on four criteria. Simple and fast "
            "but increasingly supplemented with more nuanced frameworks for complex B2B."
        ),
        "criteria": {
            "Budget": {
                "description": "Has the prospect allocated budget for this purchase?",
                "questions": [
                    "Do you have an allocated budget for solving this problem this year?",
                    "What is the budget range you are working with?",
                    "How is this type of purchase typically funded in your company?",
                ],
                "sg_context": (
                    "Singapore SMEs may have access to PSG grants (up to 50% co-funding). "
                    "Always ask about grant awareness — it can double the effective budget."
                ),
            },
            "Authority": {
                "description": "Is this person the decision-maker, or do we need to access others?",
                "questions": [
                    "Who else would be involved in a decision of this type?",
                    "What does your approval process look like for software purchases?",
                    "Who would need to sign off on a contract at this value?",
                ],
                "sg_context": (
                    "In Singapore family-run SMEs, the founder/owner is often the sole decision-maker. "
                    "In corporates, procurement, IT, and C-suite may all be involved."
                ),
            },
            "Need": {
                "description": "Does the prospect have a genuine, urgent problem your solution solves?",
                "questions": [
                    "What is the cost of not solving this problem in the next 12 months?",
                    "What have you tried already?",
                    "How is this problem ranked vs. other priorities this quarter?",
                ],
                "sg_context": (
                    "Compliance-driven needs (MOM, MAS, PDPA) have genuine urgency in Singapore. "
                    "Frame need discovery around regulatory risk and audit exposure."
                ),
            },
            "Timeline": {
                "description": "When does the prospect need to make a decision and implement?",
                "questions": [
                    "When do you need this solution live?",
                    "Is there a business event driving this timeline (e.g., audit, quarter-end)?",
                    "What happens if implementation slips 3 months?",
                ],
                "sg_context": (
                    "Singapore fiscal years vary (April or January). "
                    "PSG grant windows and Budget incentive timelines create real urgency."
                ),
            },
        },
        "limitation": (
            "BANT is a filter, not a full sales process. It can eliminate good prospects "
            "who simply have not been educated on budget or urgency yet. "
            "Supplement with MEDDIC for complex deals."
        ),
    },
    "MEDDIC": {
        "description": (
            "Enterprise-grade qualification framework developed at PTC. More thorough "
            "than BANT — covers the full buying committee and decision process. "
            "Especially effective for deals > SGD 50,000 ACV with multi-stakeholder decisions."
        ),
        "criteria": {
            "Metrics": {
                "description": "Quantified economic impact of the purchase. The value justification.",
                "application": (
                    "Define the ROI case in the prospect's own language and numbers. "
                    "'Saving 20 hours per week at your finance manager's rate of SGD 35/hour "
                    "= SGD 36,400/year savings against our SGD 12,000 annual subscription.'"
                ),
            },
            "Economic Buyer": {
                "description": "The person who controls the budget and has final authority to sign.",
                "application": (
                    "Identify and access the economic buyer early. Champions are valuable "
                    "but cannot close without the EB's approval. Get time with the EB."
                ),
            },
            "Decision Criteria": {
                "description": "The specific criteria the buying committee will use to evaluate and choose.",
                "application": (
                    "Discover all criteria: technical (integration, security, uptime), "
                    "commercial (price, contract flexibility), and political (vendor reputation, risk)."
                ),
            },
            "Decision Process": {
                "description": "The sequence of steps, stakeholders, and governance required to approve the purchase.",
                "application": (
                    "Map the full procurement journey: demo → security review → legal → "
                    "procurement → board approval → contract. Know every gate."
                ),
            },
            "Identify Pain": {
                "description": "The compelling business reason to change. Pain must be explicitly owned by the buyer.",
                "application": (
                    "Pain must be specific, quantified, and connected to a business outcome "
                    "the economic buyer cares about. 'Operational inefficiency' is not pain. "
                    "'SGD 180,000/year in overtime costs from manual processing' is pain."
                ),
            },
            "Champion": {
                "description": "An internal advocate who wants you to win and will actively sell on your behalf.",
                "application": (
                    "Identify and develop your champion: give them materials to sell internally, "
                    "coach them on objection handling, help them build their own internal business case."
                ),
            },
        },
        "best_for": "Enterprise deals (ACV > SGD 30,000), multi-stakeholder committees, long cycles (3–12 months)",
    },
    "SPIN": {
        "description": (
            "Neil Rackham's research-backed questioning framework (Huthwaite International). "
            "Derived from analysis of 35,000 sales calls. Particularly effective for "
            "complex B2B sales where discovery is critical. Questions are ordered to "
            "guide the prospect to articulate their own need."
        ),
        "criteria": {
            "Situation": {
                "description": "Understand the prospect's current state — context and background.",
                "examples": [
                    "How many people are involved in your current finance reconciliation process?",
                    "What systems do you currently use for managing customer data?",
                    "How long have you been managing this process with spreadsheets?",
                ],
                "warning": "Do not over-use Situation questions — they feel like interrogation if overdone.",
            },
            "Problem": {
                "description": "Uncover the difficulties, dissatisfactions, and problems the prospect has.",
                "examples": [
                    "How much time does your team spend on manual data entry each week?",
                    "What happens when there is an error in the reconciliation process?",
                    "Where does your current process break down most often?",
                ],
            },
            "Implication": {
                "description": (
                    "Explore the consequences and downstream effects of the problem. "
                    "This is where SPIN creates urgency — the prospect articulates their own pain."
                ),
                "examples": [
                    "What impact does that 12-hour reconciliation delay have on your month-end reporting?",
                    "When errors occur, what does it cost in terms of correction time and customer trust?",
                    "How does this limit your team's ability to focus on growth activities?",
                ],
            },
            "Need-Payoff": {
                "description": (
                    "Get the prospect to articulate the value of solving the problem — "
                    "they sell themselves on the solution. The most powerful questions in the framework."
                ),
                "examples": [
                    "If you could eliminate that reconciliation step, what would your team do with those hours?",
                    "How would automated error detection change your audit preparation process?",
                    "What would it mean for your business if you could close the books 3 days faster?",
                ],
            },
        },
        "best_for": "Complex B2B discovery calls, consultative selling, deals with hidden or undefined need",
    },
    "CHALLENGER": {
        "description": (
            "Matthew Dixon & Brent Adamson's research-based model (CEB/Gartner). "
            "The top-performing sales rep archetype: teaches the prospect something new, "
            "tailors the message to their specific context, and constructively controls "
            "the sales process. Challenger reps win by reframing how prospects think "
            "about their business."
        ),
        "criteria": {
            "teach": {
                "description": (
                    "Bring unique, commercially relevant insights the prospect did not know. "
                    "The Challenger opens with a teach that reframes the prospect's business "
                    "problem — ideally in a way that only your solution can solve."
                ),
                "application": (
                    "Lead with a surprising insight about the prospect's industry, market, "
                    "or competitive position. For Singapore: use EnterpriseSG data, "
                    "MAS industry stats, or proprietary benchmarks to reframe their reality."
                ),
                "example": (
                    "'Most Singapore logistics SMEs believe their biggest cost driver is fuel. "
                    "Our analysis of 200 companies shows it is actually unplanned downtime — "
                    "which costs 3x more than fuel per revenue dollar. Here is what that means for you...'"
                ),
            },
            "tailor": {
                "description": (
                    "Customise the message to resonate with the specific stakeholder, their "
                    "vertical, and their personal drivers. CFOs care about ROI and risk. "
                    "Operations directors care about efficiency and control. "
                    "CEOs care about competitive position and growth."
                ),
                "application": (
                    "Build persona-specific teaching maps: the same insight is framed differently "
                    "for the CEO, CFO, and operations head. Research the individual, not just the company."
                ),
            },
            "take_control": {
                "description": (
                    "Proactively guide the deal forward. Challenger reps are comfortable with "
                    "tension and constructively push back on unreasonable demands. "
                    "They do not cave on price without getting something in return."
                ),
                "application": (
                    "Set mutual action plans. Hold the prospect accountable to agreed next steps. "
                    "Challenge objections with data. Ask for the order with confidence. "
                    "Do not let deals stall in perpetual 'evaluation.'"
                ),
            },
        },
        "best_for": "Complex enterprise deals; accounts with entrenched status quo; markets with sophisticated buyers",
        "sg_context": (
            "Challenger approach works well with Singapore CFOs and CEOs of mid-market companies "
            "who are accustomed to vendor relationships and respond to data-driven insight. "
            "May feel aggressive for traditional family business founders — calibrate tone."
        ),
    },
}

# ---------------------------------------------------------------------------
# ICP (Ideal Customer Profile) Framework
# ---------------------------------------------------------------------------

ICP_FRAMEWORK: dict[str, dict] = {
    "description": (
        "A detailed specification of the type of company most likely to buy, succeed with, "
        "and expand their use of your product. A strong ICP makes every downstream GTM "
        "decision more precise: which prospects to target, which message to use, "
        "which channel to invest in, and when to disqualify."
    ),
    "firmographic": {
        "description": "Objective, measurable company attributes",
        "attributes": [
            {
                "name": "company_size",
                "dimensions": ["headcount", "revenue", "office count"],
                "sg_context": "Singapore SME defined as < SGD 100M annual revenue OR < 200 employees",
            },
            {
                "name": "industry_vertical",
                "dimensions": ["primary SSIC code", "sub-vertical", "product vs. service"],
                "sg_context": "Use Singapore Standard Industrial Classification codes for precision",
            },
            {
                "name": "geography",
                "dimensions": ["HQ country", "regional footprint", "expansion stage"],
                "sg_context": "Singapore HQ only vs. ASEAN operations vs. global with SG office",
            },
            {
                "name": "funding_stage",
                "dimensions": ["bootstrapped", "Seed", "Series A/B/C", "PE-backed", "public", "family-owned"],
                "sg_context": "Family-run vs. VC-backed requires completely different GTM and messaging",
            },
            {
                "name": "revenue",
                "dimensions": ["ARR/annual revenue", "revenue model", "revenue trajectory"],
                "sg_context": "SGD denomination; look for companies passing inflection points (hiring sprees, new office)",
            },
        ],
    },
    "technographic": {
        "description": "Technology stack and digital maturity indicators",
        "attributes": [
            {
                "name": "current_tech_stack",
                "dimensions": ["ERP", "CRM", "HRM", "financial systems", "communication tools"],
                "sg_context": "Xero/QuickBooks users are digitally primed. Still on manual/Excel = highest pain",
            },
            {
                "name": "integration_needs",
                "dimensions": ["API-first vs. closed ecosystem", "data portability requirements"],
                "sg_context": "SAP/Oracle shops have complex integration requirements; factor into sales cycle",
            },
            {
                "name": "cloud_maturity",
                "dimensions": ["cloud-native", "hybrid", "on-premise only"],
                "sg_context": "Regulated industries (banking, healthcare) may require on-prem or local cloud",
            },
            {
                "name": "digital_investment_signals",
                "dimensions": ["tech job postings", "LinkedIn tech headcount", "recent software adoption"],
                "sg_context": "Companies hiring for 'digital transformation' or 'IT modernisation' are primed",
            },
        ],
    },
    "behavioral": {
        "description": "Observable buying behaviour patterns",
        "attributes": [
            {
                "name": "buying_triggers",
                "dimensions": [
                    "compliance mandate (regulatory change)",
                    "growth milestone (headcount/revenue threshold)",
                    "pain event (audit failure, data breach, public embarrassment)",
                    "leadership change (new CFO/CTO/CEO)",
                    "funding event (new capital to invest)",
                    "competitive pressure (competitor gains advantage)",
                ],
                "sg_context": "MAS regulatory updates, MOM payroll requirements, PDPA audit cycles are SG-specific triggers",
            },
            {
                "name": "sales_cycle_length",
                "dimensions": ["< 1 month", "1–3 months", "3–6 months", "> 6 months"],
                "sg_context": "Singapore SME decisions are faster for sub-SGD 20k; slower for enterprise",
            },
            {
                "name": "champion_persona",
                "dimensions": ["title", "department", "internal influence", "technical depth"],
                "sg_context": "Operations directors and CFOs tend to champion operational SaaS in SG SMEs",
            },
            {
                "name": "evaluation_process",
                "dimensions": ["self-serve trial", "vendor-led demo", "RFP/tender", "reference calls"],
                "sg_context": "Government-linked companies require formal tender processes; SMEs prefer demos",
            },
        ],
    },
    "psychographic": {
        "description": "Softer attributes around mindset, values, and culture",
        "attributes": [
            {
                "name": "risk_tolerance",
                "dimensions": ["early adopter", "early majority", "conservative", "laggard"],
                "sg_context": "Singapore SMEs are generally conservative; reference customers and proof reduce risk perception",
            },
            {
                "name": "innovation_appetite",
                "dimensions": ["tech-forward", "pragmatic", "compliance-driven only"],
                "sg_context": "SG Startup ecosystem is tech-forward; traditional F&B and manufacturing are pragmatic",
            },
            {
                "name": "values_alignment",
                "dimensions": ["efficiency-focused", "growth-obsessed", "compliance-first", "people-first"],
                "sg_context": "Align to their strategic priority, not just their tactical pain",
            },
            {
                "name": "leadership_ambition",
                "dimensions": ["lifestyle business", "ASEAN ambition", "regional IPO path"],
                "sg_context": "GTM strategy messaging must match their growth horizon",
            },
        ],
    },
    "negative_icp": {
        "description": (
            "Equally important: defining who is NOT a good fit. "
            "Negative ICP prevents wasted sales resources and reduces churn from "
            "customers who were never a good fit."
        ),
        "common_sg_disqualifiers": [
            "Below minimum viable company size (< 10 employees) — insufficient budget and complexity",
            "Sole-proprietorships using consumer tools only — not ready for B2B SaaS",
            "Consumer business model (B2C) when your solution is B2B-only",
            "Industry vertical you have no case studies in — credibility gap too large",
            "Recently switched to a direct competitor — switching cost too high",
            "No IT capability or budget for implementation and change management",
        ],
    },
    "icp_scoring_logic": {
        "description": "How to score and prioritise prospects against ICP",
        "method": (
            "Assign point values to each ICP criterion. Tier A (80–100 points): ideal, "
            "prioritise immediately. Tier B (60–79): good fit, work with standard process. "
            "Tier C (40–59): marginal, lower priority. Below 40: disqualify."
        ),
        "example_scoring": {
            "Singapore HQ": 10,
            "10–200 employees": 15,
            "SGD 2M–50M revenue": 15,
            "Active buying trigger present": 20,
            "Champion identified": 15,
            "Budget confirmed": 10,
            "Competitor using manual process": 10,
            "PSG-eligible industry": 5,
        },
    },
}

# ---------------------------------------------------------------------------
# Singapore SME-Specific Context
# ---------------------------------------------------------------------------

SINGAPORE_SME_CONTEXT: dict[str, dict] = {
    "market_overview": {
        "sme_count": "Over 280,000 SMEs in Singapore (2024)",
        "sme_gdp_contribution": "Approximately 48% of GDP",
        "sme_employment": "Approximately 65% of workforce",
        "key_sectors": [
            "Wholesale & Retail Trade",
            "Professional, Scientific & Technical Services",
            "F&B (Food & Beverage)",
            "Manufacturing",
            "Construction",
            "ICT & Digital Media",
            "Financial Services (fintech)",
            "Logistics & Transport",
        ],
        "digital_adoption_challenges": [
            "High labour costs driving need for automation",
            "Succession planning for traditional family businesses",
            "Competition from larger regional and global players",
            "Need to scale into ASEAN markets with limited resources",
        ],
    },
    "psg_grant": {
        "description": (
            "Productivity Solutions Grant — co-funds adoption of pre-approved IT solutions "
            "and equipment for Singapore SMEs. Administered by EnterpriseSG."
        ),
        "funding_rate": "Up to 50% of qualifying costs (as of 2024)",
        "eligibility": [
            "Business entity registered and operating in Singapore",
            "At least 30% local shareholding",
            "Company's annual sales turnover < SGD 100 million OR fewer than 200 workers",
        ],
        "qualifying_categories": [
            "Customer Management (CRM)",
            "Data Analytics",
            "Financial Management (accounting, payroll)",
            "Inventory Tracking and Management",
            "HR Management",
            "Digital Marketing",
            "Cybersecurity",
            "Project Management",
        ],
        "gtm_angle": (
            "PSG pre-approval is a significant GTM differentiator. "
            "Leads with PSG angle in outreach: 'Our solution is PSG pre-approved — "
            "you pay 50% less to get started.' "
            "This is a genuine urgency and value driver, not manufactured scarcity."
        ),
        "vendor_benefit": (
            "Being a PSG pre-approved vendor signals government endorsement, "
            "reduces buyer risk perception, and enables a large market of subsidised buyers. "
            "The application process is through IMDA and typically takes 3–6 months."
        ),
    },
    "enterprise_sg_alignment": {
        "description": (
            "EnterpriseSG supports Singapore companies to grow and internationalise. "
            "Multiple programmes are relevant GTM angles for B2B vendors."
        ),
        "key_programmes": {
            "Enterprise Development Grant (EDG)": (
                "Supports projects that help companies upgrade business capabilities "
                "and go overseas. Covers up to 50% of qualifying costs."
            ),
            "Market Readiness Assistance (MRA)": (
                "Funds market assessment, business development, and marketing activities "
                "for companies entering new overseas markets."
            ),
            "Scale-Up SG": (
                "Tailored programme for high-growth Singapore companies with ambitions to "
                "become significant regional players."
            ),
            "Startup SG Founder": (
                "SGD 50,000 startup capital grant for first-time entrepreneurs, "
                "matched dollar-for-dollar."
            ),
        },
        "gtm_angle": (
            "Frame your solution as an enabler of EnterpriseSG programme objectives: "
            "'Our platform helps you meet the digital capability requirements for EDG "
            "eligibility' or 'We have helped 14 Singapore companies use MRA to fund "
            "their ASEAN market entry research.'"
        ),
    },
    "key_buying_triggers": [
        {
            "trigger": "MAS regulatory update",
            "description": "Monetary Authority of Singapore issues new notice or consultation paper",
            "sectors": ["Fintech", "Banking", "Insurance", "Payment services"],
            "urgency": "High — typically 6–12 month compliance deadline",
            "gtm_response": "Send regulatory briefing + solution mapping within 48 hours of MAS announcement",
        },
        {
            "trigger": "MOM payroll/HR regulation change",
            "description": "Ministry of Manpower updates Employment Act, CPF rates, or SDL requirements",
            "sectors": ["All Singapore employers"],
            "urgency": "High — legal compliance requirement",
            "gtm_response": "Targeted campaign to all HR contacts: 'Are you compliant with the new [regulation]?'",
        },
        {
            "trigger": "PDPA enforcement action",
            "description": "PDPC issues fine or enforcement action against a Singapore company",
            "sectors": ["All businesses handling personal data"],
            "urgency": "Medium-High — risk aversion triggered by news",
            "gtm_response": "Case study: 'How [Company] avoided a PDPC audit with [Platform]'",
        },
        {
            "trigger": "Singapore Budget announcement",
            "description": "Annual Budget introduces new SME support programmes, grants, or incentives",
            "sectors": ["All SMEs"],
            "urgency": "Medium — typically 6–18 month window to access incentives",
            "gtm_response": "Budget impact analysis sent to ICP list within 24 hours of Budget announcement",
        },
        {
            "trigger": "Company funding round",
            "description": "Target company closes Series A, B, or growth round",
            "sectors": ["Startups, scale-ups"],
            "urgency": "High — new budget, rapid hiring, infrastructure investment needed",
            "gtm_response": "Outreach within 1 week of announcement: 'Congratulations on your raise — here is how we help Series B companies scale their GTM'",
        },
        {
            "trigger": "Key leadership hire",
            "description": "New CFO, CTO, COO, or VP Sales joins target company",
            "sectors": ["All"],
            "urgency": "Medium-High — new leader typically mandated to make change in first 90 days",
            "gtm_response": "Executive briefing outreach within 2 weeks of LinkedIn announcement",
        },
        {
            "trigger": "Growth milestone",
            "description": "Company hits headcount threshold (crosses 50 employees) or opens new office",
            "sectors": ["All"],
            "urgency": "Medium — growing pains create systems needs",
            "gtm_response": "LinkedIn job posting signals; outreach when they post 3+ roles simultaneously",
        },
    ],
    "common_objections": [
        {
            "objection": "We already use Excel / we handle it manually",
            "underlying_fear": "Change is risky; learning curve will hurt productivity",
            "response_framework": "PAS + STAR: quantify the cost of manual, show a comparable company that made the switch",
            "sg_angle": "Calculate their cost: 'At SGD 30/hour × 12 hours/week × 52 weeks = SGD 18,720/year in manual reconciliation'",
        },
        {
            "objection": "We do not have budget right now",
            "underlying_fear": "We cannot afford it / we do not prioritise this",
            "response_framework": "BANT budget discovery + PSG grant education",
            "sg_angle": "Introduce PSG co-funding: 'With PSG, your net cost is SGD X instead of SGD Y. Does that change the conversation?'",
        },
        {
            "objection": "We tried something similar before and it did not work",
            "underlying_fear": "Past failure makes them risk-averse",
            "response_framework": "Just Listen technique: acknowledge the pain first, then differentiate",
            "sg_angle": "Ask about the previous failure specifically. Address the exact failure mode. Offer a low-risk pilot.",
        },
        {
            "objection": "We need to discuss with our team / boss first",
            "underlying_fear": "No decision authority; or not sold yet themselves",
            "response_framework": "Champion-building: give them materials to sell internally",
            "sg_angle": "Offer to facilitate a group demo. Provide an internal business case template with SGD ROI calculation.",
        },
        {
            "objection": "Can you give us a discount?",
            "underlying_fear": "Testing your confidence; or genuinely constrained on price",
            "response_framework": "Challenger take-control: 'I can discuss flexibility, but help me understand — is price the primary factor, or is it the value we have demonstrated so far?'",
            "sg_angle": "Explore PSG grant first. If discount needed, trade for case study permission or extended commitment.",
        },
        {
            "objection": "We are too small for this / not ready yet",
            "underlying_fear": "Complexity, implementation burden, feels like overkill",
            "response_framework": "Right-size the solution. Show the simplest implementation path. Offer a 14-day free trial.",
            "sg_angle": "Show 'companies your size in Singapore' case study. Normalise adoption at their scale.",
        },
    ],
    "channel_effectiveness": {
        "LinkedIn": {
            "effectiveness": "High for B2B Singapore",
            "notes": "Singapore professionals are highly active on LinkedIn. Decision-makers post and engage. InMail has higher open rates than email in many segments.",
            "best_for": "Awareness, thought leadership, direct outreach to mid-senior roles",
        },
        "WhatsApp": {
            "effectiveness": "Very high for SME relationships (once relationship established)",
            "notes": "Singapore business communication culture heavily uses WhatsApp. Not appropriate for cold outreach, but essential for warm relationship management.",
            "best_for": "Existing relationships, follow-up after meeting, account management",
        },
        "Email": {
            "effectiveness": "Medium — lower open rates than LinkedIn for cold outreach",
            "notes": "Best for nurture sequences, content delivery, and formal proposals. Cold email works better with strong personalisation.",
            "best_for": "Nurture sequences, formal communications, content delivery",
        },
        "Events": {
            "effectiveness": "Very high ROI per contact in Singapore",
            "notes": "Singapore is a conference hub. Industry events (Singapore FinTech Festival, F&B Asia, PropTech Summit SG) concentrate decision-makers. Dinner sponsorships and speaking slots outperform booth presence.",
            "best_for": "Enterprise pipeline, relationship building, brand authority",
        },
        "Referrals": {
            "effectiveness": "Highest conversion rate of any channel",
            "notes": "Singapore's small business community means referrals carry enormous weight. A warm introduction from a mutual contact is worth 10x cold outreach.",
            "best_for": "Enterprise deals, community-led growth",
        },
        "Content_SEO": {
            "effectiveness": "Medium-long term — significant compounding effect",
            "notes": "Singapore English-language search intent is significant. High-value keyword content targeting Singapore-specific problems (CPF calculator, MOM compliance) drives qualified inbound.",
            "best_for": "Organic pipeline, brand authority, inbound MQL generation",
        },
    },
}

# ---------------------------------------------------------------------------
# Campaign Planning Framework
# ---------------------------------------------------------------------------

CAMPAIGN_BRIEF_TEMPLATE: dict[str, dict] = {
    "objective": {
        "description": "What business outcome does this campaign drive?",
        "examples": ["Generate 50 SQLs in Q2", "Drive 200 trial signups from fintech segment", "Reactivate 30 churned accounts"],
        "metrics": ["MQL target", "SQL target", "pipeline value target", "conversion rate target"],
    },
    "target_segment": {
        "description": "Precisely defined ICP segment for this campaign",
        "required_fields": ["Industry vertical", "Company size range", "Geography", "Buying trigger", "Persona (title/role)"],
    },
    "insight_hook": {
        "description": "The Challenger-style insight or Unexpected hook that opens the campaign",
        "examples": [
            "Most Singapore logistics companies do not know their real cost-per-delivery",
            "The upcoming MAS Notice 702 revision will require X change by December",
        ],
    },
    "value_proposition": {
        "description": "The single, specific, provable claim of value for this segment",
        "template": "[Product] helps [target segment] [achieve outcome] by [mechanism], unlike [alternative]",
    },
    "messaging_framework": {
        "description": "Which messaging framework to use for this campaign",
        "options": list(MESSAGING_FRAMEWORKS.keys()),
        "selection_logic": {
            "cold_outreach": "PAS",
            "nurture_sequence": "AIDA or BAB",
            "case_study": "STAR",
            "landing_page": "AIDA or BAB",
            "product_demo": "FAB",
        },
    },
    "cialdini_principles_to_activate": {
        "description": "Which 1–2 Cialdini principles will be primary in this campaign",
        "options": list(CIALDINI_PRINCIPLES.keys()),
        "guidance": "Choose based on stage: Reciprocity for awareness, Social Proof for consideration, Scarcity for conversion",
    },
    "channels": {
        "primary": "The highest-leverage channel for this segment",
        "secondary": "Supporting channel for multi-touch",
        "sequence_length": "Number of touches before disqualifying",
    },
    "content_pieces": {
        "description": "List of assets needed to execute the campaign",
        "typical_set": [
            "Cold outreach email sequence (3–5 touches)",
            "LinkedIn message sequence (2–3 touches)",
            "One-page value proposition asset",
            "Case study (STAR format)",
            "Demo deck / discovery call guide",
        ],
    },
    "success_metrics": {
        "leading_indicators": ["Email open rate", "Reply rate", "LinkedIn response rate", "Demo bookings"],
        "lagging_indicators": ["SQLs generated", "Pipeline value", "Deals closed", "Revenue"],
    },
}

# ---------------------------------------------------------------------------
# Objection Handling — Just Listen (Goulston) + Cialdini Synthesis
# ---------------------------------------------------------------------------

OBJECTION_HANDLING_FRAMEWORK: dict[str, dict] = {
    "philosophy": (
        "Mark Goulston's core insight: before you can move someone, you must first make them "
        "feel understood. The most common sales mistake is trying to overcome an objection "
        "before the prospect feels heard. Acknowledge → Clarify → Reframe → Evidence."
    ),
    "sequence": {
        "step_1_listen": {
            "description": "Let the objection land. Do not interrupt, do not rush to counter.",
            "technique": "Pause 2–3 seconds after the objection. Then: 'I appreciate you telling me that.'",
        },
        "step_2_acknowledge": {
            "description": "Show you genuinely understand their concern — not just their words but the underlying fear.",
            "technique": "Empathy statement: 'It sounds like your concern is really about [underlying fear], not just [surface objection]. Is that right?'",
        },
        "step_3_clarify": {
            "description": "Ask a question to deepen understanding and let them fully articulate the concern.",
            "technique": "'Help me understand — what happened that makes [objection] your primary concern?'",
        },
        "step_4_reframe": {
            "description": "Gently shift the frame without dismissing their concern.",
            "technique": "Use the Challenger approach: introduce new information that changes the context of the objection.",
        },
        "step_5_evidence": {
            "description": "Provide specific, credible evidence that addresses the reframed concern.",
            "technique": "Case study (STAR), specific metric, or third-party validation. Never generic claims.",
        },
        "step_6_next_step": {
            "description": "Move the conversation forward with a low-friction next step.",
            "technique": "'Based on what you just told me, would it make sense to...'",
        },
    },
    "power_phrases": [
        "I appreciate you raising that — it comes up a lot with companies in your situation.",
        "What would need to be true for this to make sense for you?",
        "Help me understand the story behind that concern.",
        "If we could address that concern completely, would there be any other reason not to move forward?",
        "What would you need to see to feel confident about this decision?",
        "I hear you — what would a small, low-risk first step look like to you?",
    ],
}

# ---------------------------------------------------------------------------
# RACE Framework (Digital Marketing — Kingsnorth)
# ---------------------------------------------------------------------------

RACE_FRAMEWORK: dict[str, dict] = {
    "description": (
        "Smart Insights RACE Framework for digital marketing planning. "
        "Provides a structured approach to planning, managing, and optimising "
        "digital marketing across the customer lifecycle."
    ),
    "stages": {
        "Reach": {
            "description": "Build awareness and visibility of your brand to the target audience",
            "tactics": [
                "SEO and content marketing",
                "Paid search (Google Ads)",
                "LinkedIn ads and sponsored content",
                "PR and media outreach",
                "Social media organic",
                "Influencer and partner marketing",
            ],
            "key_metrics": ["Impressions", "Reach", "Website traffic", "Brand search volume"],
            "sg_focus": "LinkedIn and local media (e27, Tech in Asia, Business Times) for B2B Singapore reach",
        },
        "Act": {
            "description": "Drive interactions and leads — move prospects from visitor to lead",
            "tactics": [
                "Landing page optimisation",
                "Lead magnets (calculators, assessments, templates)",
                "Webinars and live events",
                "Free trials and freemium onboarding",
                "Retargeting campaigns",
            ],
            "key_metrics": ["Website conversion rate", "Lead volume", "Cost per lead", "MQL count"],
            "sg_focus": "PSG grant calculator or eligibility checker as high-converting Singapore-specific lead magnet",
        },
        "Convert": {
            "description": "Turn leads into customers — the sales process",
            "tactics": [
                "Personalised outreach sequences",
                "Demo booking and delivery",
                "Proposal and contract negotiation",
                "Proof of Concept (POC) programmes",
                "Reference customer calls",
            ],
            "key_metrics": ["SQL-to-Close rate", "Sales cycle length", "ACV", "Win rate"],
            "sg_focus": "Champion-building for Singapore SME buying committees; PSG grant documentation support",
        },
        "Engage": {
            "description": "Retain, cross-sell, and grow existing customers — generate advocacy",
            "tactics": [
                "Customer success and onboarding",
                "In-product messaging and adoption campaigns",
                "QBRs (Quarterly Business Reviews)",
                "Customer community and events",
                "Referral and advocacy programmes",
                "Upsell/cross-sell sequences",
            ],
            "key_metrics": ["NPS", "Net Revenue Retention (NRR)", "Churn rate", "Expansion ARR"],
            "sg_focus": "Singapore reference customer development — local case studies command premium credibility",
        },
    },
}

# ---------------------------------------------------------------------------
# 4Ps Marketing Mix (Kotler)
# ---------------------------------------------------------------------------

MARKETING_MIX_4P: dict[str, dict] = {
    "description": (
        "The foundational marketing mix framework (McCarthy, developed by Kotler). "
        "For B2B SaaS, each P takes on specific digital-age characteristics. "
        "The 4Ps define what you sell, what you charge, where you sell it, and how you promote it."
    ),
    "Product": {
        "description": "What you are selling — features, quality, design, brand, warranty, packaging",
        "b2b_saas_dimensions": [
            "Core product (what it does)",
            "Integration ecosystem (what it connects to)",
            "Onboarding and training (how customers start)",
            "Support tiers (how you help them succeed)",
            "Product roadmap (what it will become)",
        ],
        "sg_sme_considerations": [
            "Must work out-of-the-box with minimal IT support",
            "Mobile-first for field operations",
            "Local compliance built-in (MOM, CPF, PDPA)",
            "Bilingual support where customer base is multicultural",
        ],
    },
    "Price": {
        "description": "What you charge — pricing model, discounting, payment terms, financing",
        "b2b_saas_models": {
            "per_seat": "Per user/month — scales with team size",
            "usage_based": "Per transaction/usage — aligns cost with value",
            "flat_fee": "Fixed monthly/annual — predictable for buyer and seller",
            "freemium": "Free tier + paid upgrade — PLG motion",
            "outcome_based": "Pay-for-results — highest alignment, hardest to price",
        },
        "sg_sme_considerations": [
            "Annual prepay with discount to improve cash flow",
            "PSG grant-aligned pricing tiers",
            "SGD pricing rather than USD to remove FX uncertainty",
            "Month-to-month option to reduce commitment anxiety",
        ],
    },
    "Place": {
        "description": "Where and how your product reaches the customer — distribution, channels",
        "b2b_saas_channels": [
            "Direct (website self-serve)",
            "Sales-assisted (demo → contract)",
            "Channel/reseller (IT resellers, system integrators)",
            "Marketplace (Salesforce AppExchange, AWS Marketplace)",
            "OEM (built into another product)",
        ],
        "sg_sme_considerations": [
            "PSG pre-approved vendor status (IMDA marketplace)",
            "Industry association endorsement as distribution",
            "WhatsApp as customer communication channel",
            "Local Singapore data residency requirements for some sectors",
        ],
    },
    "Promotion": {
        "description": "How you communicate to the target market — advertising, PR, events, content, sales",
        "b2b_saas_tactics": [
            "Content marketing (thought leadership, SEO)",
            "LinkedIn (organic and paid)",
            "Cold email and outreach sequences",
            "Events (hosting and speaking)",
            "PR and media",
            "Partner co-marketing",
            "Customer referral programme",
        ],
        "sg_sme_considerations": [
            "LinkedIn: primary B2B awareness channel",
            "WhatsApp: relationship channel",
            "Industry events: outsized ROI in small SG market",
            "Multilingual content: English primary, Chinese secondary for traditional SMEs",
        ],
    },
}

# ---------------------------------------------------------------------------
# Porter's 5 Forces (for competitor analysis)
# ---------------------------------------------------------------------------

PORTER_FIVE_FORCES: dict[str, dict] = {
    "description": (
        "Michael Porter's framework for analysing the competitive forces that shape "
        "industry profitability. Used by the Competitor Analyst agent to assess "
        "market attractiveness and competitive dynamics."
    ),
    "forces": {
        "competitive_rivalry": {
            "description": "Intensity of competition among existing players",
            "high_rivalry_indicators": [
                "Many competitors of similar size",
                "Slow industry growth",
                "High fixed costs",
                "Low differentiation",
                "High exit barriers",
            ],
            "sg_b2b_saas_assessment": "Assess competitor count, funding levels, pricing pressure, and feature parity",
        },
        "threat_of_new_entrants": {
            "description": "Ease with which new competitors can enter the market",
            "barriers_to_entry": [
                "Capital requirements",
                "Brand loyalty and switching costs",
                "Network effects",
                "Regulatory requirements (IMDA, MAS approval)",
                "Distribution control",
            ],
            "sg_b2b_saas_assessment": "PSG pre-approval and MAS licensing create meaningful moats in regulated verticals",
        },
        "threat_of_substitutes": {
            "description": "Alternative ways customers can meet the same need",
            "substitute_types": [
                "Direct substitutes (competing software)",
                "Manual alternatives (spreadsheets, manual process)",
                "Adjacent solutions (ERP modules)",
                "Build-vs-buy (internal development)",
            ],
            "sg_b2b_saas_assessment": "Manual process is always the primary substitute for SME SaaS",
        },
        "buyer_power": {
            "description": "Customers' ability to drive prices down or demand more value",
            "high_buyer_power_indicators": [
                "Few, large customers",
                "Low switching costs",
                "Undifferentiated product",
                "Buyers are price-sensitive",
            ],
            "sg_b2b_saas_assessment": "PSG grant reduces buyer price sensitivity; increases adoption but also increases buyer expectations",
        },
        "supplier_power": {
            "description": "Suppliers' ability to raise prices or reduce quality",
            "key_suppliers_in_saas": [
                "Cloud infrastructure (AWS, Azure, GCP)",
                "AI/LLM API providers (OpenAI, Anthropic)",
                "Payment processors",
                "Third-party data providers",
            ],
            "sg_b2b_saas_assessment": "LLM provider concentration is a meaningful risk for AI-native products",
        },
    },
}

# ---------------------------------------------------------------------------
# Convenience re-export — all framework names for discovery
# ---------------------------------------------------------------------------

ALL_FRAMEWORK_NAMES: list[str] = [
    "CIALDINI_PRINCIPLES",
    "MESSAGING_FRAMEWORKS",
    "OGILVY_PRINCIPLES",
    "MADE_TO_STICK_SUCCESS",
    "STP_FRAMEWORK",
    "GTM_FRAMEWORKS",
    "SALES_QUALIFICATION",
    "ICP_FRAMEWORK",
    "SINGAPORE_SME_CONTEXT",
    "CAMPAIGN_BRIEF_TEMPLATE",
    "OBJECTION_HANDLING_FRAMEWORK",
    "RACE_FRAMEWORK",
    "MARKETING_MIX_4P",
    "PORTER_FIVE_FORCES",
]
