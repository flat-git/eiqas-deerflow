# EIQAS research extension

Owns business records, provenance, numerical validation and report delivery. Use the public extension registry for integration. Do not import Gateway application modules or change the Harness loop.

SQLite writes and file operations are synchronous domain methods: FastAPI sync endpoints and native sync tools run them in worker threads. Lifecycle hooks must offload them. Transactions own both a business update and its audit event. Human plan confirmation is exposed only as a web action, never an Agent tool. Confirmation binds the canonical plan hash and current research question.

Tests live in `backend/tests/test_eiqas_*.py`. Keep fixtures synthetic, deterministic and small. No secrets or real runtime databases in source control. Live acquisition, actual OCR and real-model acceptance remain separate from mocked CI.
