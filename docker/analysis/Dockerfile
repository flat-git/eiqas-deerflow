# Fixed multi-architecture AIO 1.11.0 manifest; do not replace its server Python.
FROM enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.11.0@sha256:6328d7fd2f0ff0b4c147c3d05b3df1ce331f4a482eb6e550ecd64ed1fcf906e7
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-eng \
    fonts-noto-cjk libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*
RUN /opt/python3.12/bin/python -m venv /opt/eiqas-venv
COPY docker/analysis/requirements.lock /opt/eiqas/requirements.lock
RUN /opt/eiqas-venv/bin/python -m pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu --require-hashes -r /opt/eiqas/requirements.lock
COPY backend/packages/eiqas-research/eiqas_research/worker.py /opt/eiqas/worker.py
COPY --chmod=755 backend/packages/eiqas-research/eiqas_research/ocr_cli.py /opt/eiqas/tesseract-cli
ENV HF_HOME=/opt/eiqas-cache/huggingface
RUN mkdir -p /opt/eiqas-cache && \
    /opt/eiqas-venv/bin/python -m pip freeze > /opt/eiqas/python-packages.txt && \
    dpkg-query -W > /opt/eiqas/system-packages.txt
