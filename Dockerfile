FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# system deps needed for some packages (psycopg build, numpy wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev build-essential git \
    && rm -rf /var/lib/apt/lists/*

# install Python dependencies from requirements.txt (keeps build cache small)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# drop to non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
