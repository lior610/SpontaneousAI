import { useCallback, useRef, useEffect, useState } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, OverlayViewF, OverlayView } from '@react-google-maps/api';

interface MapViewProps {
  attractionLat: number;
  attractionLng: number;
  attractionTitle: string;
  userLat?: number;
  userLng?: number;
  showLocationWarning?: boolean;
}

const containerStyle = {
  width: '100%',
  height: '100%',
};

const libraries: ('marker' | 'geometry')[] = ['marker', 'geometry'];

export function MapView({ attractionLat, attractionLng, attractionTitle, userLat, userLng, showLocationWarning }: MapViewProps) {
  const mapRef = useRef<google.maps.Map | null>(null);
  const rendererRef = useRef<google.maps.DirectionsRenderer | null>(null);
  const [walkingMinutes, setWalkingMinutes] = useState<string | null>(null);

  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
    libraries,
  });

  const hasBothPins = userLat != null && userLng != null;

  // Fetch walking route between user and attraction, render it on the map
  useEffect(() => {
    if (!isLoaded || !hasBothPins) {
      setWalkingMinutes(null);
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
      return;
    }

    // Retry up to 10 times waiting for map ref to be available
    let retryCount = 0;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const tryRoute = () => {
      if (cancelled) return;
      if (!mapRef.current) {
        if (retryCount >= 10) return;
        retryCount++;
        timeoutId = setTimeout(tryRoute, 300);
        return;
      }

      // Request walking directions from Google
      const directionsService = new google.maps.DirectionsService();
      directionsService.route(
        {
          origin: { lat: userLat!, lng: userLng! },
          destination: { lat: attractionLat, lng: attractionLng },
          travelMode: google.maps.TravelMode.WALKING,
        },
        (result, status) => {
          if (cancelled) return;
          if (status === 'OK' && result) {
            if (rendererRef.current) {
              rendererRef.current.setMap(null);
            }
            // Draw the route polyline on the map
            rendererRef.current = new google.maps.DirectionsRenderer({
              map: mapRef.current!,
              suppressMarkers: true,
              polylineOptions: {
                strokeColor: '#4285F4',
                strokeOpacity: 0.8,
                strokeWeight: 4,
              },
            });
            rendererRef.current.setDirections(result);

            const leg = result.routes[0]?.legs[0];
            if (leg?.duration) {
              setWalkingMinutes(leg.duration.text);
            }
          }
        }
      );
    };

    tryRoute();

    // Cleanup: cancel pending retries and remove route renderer
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
    };
  }, [isLoaded, attractionLat, attractionLng, userLat, userLng, hasBothPins]);

  // Auto-zoom to fit both pins, or center on attraction if only one pin
  const fitBounds = useCallback(() => {
    if (!mapRef.current) return;
    if (hasBothPins) {
      const bounds = new google.maps.LatLngBounds();
      bounds.extend({ lat: attractionLat, lng: attractionLng });
      bounds.extend({ lat: userLat, lng: userLng });
      mapRef.current.fitBounds(bounds, 60);
    } else {
      mapRef.current.setCenter({ lat: attractionLat, lng: attractionLng });
      mapRef.current.setZoom(15);
    }
  }, [attractionLat, attractionLng, userLat, userLng, hasBothPins]);

  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    fitBounds();
  }, [fitBounds]);

  // Re-fit bounds when coordinates change (e.g. user location arrives late)
  useEffect(() => {
    fitBounds();
  }, [fitBounds]);

  if (!isLoaded) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-muted rounded-xl">
        <span className="text-sm text-muted-foreground">Loading map...</span>
      </div>
    );
  }

  const midpoint = hasBothPins
    ? { lat: (attractionLat + userLat) / 2, lng: (attractionLng + userLng) / 2 }
    : null;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Shown when no real user coords are available (no GPS, no completed activities yet) */}
      {showLocationWarning && (
        <div style={{
          position: 'absolute',
          top: 8,
          left: 8,
          right: 8,
          zIndex: 10,
          background: 'rgba(255, 255, 255, 0.92)',
          borderRadius: '8px',
          padding: '6px 12px',
          fontSize: '12px',
          color: '#6b7280',
          textAlign: 'center',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
        }}>
          Couldn't find recent location
        </div>
      )}
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={{ lat: attractionLat, lng: attractionLng }}
        zoom={14}
        onLoad={onLoad}
        options={{
          disableDefaultUI: true,
          zoomControl: true,
          mapTypeControl: false,
          streetViewControl: false,
        }}
      >
      {/* Attraction pin (red default marker) */}
      <MarkerF
        position={{ lat: attractionLat, lng: attractionLng }}
        title={attractionTitle}
      />
      {hasBothPins && (
        <>
          {/* User location pin (blue circle) */}
          <MarkerF
            position={{ lat: userLat, lng: userLng }}
            title="You"
            icon={{
              path: google.maps.SymbolPath.CIRCLE,
              scale: 10,
              fillColor: '#4285F4',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 3,
            }}
          />
          {/* Walking time badge shown at midpoint of route */}
          {walkingMinutes && midpoint && (
            <OverlayViewF
              position={midpoint}
              mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
            >
              <div style={{
                transform: 'translate(8px, -50%)',
                background: '#fff',
                border: '2px solid #4285F4',
                borderRadius: '16px',
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 700,
                color: '#4285F4',
                boxShadow: '0 2px 8px rgba(66,133,244,0.25)',
                whiteSpace: 'nowrap',
              }}>
                {walkingMinutes}
              </div>
            </OverlayViewF>
          )}
        </>
      )}
      </GoogleMap>
    </div>
  );
}
