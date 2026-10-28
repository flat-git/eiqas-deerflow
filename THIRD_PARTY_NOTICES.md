# Third-party notices

EIQAS source additions use MIT. This does not change the licenses of bundled libraries, model weights or the analysis image.

- **DeerFlow v2.1.0**: MIT; the original ByteDance notice is retained in [LICENSE](LICENSE). See [UPSTREAM.md](UPSTREAM.md) for the pinned commit.
- **Apache ECharts 6.1.0**: Apache-2.0. Offline exports embed the npm distribution. Its full [LICENSE](backend/packages/eiqas-research/eiqas_research/assets/ECHARTS-LICENSE) and [NOTICE](backend/packages/eiqas-research/eiqas_research/assets/ECHARTS-NOTICE) are retained and included in ZIP delivery. The asset hash is fixed in the adjacent manifest.
- **ZRender, d3 and tslib**: their full license/copyright files are retained alongside the ECharts asset and included in offline ZIPs.
- **Docling / Docling models**: their respective package/model licenses apply. Packages are locked in `docker/analysis/requirements.lock`; weights are downloaded into a separate runtime cache, not committed to Git.
- **Tesseract and Noto CJK fonts**: installed from Ubuntu's package repositories in the analysis image, with their package copyright/license files retained by the distribution.
- **AIO Sandbox 1.11.0**: the image is identified by its immutable manifest digest in `docker/analysis/Dockerfile`; upstream image and installed third-party license notices remain applicable.

Python and JavaScript transitive dependencies retain their original licenses. Runtime research records, originals, credentials and model caches are excluded from the source repository. Export ZIPs include only the originals explicitly used in that report, for the operator's local study; users must respect the source material's own redistribution terms.
