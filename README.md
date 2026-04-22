# Generative AI Sector Report Prompt System

This repository now includes a modular prompt system for generating sector-specific investment impact reports on how Generative AI is reshaping an industry and what that may mean for investors.

## Architecture

- `prompts/core_system_prompt.md`: The master prompt that defines role, report objective, required structure, analytical standards, and quality bar.
- `prompts/user_prompt_template.md`: The run-time instruction layer with placeholders for sector, time horizon, audience, style notes, and any custom instructions.
- `prompts/sectors/*.md`: Concise sector adapters that inject industry economics, value-chain context, likely use cases, adoption bottlenecks, relevant KPIs, and analytical traps.
- `scripts/render_prompt.py`: A lightweight Python assembler that loads the core prompt, selected sector adapter, and user template into one prompt package.
- `scripts/generate_sector_report.py`: A lightweight report runner that reads the assembled prompt package, calls the model, and writes the finished report in markdown or HTML.
- `scripts/send_sector_report.py`: A small email delivery helper that sends the generated sector report through the same Gmail path used by the daily, weekly, and monthly workflows.
- `.github/workflows/generate_sector_report.yml`: A manual GitHub Actions workflow that renders the assembled prompt, generates the HTML report, emails it, and uploads the artifacts.

## How the Modular System Works

The system separates stable report behavior from sector-specific context:

1. The core system prompt defines how the model should think and write.
2. The sector adapter adds the economics and operating realities of a given industry.
3. The user prompt template injects run-specific parameters such as time horizon or audience.
4. `render_prompt.py` combines all three into a single assembled prompt package.
5. `generate_sector_report.py` uses that assembled package to generate the final report.
6. `send_sector_report.py` emails the finished HTML output through the existing shared SMTP configuration.

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

Generate the final report from the assembled prompt package:

```bash
OPENAI_API_KEY=your_key_here python scripts/generate_sector_report.py \
  --prompt-package artifacts/assembled_prompt.md \
  --model gpt-5.4 \
  --output-format html \
  --output artifacts/sector_report.html
```

Email the generated HTML report with the shared Gmail sender and recipient configuration:

```bash
EMAIL_USER=you@example.com \
EMAIL_PASSWORD=app_password \
EMAIL_TO=recipient@example.com \
python scripts/send_sector_report.py \
  --sector software \
  --report-path artifacts/sector_report.html
```

List supported sectors:

```bash
python scripts/render_prompt.py software --list-sectors
```

## Use the GitHub Workflow

1. Open the repository's Actions tab.
2. Select `Generate Sector AI Impact Report`.
3. Click `Run workflow`.
4. Choose a sector and optionally adjust the audience, time horizon, style notes, special instructions, or model.
5. The workflow emails the HTML report to the same configured Gmail recipient used by the daily, weekly, and monthly pipelines.
6. Download the uploaded `sector-ai-impact-report-html` artifact for the finished report.
7. If needed, also download `assembled-sector-report-prompt` to inspect the exact prompt package used for the run.

The workflow expects `OPENAI_API_KEY`, `EMAIL_USER`, `EMAIL_PASSWORD`, and `EMAIL_TO` repository secrets. It installs Python dependencies, renders the prompt package, generates the HTML report, emails it through the shared Gmail delivery path, adds a preview to the run summary, and uploads both the prompt package and the final report.

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
- Report generation currently uses the OpenAI Python client, trying the Responses API first and falling back to Chat Completions for compatibility with the repo's existing usage pattern.
- Sector report email delivery reuses the same SMTP-based Gmail path and destination-secret pattern as the existing daily, weekly, and monthly workflows.
