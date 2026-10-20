FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt requirements-dev.txt ./
# Dev requirements are included so the tests can run in this image.
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Download the embedding model at build time so the first request isn't slow.
# Keep EMBEDDING_MODEL in sync with the value in .env.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

COPY pytest.ini .
COPY app ./app
COPY tests ./tests
COPY sample_docs ./sample_docs
COPY scripts ./scripts
COPY eval ./eval

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
