# Mobile Native Container & CI/CD Pipeline Explanation (`Capacitor`)

## Overview
This document explains the technical architecture, design decisions, and build pipelines implemented to convert **SpontaneousAI** into a dual Web + Native Mobile application.

The mobile implementation provides **continuous screen-off background location tracking** (`onArrive` and `onDepart` geofence detection) and **native system notifications** across **Android** and **iOS**, while preserving 100% standard web compatibility for server deployment (`spontai.cs.colman.ac.il`).

---

## 🏗️ Architecture & Technology Stack

### 1. Capacitor Native Bridge
- **Framework**: Capacitor 8 (`@capacitor/core`, `@capacitor/cli`).
- **Function**: Acts as a lightweight native bridge wrapping the Vite React single-page app build (`web/dist`) into native Android Studio (`web/android`) and iOS Xcode (`web/ios`) containers.

### 2. Mobile Native Plugins
- **`@capacitor/geolocation`**: Continuous GPS location updates and distance calculation.
- **`@capacitor/local-notifications`**: Immediate lock-screen notification alerts on arrival (`onArrive`) or departure (`onDepart`).
- **`@capacitor/push-notifications`**: Remote server push notification handling.
- **`@capacitor/haptics`**: Physical tactile vibration alerts on arrival/departure events.
- **`@capacitor/status-bar`**: Seamless mobile status bar styling.

---

## 📍 Continuous Background Location & Geofencing Logic

### 1. Dual-Platform Abstraction
In [web/src/services/locationService.ts](file:///c:/Users/lior6/Desktop/תואר/SpontaneousAI/web/src/services/locationService.ts):
- Checks `Capacitor.isNativePlatform()`.
- **On Native Mobile App (Android/iOS)**: Uses `@capacitor/geolocation` with native OS background permissions, allowing `watchPosition` to run continuously even when the screen is locked in a pocket.
- **On Web Browser (`spontai.cs.colman.ac.il`)**: Seamlessly falls back to standard browser `navigator.geolocation`.

### 2. Arrival & Departure Notifications
In [web/src/services/nativeNotificationService.ts](file:///c:/Users/lior6/Desktop/תואר/SpontaneousAI/web/src/services/nativeNotificationService.ts):
- **Arrival (`onArrive`)**: When user comes within 120 meters of a destination, triggers haptic vibration and displays native alert: *"Arrived at [Attraction Name]"*.
- **Departure (`onDepart`)**: When user moves past 180 meters after arriving, triggers native alert: *"Departed [Attraction Name]. Ready for your next stop?"*.

---

## 🔒 Permissions & Native Manifests

### 🤖 Android (`web/android/app/src/main/AndroidManifest.xml`)
Added permissions required for background location and notifications:
- `android.permission.ACCESS_FINE_LOCATION`
- `android.permission.ACCESS_COARSE_LOCATION`
- `android.permission.ACCESS_BACKGROUND_LOCATION`
- `android.permission.FOREGROUND_SERVICE`
- `android.permission.FOREGROUND_SERVICE_LOCATION`
- `android.permission.POST_NOTIFICATIONS`
- `android.permission.VIBRATE`

### 🍎 iOS (`web/ios/App/App/Info.plist`)
Added privacy usage descriptions and background modes:
- `NSLocationAlwaysAndWhenInUseUsageDescription`
- `NSLocationWhenInUseUsageDescription`
- `UIBackgroundModes`: `["location"]`

---

## ⚙️ CI/CD Mobile Build Pipeline (GitHub Actions)

Workflow file: [.github/workflows/mobile-build.yml](file:///c:/Users/lior6/Desktop/תואר/SpontaneousAI/.github/workflows/mobile-build.yml)

- **Trigger**: Manual workflow dispatch (`workflow_dispatch`).
- **Android Job (`ubuntu-latest`)**:
  1. Sets up JDK 17 & Node 20.
  2. Runs `npm run build` in `web/` and `npx cap sync android`.
  3. Compiles Android Debug APK via `./gradlew assembleDebug`.
  4. Uploads downloadable artifact: `SpontaneousAI-Android-APK` (`app-debug.apk`).
- **iOS Job (`macos-latest`)**:
  1. Sets up Xcode & Node 20 on Apple Silicon runners.
  2. Runs `npm run build` in `web/` and `npx cap sync ios`.
  3. Compiles iOS Simulator App bundle via `xcodebuild`.
  4. Uploads downloadable artifact: `SpontaneousAI-iOS-App` (`SpontaneousAI-iOS-App.zip`).

---

## 📱 App Launcher Icons & Splash Screens

Generated automatically via `@capacitor/assets` from the core SVG logo ([web/public/logo.svg](file:///c:/Users/lior6/Desktop/תואר/SpontaneousAI/web/public/logo.svg)):
- **Android**: Generated all density launcher icons (`mipmap-ldpi`, `mdpi`, `hdpi`, `xhdpi`, `xxhdpi`, `xxxhdpi`) and adaptive splash screens.
- **iOS**: Generated `AppIcon.appiconset` and storyboard splash screens.
