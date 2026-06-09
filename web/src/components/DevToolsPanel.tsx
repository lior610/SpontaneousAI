import React, { useState } from 'react';
import { showAppNotification } from '../services/notificationService';

// A simple global state for dev tools
export const devToolsState = {
  mockTimeEnabled: false,
  mockTime: new Date().toISOString(),
};

// Global interceptor for geolocation to allow live spoofing
const watchCallbacks = new Set<PositionCallback>();
if ('geolocation' in navigator) {
  const originalWatch = navigator.geolocation.watchPosition;
  navigator.geolocation.watchPosition = function (success, error, options) {
    watchCallbacks.add(success);
    const id = originalWatch.call(navigator.geolocation, success, error, options);
    // Simple hack to cleanup, though not strictly necessary for devtools
    return id;
  };

  const originalClear = navigator.geolocation.clearWatch;
  navigator.geolocation.clearWatch = function (id) {
    // We don't easily know which callback matches the ID, but it's just for devtools
    return originalClear.call(navigator.geolocation, id);
  };
  
  const originalGet = navigator.geolocation.getCurrentPosition;
  navigator.geolocation.getCurrentPosition = function (success, error, options) {
    if ((window as any).__MOCK_GPS) {
      success((window as any).__MOCK_GPS);
    } else {
      originalGet.call(navigator.geolocation, success, error, options);
    }
  };
}

export function DevToolsPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [lat, setLat] = useState('32.0853'); // Tel aviv
  const [lng, setLng] = useState('34.7818');
  const now = new Date();
  const defaultTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
  const [mockTimeInput, setMockTimeInput] = useState(defaultTime);

  // DevTools enabled for production demo
  // if (import.meta.env.MODE !== 'development') {
  //   return null;
  // }

  const handleTestNotification = () => {
    showAppNotification('Test Notification', 'This is a test from DevTools!');
  };

  const handleSimulateLocation = () => {
    if ('geolocation' in navigator) {
      const mockPos: any = {
        coords: {
          latitude: parseFloat(lat),
          longitude: parseFloat(lng),
          accuracy: 10,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          speed: null,
        },
        timestamp: Date.now(),
      };
      
      (window as any).__MOCK_GPS = mockPos;
      
      // Trigger all registered watchers immediately
      watchCallbacks.forEach(cb => cb(mockPos));
      
      alert(`Simulated location set to ${lat}, ${lng}. \n(The geofence and tracking received this coordinate immediately).`);
    }
  };

  const handleSetMockTime = () => {
    if (mockTimeInput) {
      const [hourStr, minStr] = mockTimeInput.split(':');
      const d = new Date();
      d.setHours(parseInt(hourStr, 10));
      d.setMinutes(parseInt(minStr || '0', 10));
      d.setSeconds(0);
      d.setMilliseconds(0);
      
      devToolsState.mockTimeEnabled = true;
      devToolsState.mockTime = d.toISOString();
      alert(`Mock time set to ${mockTimeInput}. (Will be passed to backend engines)`);
    } else {
      devToolsState.mockTimeEnabled = false;
      alert('Mock time disabled.');
    }
  };

  return (
    <div className={`fixed bottom-4 left-4 z-50 transition-all ${isOpen ? 'w-80' : 'w-12 h-12'}`}>
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="w-full h-full bg-slate-800 text-white rounded-full flex items-center justify-center shadow-lg hover:bg-slate-700"
          title="DevTools"
        >
          🛠️
        </button>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg shadow-xl p-4 flex flex-col gap-4 text-sm">
          <div className="flex justify-between items-center border-b pb-2">
            <h3 className="font-bold">DevTools</h3>
            <button onClick={() => setIsOpen(false)} className="text-slate-500 hover:text-slate-800">
              ✕
            </button>
          </div>

          <div className="flex flex-col gap-2 border-b pb-2">
            <h4 className="font-semibold text-xs text-slate-500 uppercase">Notifications</h4>
            <button
              onClick={handleTestNotification}
              className="bg-blue-500 text-white px-3 py-1.5 rounded hover:bg-blue-600 w-full"
            >
              Test Base Notification
            </button>
          </div>

          <div className="flex flex-col gap-2 border-b pb-2">
            <h4 className="font-semibold text-xs text-slate-500 uppercase">Simulate GPS</h4>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Lat"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                className="border p-1 w-full rounded"
              />
              <input
                type="text"
                placeholder="Lng"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                className="border p-1 w-full rounded"
              />
            </div>
            <button
              onClick={handleSimulateLocation}
              className="bg-green-500 text-white px-3 py-1.5 rounded hover:bg-green-600 w-full"
            >
              Set GPS Location
            </button>
          </div>

          <div className="flex flex-col gap-2">
            <h4 className="font-semibold text-xs text-slate-500 uppercase">Simulate Time</h4>
            <div className="flex gap-2 items-center">
              <input
                type="time"
                value={mockTimeInput}
                onChange={(e) => setMockTimeInput(e.target.value)}
                className="border p-1 w-full rounded"
              />
              <button
                onClick={handleSetMockTime}
                className="bg-purple-500 text-white px-3 py-1.5 rounded hover:bg-purple-600 whitespace-nowrap"
              >
                Set Time
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
