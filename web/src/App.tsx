import { Routes, Route } from "react-router-dom";

import { LandingPage } from "./pages/LandingPage";
import { TripPage } from "./pages/TripPage";
import { TripsPage } from "./pages/TripsPage";
import { PastTripSummaryPage } from "./pages/PastTripSummaryPage";
import WizardPage from "./pages/WizardPage";
import { LoginPage } from "./pages/LoginPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { NotFound } from "./pages/NotFound";

import { NotificationProvider } from "./components/NotificationProvider";
import { DevToolsPanel } from "./components/DevToolsPanel";

export default function App() {
  return (
    <NotificationProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/trips" element={<TripsPage />} />
        <Route path="/trips/:tripId/summary" element={<PastTripSummaryPage />} />
        <Route path="/trip" element={<TripPage />} />
        <Route path="/wizard" element={<WizardPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <DevToolsPanel />
    </NotificationProvider>
  );
}
