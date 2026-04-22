# Generative AI Sector Report Prompt System

This repository now includes a modular prompt system for generating sector-specific investment impact reports on how Generative AI is reshaping an industry and what that may mean for investors.

## Architecture

- `prompts/core_system_prompt.md`: The master prompt that defines role, report objective, required structure, analytical standards, and quality bar.
- `prompts/user_prompt_template.md`: The run-time instruction layer with placeholders for sector, time horizon, audience, style notes, and any custom instructions.
- `prompts/sectors/*.md`: Concise sector adapters that inject industry economics, value-chain context, likely use cases, adoption bottlenecks, relevant KPIs, and analytical traps.
- `scripts/render_prompt.py`: A lightweight Python assembler that loads the core prompt, selected sector adapter, and user template into one prompt package.
- `.github/workflows/generate_sector_report.yml`: A manual GitHub Actions workflow that renders the assembled prompt and uploads it as an artifact for downstream report generation.

## How the Modular System Works

The system separates stable report behavior from sector-specific context:

1. The core system prompt defines how the model should think and write.
2. The sector adapter adds the economics and operating realities of a given industry.
3. The user prompt template injects run-specific parameters such as time horizon or audience.
4. `render_prompt.py` combines all three into a single assembled prompt package ready for model invocation.

This structure keeps the prompt system maintainable. You can improve sector specificity without rewriting the full prompt every time, and you can adjust the base reporting standard once in the core prompt instead of editing multiple independent prompt copies.

## Why Sector Adapters Instead of Fully Separate Prompts

Sector adapters are a better maintenance pattern than fully separate prompts because they:

- preserve a consistent report structure and quality standard across sectors
- reduce drift when the core analytical framework changes
- make sector updates smaller and easier to review
- improve reuse in automation workflows such as GitHub Actions
- keep the model grounded in industry specifics without duplicating the entire instruction stack

## Run Locally

Render a prompt package to stdout:

```bash
python scripts/render_prompt.py software
```

Render to a file with custom inputs:

```bash
python scripts/render_prompt.py healthcare \
  --audience "portfolio managers and strategists" \
  --time-horizon "12-24 months and 5+ years" \
  --style-notes "Write with concise, institutional tone" \
  --special-instructions "Emphasize reimbursement and administrative cost takeout" \
  --output artifacts/assembled_prompt.md
```

List supported sectors:

```bash
python scripts/render_prompt.py software --list-sectors
```

## Use the GitHub Workflow

1. Open the repository's Actions tab.
2. Select `Generate Sector Report Prompt`.
3. Click `Run workflow`.
4. Choose a sector and optionally adjust the audience, time horizon, style notes, or special instructions.
5. Download the uploaded `assembled-sector-report-prompt` artifact.

The workflow currently assembles and stores the prompt package only. A commented placeholder shows where to add a future model invocation step once you choose an inference provider.

## Add a New Sector

1. Create a new file in `prompts/sectors/` named after the sector, for example `aerospace_defense.md`.
2. Follow the same compact adapter pattern used by the existing sectors:
   - sector definition
   - main business models
   - value chain notes
   - key revenue drivers
   - key cost centers
   - high-probability Gen AI use cases
   - adoption bottlenecks
   - likely beneficiaries
   - incumbents at risk
   - important KPIs or signals investors should watch
   - sector-specific analytical traps to avoid
3. Add the new sector name to the `workflow_dispatch` options in `.github/workflows/generate_sector_report.yml`.
4. Test locally with `python scripts/render_prompt.py <new_sector_name>`.

## Design Assumptions

- The report is meant to be investment-oriented and client-ready, not a technical AI explainer.
- The output should stay balanced and explicit about uncertainty rather than defaulting to optimistic AI narratives.
- The prompt assembler is intentionally dependency-free so it can run easily in local environments and CI.
