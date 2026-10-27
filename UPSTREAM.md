# Upstream provenance

- Repository: https://github.com/bytedance/deer-flow
- Release: v2.1.0 (2026-09-24)
- Commit: `345f08be00c8a9495079b732a39b46aa9af1584e`
- License: MIT; retain the root LICENSE and upstream notices.
- Product repository: https://github.com/flat-git/eiqas-deerflow

`upstream` is the official read/fetch remote. `origin` is this independent product. Only product branches and EIQAS release tags are pushed to origin. No old private EIQAS source history or research data is imported.

The public upstream Git history is preserved. Inherited automation is archived under `.github/upstream-workflows/` for reference; only EIQAS workflows are active. In particular, upstream publishing and scheduled automation do not execute in this product repository.

The upstream Harness remains a separate dependency layer. EIQAS business services use public extension contracts; changes to framework internals require a documented reason and regression tests.
