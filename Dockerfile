FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirments.txt ./
RUN pip install --no-cache-dir -r requirments.txt

COPY src ./src

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/data \
    && chown bot:bot /app/data

USER bot

CMD ["python", "-m", "src.main"]