# Generative AI Sector Report Prompt System

This repository includes a modular prompt framework for generating sector-specific investment impact reports on how Generative AI is reshaping an industry and what the likely implications may be for investors, with an optional frontier-possibilities mode available through the local Streamlit launcher.

## Architecture

The system is intentionally simple and modular:

- `prompts/core_system_prompt.md`: The reusable master prompt that defines role, audience, tone, required report structure, analytical standards, and quality bar.
- `prompts/user_prompt_template.md`: The runtime instruction layer for the default investment implication reports.
- `prompts/user_prompt_frontier_possibilities.md`: The runtime instruction layer for frontier possibility reports.
- `prompts/sectors/*.md`: Sector adapters that inject industry-specific business models, value-chain context, likely Gen AI use cases, adoption bottlenecks, value-capture questions, and analytical traps.
- `scripts/render_prompt.py`: A dependency-light assembler that combines the core prompt, a chosen sector adapter, and the selected prompt template into one final prompt package.
- `scripts/validate_prompt_package.py`: A lightweight validator that checks assembled prompt packages before upload, including healthcare-specific checks for all four required analytical pillars.
- `scripts/generate_sector_report.py`: A report runner that uses the assembled prompt package to generate the final report.
- `scripts/send_sector_report.py`: A delivery helper that emails the generated HTML report using the shared Gmail workflow secrets.
- `.github/workflows/generate_sector_report.yml`: A manual GitHub Actions workflow that renders the prompt package, validates it, generates the report, emails it, and uploads both artifacts.
- `examples/`: Sample assembled prompt packages for inspection.

## How the Modular Prompt System Works

The design separates stable instruction logic from sector-specific context:

1. The core system prompt defines how the model should analyze and write.
2. The sector adapter forces the analysis to reflect the economics and operating realities of a particular industry.
3. The selected prompt template applies run-specific inputs such as audience, time horizon, any custom emphasis, and the required output structure for that mode.
4. `render_prompt.py` assembles those layers into one final prompt package for downstream model use.
5. `validate_prompt_package.py` blocks publication if required sections or healthcare pillars are missing.
6. `generate_sector_report.py` uses the assembled prompt package to create the final sector report.
7. `send_sector_report.py` emails the generated HTML report through the existing workflow email path.

This approach is easier to maintain than keeping one full prompt per sector. It preserves consistency across reports while still allowing sector specificity to improve over time.

## Why Sector Adapters Are Better Than Separate Full Prompts

Sector adapters are the right maintenance pattern here because they:

- keep report structure and quality standards consistent across sectors
- reduce prompt drift when the core analytical framework changes
- make sector updates smaller and easier to review
- support automation in GitHub Actions and other pipelines
- let the model stay grounded in industry detail without duplicating the full instruction stack

## Why Healthcare Is Deeper Than the Other Sectors

Healthcare is treated as a richer adapter because a shallow healthcare AI prompt will often collapse into documentation, coding, and call-center automation. Those are important, but they are not the whole investment story.

The healthcare adapter now forces the model to address four required analytical pillars:

1. Clinical and administrative workflow
2. Biotechnology and therapeutic development
3. Diagnostic intelligence at scale
4. Long-run in-home healthcare transformation through physical AI, robotics, ambient sensing, and agentic care systems

That structure is designed to keep the report investment-relevant across providers, payers, life sciences, diagnostics, healthcare IT, and longer-duration care delivery change.

## Run Locally

Render a prompt package with defaults:

```bash
python scripts/render_prompt.py healthcare
```

Render a prompt package with explicit inputs:

```bash
python scripts/render_prompt.py \
  --sector-name healthcare \
  --audience "portfolio managers and strategists" \
  --time-horizon "1-3 years and 3-7 years" \
  --style-notes "Write in crisp institutional prose" \
  --special-instructions "Spend real time on biotech productivity and diagnostic intelligence"
```

Render a second healthcare variant by changing only the run-time emphasis:

```bash
python scripts/render_prompt.py \
  --sector-name healthcare \
  --audience "portfolio managers and strategists" \
  --time-horizon "1-3 years and 3-7 years" \
  --style-notes "Write in crisp institutional prose" \
  --special-instructions "Lean harder into long-run in-home care transformation, robotics, ambient sensing, and caregiver augmentation."
```

Render a frontier possibilities prompt package:

```bash
python scripts/render_prompt.py \
  --sector-name healthcare \
  --industry-focus biotechnology \
  --report-mode frontier_possibilities
```

In the local Streamlit launcher, the Sector Report Launcher can choose between `Investment Implications` and `Frontier Possibilities`. The GitHub Actions workflow remains on the existing investment-oriented path.

In GitHub Actions, the sector dropdown now uses the standard GICS sectors. The workflow also includes an `industry_focus` dropdown with:

- `balanced` for a sector-level report spanning all industries in the selected sector
- the standard GICS industries for the covered sectors

The workflow validates the sector and industry pairing before prompt rendering. If you pick an industry that does not belong to the selected sector, the run fails fast with the allowed options for that sector.

Validate an assembled prompt package before using or publishing it:

```bash
python scripts/validate_prompt_package.py \
  --prompt-package out/final_prompt_healthcare.md \
  --sector-name healthcare
```

By default, the script writes the assembled prompt to:

```bash
out/final_prompt_<sector>.md
```

Examples:

- `out/final_prompt_healthcare.md`
- `out/final_prompt_semiconductors.md`

List available sectors:

```bash
python scripts/render_prompt.py --list-sectors
```

## Use the GitHub Workflow

1. Open the repository's **Actions** tab.
2. Select **Generate Sector Report**.
3. Click **Run workflow**.
4. Choose a sector and optionally adjust the audience, time horizon, style notes, and special instructions.
5. Choose `industry_focus` as `balanced` for a full sector report or select a standard GICS industry to tilt the report toward that industry while still preserving sector context.
6. The workflow validates both the sector and industry focus, then validates the assembled prompt package before generating the report. For healthcare, that validation still explicitly checks that the required analytical pillars are present.
7. The workflow generates the final HTML report, emails it through the configured Gmail workflow secrets, and uploads both the prompt package and report artifacts.
8. Download `assembled-sector-report-prompt` if you want to inspect the exact prompt package, and `sector-ai-impact-report-html` if you want the generated report artifact.

The workflow now runs end to end: it assembles the prompt, validates it, generates the report, emails the HTML output, and uploads both the prompt package and final report artifacts.

## Local macOS Launcher App

If you want Dock-friendly local apps instead of launching Streamlit from Terminal manually, build the macOS wrappers:

```bash
./scripts/build_ai_signal_center_app.sh
```

By default this creates:

```bash
~/Applications/AI Signal Command Center.app
~/Applications/Stop AI Signal Command Center.app
```

The start app wraps [launch_ai_signal_center.command](/Users/davidborberg/ai-research-pipeline/launch_ai_signal_center.command), so one click starts the local Streamlit server on port `8510` if needed and opens the browser. The stop app wraps [stop_ai_signal_center.command](/Users/davidborberg/ai-research-pipeline/stop_ai_signal_center.command). After building them once, drag either or both apps into the Dock.

The Streamlit app also persists the last-used workspace selection locally, so reopening the launcher returns you to the most recent workspace view.

If you want the app somewhere else, pass a target directory:

```bash
./scripts/build_ai_signal_center_app.sh ~/Desktop
```

## Add a New Sector

1. Create a new file in `prompts/sectors/` such as `aerospace_defense.md`.
2. Follow the existing adapter pattern:
   - sector definition
   - major business models
   - value chain notes
   - key revenue drivers
   - key cost centers
   - high-probability Gen AI use cases
   - adoption bottlenecks
   - likely beneficiaries
   - incumbents at risk
   - important KPIs and signals
   - analytical traps to avoid
3. Add the new sector to the workflow dropdown in `.github/workflows/generate_sector_report.yml`.
4. Run `python scripts/render_prompt.py --sector-name <new_sector>` to validate the adapter locally.

## Modify the Healthcare Logic Over Time

Healthcare is the most likely adapter to evolve because the sector spans multiple distinct investment subthemes. The best way to extend it is to preserve the current pillar structure and deepen specific sections as evidence improves.

Good future update paths include:

- refining the biotech section as AI-native discovery, platform biology, or trial design economics mature
- deepening the diagnostic intelligence section as evidence, reimbursement, and liability frameworks evolve
- expanding the in-home care section as physical AI, robotics, sensing, and payer support move from pilot activity toward scaled deployment
- adding more explicit subsector cues for payers, CROs, medtech, diagnostics, provider systems, and home health
- refining the healthcare preset library further if you want even narrower structured emphasis modes beyond the current dropdown choices

## Examples

The `examples/` directory contains assembled prompt packages for:

- `examples/healthcare_prompt_package.md`
- `examples/healthcare_prompt_package_homecare_variant.md`
- `examples/semiconductors_prompt_package.md`

These are useful for checking whether sector specificity is actually showing up in the final prompt package.

## Design Assumptions

- The report is meant to be investment-oriented and client-ready, not a technology demo.
- The output should separate realistic nearer-term impacts from longer-duration possibilities.
- The renderer should remain dependency-light and easy to use in CI.
- Healthcare needs stronger structural guidance than the other sectors to avoid defaulting to a generic administrative-automation narrative.
- The `special_instructions` field is the right place to emphasize one healthcare angle over another at run time without weakening the base healthcare adapter.
