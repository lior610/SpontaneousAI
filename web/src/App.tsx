import { Routes, Route } from "react-router-dom";

import { LandingPage } from "./pages/LandingPage";
import { TripPage } from "./pages/TripPage";
import WizardPage from "./pages/WizardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFound } from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/trip" element={<TripPage />} />
      <Route path="/wizard" element={<WizardPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
