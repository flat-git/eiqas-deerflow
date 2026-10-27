# EIQAS DeerFlow v0.1

## Goal and decisions

Independent public product on pinned DeerFlow v2.1.0. Single user, native model configuration, public-source research including Chinese/English OCR, real calculations, interactive reports and reproducible exports. Confirm a research plan once; ask again for material changes or unresolved evidence. No legacy EIQAS migration, drag/drop editor, shared-team deployment or public report hosting.

## Milestones

- [ ] M0 — repository, Project/Milestone/12 tasks, CI, runtime and real model/tool smoke.
- [ ] M1 — research records, plans, explicit confirmation and five-stage events.
- [ ] M2 — source acquisition, originals, PDF/OCR, datasets and correction.
- [ ] M3 — actual calculation, numerical validation, cancellation and partial results.
- [ ] M4 — workbench, interactive results/provenance, offline exports.
- [ ] M5 — real studies, OCR regression, reader trial and v0.1 release.

## Actual progress

2026-10-27: verified upstream commit; created the independent public repository, v0.1.0 Milestone, tasks #1–#12 and roadmap #13. Installed pinned backend dependencies; baseline tests are running. Docker is available. Frontend installation uses the pinned pnpm 10.26.2 because the host's pnpm 9 does not understand the lockfile configuration.

GitHub Projects needs the CLI's `project` scope. Model credentials are not present in the current environment. Neither fact blocks offline implementation, but their corresponding live checks remain pending.

## Evidence and acceptance

See [development notes](docs/eiqas-development.md) and the GitHub roadmap. Keep code completion, automated tests, real model calls, actual OCR and human trial separate. Close tasks only after their stated checks pass.
