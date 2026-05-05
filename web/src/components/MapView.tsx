import { useCallback, useRef, useEffect, useState } from 'react';
import { GoogleMap, useJsApiLoader, MarkerF, OverlayViewF, OverlayView } from '@react-google-maps/api';

interface MapViewProps {
  attractionLat: number;
  attractionLng: number;
  attractionTitle: string;
  userLat?: number;
  userLng?: number;
}

const containerStyle = {
  width: '100%',
  height: '100%',
};

const libraries: ('marker' | 'geometry')[] = ['marker', 'geometry'];

export function MapView({ attractionLat, attractionLng, attractionTitle, userLat, userLng }: MapViewProps) {
  const mapRef = useRef<google.maps.Map | null>(null);
  const rendererRef = useRef<google.maps.DirectionsRenderer | null>(null);
  const [walkingMinutes, setWalkingMinutes] = useState<string | null>(null);

  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
    libraries,
  });

  const hasBothPins = userLat != null && userLng != null;

  useEffect(() => {
    if (!isLoaded || !hasBothPins) {
      setWalkingMinutes(null);
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
      return;
    }

    const tryRoute = () => {
      if (!mapRef.current) {
        setTimeout(tryRoute, 300);
        return;
      }

      const directionsService = new google.maps.DirectionsService();
      directionsService.route(
        {
          origin: { lat: userLat!, lng: userLng! },
          destination: { lat: attractionLat, lng: attractionLng },
          travelMode: google.maps.TravelMode.WALKING,
        },
        (result, status) => {
          console.log('[MapView] Directions status:', status);
          if (status === 'OK' && result) {
            if (rendererRef.current) {
              rendererRef.current.setMap(null);
            }
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
          } else {
            console.warn('[MapView] Directions failed:', status);
          }
        }
      );
    };

    tryRoute();

    return () => {
      if (rendererRef.current) {
        rendererRef.current.setMap(null);
        rendererRef.current = null;
      }
    };
  }, [isLoaded, attractionLat, attractionLng, userLat, userLng, hasBothPins]);

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
      <MarkerF
        position={{ lat: attractionLat, lng: attractionLng }}
        title={attractionTitle}
      />
      {hasBothPins && (
        <>
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
  );
}
