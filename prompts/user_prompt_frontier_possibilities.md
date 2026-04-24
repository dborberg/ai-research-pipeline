Use the core system prompt together with the selected sector adapter to write a complete sector or industry report focused on credible frontier possibilities.

## Report Inputs

- Sector: {{sector_display_name}}
- Industry focus: {{industry_name}}
- Audience: {{audience}}
- Time horizon: {{time_horizon}}
- Style notes: {{style_notes}}
- Special instructions: {{special_instructions}}

## Instructions

- Produce a 900-1,200 word report.
- Use exactly this title: Generative AI and What May Become Possible in {{industry_name}} within {{sector_display_name}}
- Use exactly these section headings:
  1. Executive Summary
  2. What Changes Become Possible
  3. Real but Ambitious Frontier Scenarios
  4. Constraints and Gating Factors
  5. Signals to Watch
  6. Bottom Line
- Write in an analytical, imaginative but credible, grounded voice.
- Do not use markdown tables.
- Use the core system prompt as the governing instruction layer.
- Use the selected sector adapter as the sector-specific context and analytical specificity layer.
- Reuse the existing sector and industry context exactly as supplied. If the selected industry focus is a balanced sector view, keep the report balanced across the sector's major industries rather than collapsing into one niche.
- Propose ambitious but credible ideas rather than generic futurism.
- Distinguish clearly between near-term plausible, medium-term transformative, and longer-run frontier scenarios.
- For each major scenario, explain what would need to be true for it to happen.
- Discuss gating factors such as regulation, trust, economics, data quality, workflow integration, liability, labor acceptance, customer behavior, and physical constraints where relevant.
- Avoid generic futurism, science-fiction language, hype, or claims that are detached from sector economics and operating realities.
- Use the stated time horizon to separate nearer-term possibilities from longer-duration frontier outcomes.
- Apply the style notes only if they do not weaken the core prompt's standards for specificity, balance, uncertainty, and investment relevance.
- Apply the special instructions only if they do not conflict with the core prompt or the sector adapter.
- If the sector adapter identifies required analytical pillars, treat them as mandatory parts of the analysis rather than optional examples.
- If the selected sector is healthcare, preserve emphasis on therapeutic development and biotech, diagnostics enhanced by broad evidence and large-scale case intelligence, in-home care transformation through physical AI, robotics, ambient sensing, and agentic care systems, augmentation versus replacement, and practical hurdles including trust, liability, reimbursement, regulation, validation, safety, and hardware economics.
- Aim for the lower half of the allowed length range if needed to ensure the report is fully completed.
- Prefer completeness over extra detail if there is any risk of truncation.

## Output Reminder

- Write only the final report.
- Do not describe the prompt package.
- Do not add preambles, caveats, or methodology notes outside the requested report structure.
- Do not end with unfinished bullets, unfinished sentences, unfinished scenario descriptions, or an incomplete Bottom Line.