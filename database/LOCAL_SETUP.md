# Using a local PostgreSQL database

Use these steps to run the API against a local Postgres instance (no Docker).

## 1. Install and start PostgreSQL

**macOS (Homebrew):**

- Install (if needed): `brew install postgresql`
- Start: `brew services start postgresql`

Use `postgresql` with no version number so Homebrew uses the formula you have. If you installed a specific version (e.g. `postgresql@14`), use that name: `brew services start postgresql@14`.

**macOS (Postgres.app):** open the app so the server is running.

**Other:** start your Postgres server however you normally do.

## 2. Create databases and tables

With a **versioned** Homebrew install (e.g. `postgresql@18`), `psql` is not on your PATH. Use the full path:

```bash
$(brew --prefix postgresql@18)/bin/psql -h localhost -d postgres -f database/init.sql
```

Or add the bin to your PATH for this session, then run `psql`:

```bash
export PATH="$(brew --prefix postgresql@18)/bin:$PATH"
psql -h localhost -d postgres -f database/init.sql
```

Run from the **project root** (so the path `database/init.sql` is correct). If your setup uses a `postgres` user, add `-U postgres` before `-d postgres`.

**Homebrew default:** the DB user is often your macOS username (no password). Try:

```bash
psql -h localhost -d postgres -f database/init.sql
```

If you use a different user or password, add `-U YOUR_USER` and set `POSTGRES_USER` / `POSTGRES_PASSWORD` in `api/.env`.

If you get **"column email does not exist"** when registering, your `users` table was created before the `email` column existed. From the **project root** run:

```bash
psql -h localhost -d users -f database/migrations/001_add_email_to_users.sql
```

(Homebrew default: no `-U` so it uses your macOS user. If you use a different DB user, add `-U YOUR_USER`.)

## 3. Point the API at local Postgres

In the `api/` folder, copy the example env and adjust if needed:

```bash
cd api
cp .env.example .env
```

Edit `api/.env` if your local Postgres uses a different user/password.

## 4. Run the API

From the `api/` folder:

```bash
npm run dev
```

The API will use the `users` database on localhost for user and trip endpoints.

## 5. Test the API

With the API running (and using `api/.env` for local Postgres), from the `api/` folder run:

```bash
npm run test:api
```

This hits all user and trip endpoints (register, login, list, get by id, update, create trip, list trips, get trip, update trip, duplicate validations, delete trip, delete user) and reports pass/fail.
