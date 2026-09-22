FROM python:3.12-slim

WORKDIR /app

# Dependencies first so code edits do not invalidate the install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY static/ static/
COPY seed/ seed/

# Uploads, the SQLite file and the Chroma index all live here.
ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# A shell is needed to expand $PORT, which Render injects at runtime; exec then
# replaces it so uvicorn is PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
