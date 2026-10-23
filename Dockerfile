FROM python:3.12-slim

WORKDIR /app

# Install requirements first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend package
COPY backend/ .

# Copy the ai package (Token Factory client, quiz generation)
COPY ai/ ai/

# Run with a single worker — the login rate limiter is in-memory
# and would not be consistent across multiple workers.
EXPOSE 8000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
