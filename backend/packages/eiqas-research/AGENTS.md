# EIQAS research extension

Owns business records, provenance, numerical validation and report delivery. Use the public extension registry for integration. Do not import Gateway application modules or change the Harness loop.

SQLite writes and file operations are synchronous domain methods: FastAPI sync endpoints and native sync tools run them in worker threads. Lifecycle hooks must offload them. Transactions own both a business update and its audit event. Human plan confirmation is exposed only as a web action, never an Agent tool. Confirmation binds the canonical plan hash and current research question.

Tests live in `backend/tests/test_eiqas_*.py`. Keep fixtures synthetic, deterministic and small. No secrets or real runtime databases in source control. Live acquisition, actual OCR and real-model acceptance remain separate from mocked CI.

`evidence.py` owns scoped originals, located extraction, human corrections and frozen datasets. `analysis.py` owns actual sandbox run receipts and terminal cancellation fences. `reports.py` resolves numeric cells and citations; `exporter.py` uses the same snapshot for all formats and packages only an explicit, checked file list. Native Agent tools must never expose plan confirmation or human correction.

Frontend lives under `/research`; keep one native stream per active research and scoped query keys. Offline exports embed the checked ECharts asset, whose version/hash/license manifest is maintained by `scripts/sync_eiqas_assets.py`. Re-run that script when the chart package or analysis dependency lock changes. Actual OCR acceptance is `scripts/acceptance/ocr_case.py` inside the pinned analysis image, separate from CI mocks.
