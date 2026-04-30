# Containerization

Build the application image and run with Docker Compose (recommended for local development):

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
docker compose build --progress=plain
docker compose up
```

Notes:
- The `web` service exposes port `8000` (FastAPI/uvicorn).
- `docker-compose.yml` includes a `db` (Postgres) and `redis` service for convenience.
- Copy or adapt values from `.env.example` into a `.env` file before starting.

To run the app image directly:

```powershell
docker build -t credit-ai-platform:local .
docker run --rm -p 8000:8000 --env-file .env credit-ai-platform:local
```

If you don't need Postgres/Redis locally, remove `depends_on`/services from `docker-compose.yml`.

Running both API and UI with compose

The provided `docker-compose.yml` runs the API (`web` on port `8000`), Postgres (`db`), Redis (`redis`), and the operator UI (`ui` on port `8501`). Start both with:

```powershell
cd C:\Users\rojab\MyData\credit-ai-platform
docker compose build --progress=plain
docker compose up
```

Open the UI at http://localhost:8501 and the API at http://localhost:8000.
