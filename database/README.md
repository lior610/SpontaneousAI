# Database setup

The API stores **users** and **trips** in a separate PostgreSQL database named **`users`**, not in the default `postgres` database.

## One-time setup

1. Start PostgreSQL (e.g. `brew services start postgresql` on macOS).
2. Run the init script (as a superuser or the user that owns the DB):
   ```bash
   psql -f init.sql
   ```
   Or from `psql`: `\i init.sql` (after connecting to any DB, e.g. `postgres`).

This creates:

- Database **`attractions`** (for vectors/attractions; optional for basic app).
- Database **`users`** with:
  - **`users`** table (accounts + preferences)
  - **`trips`** table (trips per user)

## Viewing data

Connect to the **`users`** database so you see the right tables:

```bash
psql -d users
```

Or from inside `psql`:

```text
\c users
\dt
SELECT * FROM users;
SELECT * FROM trips;
```

If you stay connected to the default **`postgres`** database, you will **not** see the `users` or `trips` tables there; they exist only in the **`users`** database.

## Migrations (existing databases)

If you already have the `users` database and tables, add new columns without recreating everything:

```bash
# Wizard preference breakdown (categories + percentages)
psql -d users -f database/migrations/001_add_preference_breakdown.sql

# Wizard constraints: max walking distance (km) and preferred transport
psql -d users -f database/migrations/002_add_max_walking_distance_and_preferred_transportation.sql

# Remove legacy fields (current_city, desired_vibe, desired_indoor, avoid_category_1/2/3)
psql -d users -f database/migrations/003_remove_legacy_trip_fields.sql

# Move with_kids from users to trips
psql -d users -f database/migrations/004_move_with_kids_to_trips.sql

# Remove user preference fields (night_owl, activity_intensity_preference, crowd_tolerance, tiredness_level, accessibility_needs)
psql -d users -f database/migrations/005_remove_user_preference_fields.sql
```

## API configuration

The API uses `POSTGRES_USERS_DB=users` (see `api/.env.example`). Ensure the `users` database and tables exist; otherwise registration/login and trip creation will fail with 500 errors.
