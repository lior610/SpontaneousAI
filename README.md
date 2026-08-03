# SpontaneousAI

The system generates a personal and dynamic trip itinerary in real time using data from blogs, Google Maps ratings, and other databases.

| Service | Folder | Responsibility | Tech Stack |
|---------|--------|----------------|------------|
| Web | /web | Shows the UI to the user. | React |
| API | /api | Handles user accounts, forwards requests to Engine. | Node.js |
| Engine | /engine | "Thinks" about recommendations, manages DB Structure. | Python, FastAPI |
| Database | /database | Stores data and AI Vectors. | PostgreSQL |
| Shared | /shared/api | Ensures Web and Engine speak the same language. | OpenAPI |

- Engine: http://localhost:8000
- API: http://localhost:3000
- Web: http://localhost:5173

## How to Run

### Local Development

For active development with hot-reloading enabled, use the default `docker-compose.yml`:

```bash
# 1. Create a .env file from the example
cp .env.example .env

# 2. Build and start the services
docker-compose up -d --build
```
This mounts your local directories so changes are reflected instantly without needing to rebuild.

### Production Deployment (Remote Server)

For deploying to a production server (which compiles the frontend to static files and serves them via Nginx):

```bash
# 1. Ensure you have your .env file with production secrets
# 2. Build and start using the production compose file
docker-compose -f docker-compose.prod.yml up -d --build
```
**Note:** The production configuration binds ports 80 and 443 to the web container and looks for SSL certificates in `/etc/ssl/cs`. Ensure your certificates match the configuration in `web/nginx.conf` before deploying.

---

## 📱 Mobile Native App Installation (Android)

SpontaneousAI includes a native mobile container built with **Capacitor**, providing continuous background location tracking (`onArrive` and `onDepart`) and native system notifications.

### 1. Generating Mobile Artifacts via GitHub Actions
Mobile builds are compiled manually via GitHub Actions to produce ready-to-install binaries:
1. Go to your GitHub repository -> **Actions** tab.
2. Select the **Build Mobile App Artifacts (Android)** workflow.
3. Click **Run workflow** (select the `native-app-develop` branch).
4. Once completed, scroll down to **Artifacts** to download:
   - `SpontaneousAI-Android-APK` (`app-debug.apk`)

---

### 2. Installing on Android
1. Download `app-debug.apk` onto your Android phone or transfer it via USB.
2. Open the file on your device. If prompted, enable **"Install unknown apps"** for your File Manager or Chrome.
3. Tap **Install** and open **SpontaneousAI**.
4. Grant Location ("Allow all the time" for continuous background geofencing) and Notification permissions when prompted.

