# SpontaneousAI

The system generates a personal and dynamic trip itinerary in real time using data from blogs, Google Maps ratings, and other databases.

| Service | Folder | Responsibility | Tech Stack |
|---------|--------|----------------|------------|
| Web | /web | Shows the UI to the user. | React |
| API | /api | Handles user accounts, forwards requests to Engine. | Node.js |
| Engine | /engine | "Thinks" about recommendations, manages DB Structure. | Python, FastAPI |
| Database | /database | Stores data and AI Vectors. | PostgreSQL |
| Shared | /shared-api | Ensures Web and Engine speak the same language. | OpenAPI |

## Database

The app uses an **external PostgreSQL** database. Configure credentials in `.env` (copy from `.env.example`).

### First-time setup: initialize schema

If your external DB is empty, run the init script to create `attractions` and `users` databases and tables:

```bash
PGPASSWORD=your_password psql -h 10.10.248.114 -U postgres -f database/init.sql
```

## Running locally (localhost)

To test without Docker:

1. Copy `.env.example` to `.env` and set `POSTGRES_HOST`, `POSTGRES_PASSWORD`, etc.
2. Set `ENGINE_HOST=localhost` in `.env` (for API to reach the engine).
3. Install dependencies and run:

```bash
# Option A: Single script (all services in background)
./run-local.sh

# Option B: Run each in a separate terminal for clearer logs
# Terminal 1 - Engine
cd engine && source .venv/bin/activate && export PYTHONPATH="$(pwd):$(pwd)/../shared/python" && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - API
cd api && npm run dev

# Terminal 3 - Web
cd web && npm run dev
```

- Engine: http://localhost:8000
- API: http://localhost:3000
- Web: http://localhost:5173
