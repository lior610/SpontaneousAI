# SpontaneousAI

The system generates a personal and dynamic trip itinerary in real time using data from blogs, Google Maps ratings, and other databases.

| Service | Folder | Responsibility | Tech Stack |
|---------|--------|----------------|------------|
| Web | /web | Shows the UI to the user. | React |
| API | /api | Handles user accounts, forwards requests to Engine. | Node.js |
| Engine | /engine | "Thinks" about recommendations, manages DB Structure. | Python, FastAPI |
| Database | /database | Stores data and AI Vectors. | PostgreSQL |
| Shared | /shared-api | Ensures Web and Engine speak the same language. | OpenAPI |

- Engine: http://localhost:8000
- API: http://localhost:3000
- Web: http://localhost:5173
