# EIQAS development quickstart

This is an experimental candidate under implementation, not an accepted v0.1 release. The standard deployment is local, single-user Docker Compose. The EIQAS extension does not migrate legacy EIQAS research.

Requirements: Docker Desktop/Engine with the daemon running, Python 3.12+ for setup, and a DeerFlow-supported model with tool calling. Building the frontend in Docker does not require host Node. Development tooling uses Node 22, pnpm 10.26.2 and uv 0.11.1.

```sh
git clone https://github.com/flat-git/eiqas-deerflow.git
cd eiqas-deerflow
python3 scripts/eiqas_setup.py
```

Set your model ID, endpoint and API key in the ignored `.env`, and edit the native model entry in the ignored `config.yaml` if your provider needs a specific DeerFlow adapter. Never commit either file. Setup preserves existing configuration and credentials.

```sh
docker compose --env-file .env --env-file .eiqas/deploy.env -f compose.eiqas.yaml --profile build build
docker compose --env-file .env --env-file .eiqas/deploy.env -f compose.eiqas.yaml up -d --wait nginx frontend gateway
```

Open [the workbench](http://127.0.0.1:2026/research). Create the initial native local administrator if prompted. Create a question-led research, review the saved plan and confirm it once. The agent then downloads originals, prepares located data and executes calculations. Critical gaps, conflicting definitions or uncertain OCR values require review. Material changes to the question or method invalidate confirmation.

The five stages can be revisited. Execution state, answerable scope and gaps are separate. A report binds a checked run, frozen inputs and exact evidence. Use the independent reader for charts, data, sources and downloads; conversation edits save a new result. Parameter changes execute a new run.

## Local state and verification

- `.env`, `config.yaml`, `.eiqas/` and `.deer-flow/` are local and ignored. Back up them appropriately; they contain configuration, the native account and research files.
- Only nginx publishes a host port, bound to `127.0.0.1`. Keep the Gateway to one worker in this edition.
- `eiqas-ocr-cache` is a dedicated Docker volume. The analysis environment uses the locked CPU stack and Tesseract Chinese/English language packs. First OCR use obtains public layout/table weights.
- HTML embeds ECharts and works without external chart resources. ZIP contains explicitly referenced originals, extraction records, frozen data, scripts, logs, checksums and a replay command. Recalculation is a workbench operation, not an offline HTML RPC.

Real model, real OCR, browser, offline replay and reader trial acceptance are recorded separately in [the acceptance checklist](v0.1-acceptance.md). CI does not need model credentials. Use the public issues and Project to check remaining work.

```sh
# From backend/ in a clean checkout without operator config or credentials:
make test
make test-blocking-io
# From frontend/ with pinned pnpm:
pnpm check
pnpm test
pnpm exec playwright install chromium
pnpm exec playwright test --config eiqas-layout.playwright.config.ts
pnpm build
```

For synthetic actual-container checks, run `scripts/acceptance/ocr_case.py` in the analysis image and `scripts/acceptance/offline_delivery.py` with the backend environment. These synthetic fixtures do not replace real-source studies or a human reader trial.

Run full native offline suites in a clean checkout, as CI does. Do not globally set `DEER_FLOW_CONFIG_PATH` for that suite: subprocess fixtures create their own temporary configurations. Native operator plugins can also affect generic middleware-order assumptions. EIQAS domain tests use isolated temporary state.
