# App image for the scheduler and API. Matches the Mac's Python (3.12) exactly —
# the host (Ubuntu 18.04, Python 3.6) is far too old to run the code natively,
# which is why the app runs containerized. Build context is the repo root.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=America/Los_Angeles

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
