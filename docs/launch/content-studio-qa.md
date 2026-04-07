# Content Studio — QA Gate (v1 Promotion Protocol)

**Status**: Hidden by default in production builds (`FEATURES.contentBeta = INTERNAL`).
**To promote to Beta**: pass this gate.

This document defines the protocol for deciding whether Content Studio is reliable enough to expose as a Beta surface in v1. It is not adequacy testing — it is **differentiation testing**.

The default outcome of this gate is **stay hidden**. Content Studio only graduates if it demonstrates that Hi Meet AI's output is **materially better than what a customer could get from a 2-minute prompt to ChatGPT or Claude**, across multiple verticals, with brand and workflow coherence.

If you are reading this and you cannot honestly say "yes, the output earned this," the gate failed. There is no partial credit.

---

## Gate philosophy

Three principles:

1. **Adequacy is not enough.** "It's not bad" does not promote Content Studio. The bar is "materially better than the alternative the customer would otherwise use."
2. **The alternative is real, not hypothetical.** We test against actual ChatGPT/Claude prompts that a customer could write themselves, with the same inputs.
3. **Differentiation must hold across verticals.** A feature that works for fintech but not for marketing comms is a feature that works for one customer segment, not the product. Three verticals, not one.

If Content Studio cannot pass differentiation testing, hiding it is the right call. Generic AI content damages the "Hi Meet AI is different from ChatGPT" positioning more than missing the feature does.

---

## Gate setup

### Required test data

Three test companies, one per vertical:

| Vertical | Test company profile |
|---|---|
| **fintech** | A Singapore-based B2B payments SaaS with PSG eligibility, 30 employees, ~SGD 5M ARR |
| **marketing_comms** | A Singapore-based marketing agency with SME clients, 20 employees, project-based revenue |
| **professional_services** | A Singapore-based management consulting firm, 15 employees, retainer model |

Each test company must have:
- A completed analysis (full 6-agent run, all PDCA phases complete)
- Confidence ≥ 0.6 across analysis
- ≥ 3 generated leads with fit scores
- ≥ 2 competitors identified
- ≥ 2 market insights / signals populated

### Required outputs (per vertical)

For each vertical, generate:
1. **LinkedIn post — thought_leadership / professional**
2. **LinkedIn post — product_value / conversational**
3. **Email template — cold_intro**

Total: **9 outputs** across 3 verticals.

### Required comparison data (per output)

For each of the 9 outputs, the reviewer must also produce:
- **A control output** from a 2-minute prompt to ChatGPT or Claude. The prompt may include the company name, vertical, target audience, and a one-sentence positioning. Reviewer chooses which generic LLM to use; whichever is most likely to be the customer's alternative.

Total: **9 Hi Meet AI outputs + 9 control outputs = 18 artifacts.**

---

## The 7 evaluation criteria

For each Hi Meet AI output, evaluate against these 7 criteria. **All 7 must pass for the output to count as a pass.**

### 1. Specificity
The output references the test company's actual name, product, value prop, or positioning details from the analysis.
- **Pass**: contains the company name AND at least one product/positioning detail
- **Fail**: generic — could apply to any company in the vertical

### 2. Market grounding
The output references real insights from the analysis (named competitors, specific market trends, financial details, regulatory context).
- **Pass**: at least one specific reference to analysis data (e.g., "Competitor X recently raised SGD 10M" or "PSG grant eligibility")
- **Fail**: no reference to analysis data; reads like generic industry boilerplate

### 3. Ready-to-use
The output is publishable as-is or with minor edits. No placeholder text, no `[insert]`, no incomplete sentences.
- **Pass**: a real-world user would copy-paste and send/post within 5 minutes of editing
- **Fail**: requires substantive rewriting; contains template artifacts

### 4. Tone fidelity
The selected tone is audibly present, not just label-matched.
- **Pass**: a blind reader would correctly identify "professional" vs "conversational" vs "bold" from the output alone
- **Fail**: tone is uniform regardless of selector

### 5. Differentiation (NEW — strengthened criterion)
The Hi Meet AI output is **materially better** than the control output from ChatGPT/Claude given the same inputs.
- **Pass**: a side-by-side blind read would have the reviewer prefer the Hi Meet AI version. Reviewer answers "Yes, this is meaningfully better" without hedging.
- **Fail**: outputs are roughly equivalent OR the control is preferred. Even a tie counts as a fail — Hi Meet AI must clearly win.
- **Anti-pattern**: "Hi Meet AI mentioned the company name and the control didn't." Specificity alone is not differentiation. The Hi Meet AI version must be qualitatively better in insight, hook, structure, or relevance.

### 6. Brand fidelity (NEW — strengthened criterion)
The output reflects Hi Meet AI's positioning: planning posture, briefing-room voice, evidence-based, Singapore-aware where relevant.
- **Pass**: the output reads like it came from a strategic GTM advisor, not a generic SDR
- **Fail**: the output reads as generic outbound sales / growth hacker / cold-spam tone — even if it's technically well-written

### 7. Vertical coherence (NEW — strengthened criterion)
Comparing the same theme across all 3 verticals, the outputs show vertical-specific adjustment, not template-with-name-swap.
- **Pass**: the fintech version, marketing comms version, and professional services version each contain vertical-specific language, references, or angles. The reader can tell which vertical each was written for without seeing the company name.
- **Fail**: the three outputs are structurally identical with the company name swapped. No vertical-specific reasoning.
- **Note**: Criterion 7 is evaluated across all 3 outputs of the same theme, not per output. So criteria 1–6 = per-output (passes 9 evaluations); criterion 7 = per-theme (passes 3 evaluations: one for each LinkedIn theme + email template).

---

## Sign-off rule

| Total evaluations | Pass requirement |
|---|---|
| Criteria 1–6 (per output): 9 outputs × 6 criteria = **54 evaluations** | All 54 pass |
| Criterion 7 (per theme): 3 themes (LI thought, LI product, email cold) | All 3 pass |
| **Total: 57 pass-fail decisions** | **57 / 57** |

**Anything less than 57/57 = stay Hidden.**

No partial credit. No "we'll fix it next week." No "the differentiation criterion is subjective so we'll average." If the gate fails, Content Studio remains Hidden in v1 and is reconsidered in v1.1 after improvement work.

### Reviewer requirements

- **Two independent reviewers**, one product lead and one customer-facing lead (sales or CS)
- Reviewers evaluate independently and then meet to reconcile differences
- If reviewers disagree on any criterion, the output is treated as a fail until both agree it's a pass
- Reviewers must record their evaluations with timestamp + initials in `docs/launch/content-studio-qa-results.md`

### Recording the result

Pass:
1. Create `docs/launch/content-studio-qa-results.md` with the 57-row evaluation table
2. Both reviewers' initials and date
3. Side-by-side comparison snapshots (paste the 18 artifacts inline)
4. Flip `FEATURES.contentBeta` default from `INTERNAL` to `true` in a single commit
5. Add Beta disclaimer banner to `ContentPage.tsx`
6. Add nav item to SidebarNav
7. Update `launch-package.md` to move Content Studio from Hidden to Beta
8. Update `feature-flags.md`

Fail:
1. Create `docs/launch/content-studio-qa-results.md` with the failed evaluations and reviewer notes
2. `FEATURES.contentBeta` remains `INTERNAL` (no code change)
3. Update `launch-package.md` with the failure date and the criterion(s) that failed
4. File improvement work as a post-launch backlog item, not a v1 reopener

---

## Post-promotion monitoring

If the gate passes and Content Studio is promoted to Beta:

**72-hour rollback window**: monitor support channel for 72 hours after launch. Any of:
- ≥ 2 customer complaints about output quality
- A specific failure mode (always blank, always generic, always wrong)
- Performance issues (generation > 30s, frequent errors)

triggers immediate demotion: flip `FEATURES.contentBeta` back to `INTERNAL`, redeploy, document in cycle red-team.

**No grace period**. The whole point of this strict gate is that we ship Content Studio only when it earns the slot. If launch reality shows it doesn't, we revert without ego.

---

## Why this gate exists

The cost of shipping mediocre AI content is asymmetric:
- **Best case**: a few customers use it and find it useful
- **Worst case**: a customer's first impression is "Hi Meet AI's content is just ChatGPT in a wrapper" — a positioning collapse that's expensive to reverse

A feature that has been hidden is a feature that hasn't damaged anything. A feature that has been launched and disappointed is a feature whose damage compounds with every customer who tried it. The asymmetry justifies the conservative gate.

This is the same reason banks don't ship credit decisions through prototypes. Some categories of "almost good enough" are not good enough.
