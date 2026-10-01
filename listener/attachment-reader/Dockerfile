# Pinned by digest: this image carries the OCR and NER models the privacy gate depends on, and a
# silent :latest bump could change what gets redacted.
FROM mcr.microsoft.com/presidio-image-redactor@sha256:e49fd47bfc38d834f0856063b9f00cfb3c19866e8d61b061849baf6275139612

USER root
COPY requirements.txt /reader/requirements.txt
RUN pip install --no-cache-dir -r /reader/requirements.txt
COPY reader.py /reader/reader.py
COPY tests /reader/tests
USER presidio

# The base image is used for what it carries (Tesseract 5, spaCy en_core_web_lg, Presidio's
# analyzer), not its redactor, whose word-to-box mapping missed a name spanning a line break.
ENV PYTHONPATH=/reader
WORKDIR /reader
EXPOSE 3000
# One worker: each loads spaCy en_core_web_lg (~800 MB). Threads share it; per-call state is not shared.
# --timeout here only restarts a worker that stops heartbeating; it does not bound a request in a
# thread worker. reader.py stops a long PDF itself after READ_BUDGET_SECONDS (150 s), inside the
# listener's 180 s client timeout.
ENTRYPOINT ["gunicorn", "-w", "1", "--threads", "2", "--timeout", "170", "-b", "0.0.0.0:3000", "reader:create_app()"]
