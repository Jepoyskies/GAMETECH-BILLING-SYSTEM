const ROUND = 6;
const round = (n: number) => parseFloat(n.toFixed(ROUND));

import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import { Map, Satellite, Lock, Trash2, X } from "lucide-react";
import "leaflet/dist/leaflet.css";
import "./leafletSetup";
import "../../styles/map.css";
import { DEFAULT_MAP_CENTER } from "../../lib/constants";

type MapType = "default" | "satellite";

const TILE_LAYERS = {
  default: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  satellite: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
};

const LABEL_TILES = "https://mt.google.com/vt/lyrs=h&x={x}&y={y}&z={z}";

export interface LatLng {
  latitude: number;
  longitude: number;
}

interface LocationMapPanelProps {
  value?: LatLng | null;
  initialQuery?: string;
  readOnly?: boolean;
  required?: boolean;
  onChange: (value: LatLng | null) => void;
  onAddressChange?: (address: string) => void;
  onCollapse?: () => void;
}

interface NominatimResult {
  display_name: string;
  lat: string;
  lon: string;
}

const PH_VIEWBOX = "114.0,21.5,127.0,4.5";

function Recenter({ position }: { position: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.setView(position, 16);
  }, [position, map]);
  return null;
}

function InteractionToggle({ enabled }: { enabled: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (enabled) {
      map.scrollWheelZoom.enable();
      map.doubleClickZoom.enable();
      map.touchZoom.enable();
    } else {
      map.scrollWheelZoom.disable();
      map.doubleClickZoom.disable();
      map.touchZoom.disable();
    }
  }, [enabled, map]);
  return null;
}

function ClickHandler({
  enabled,
  onPick,
}: {
  enabled: boolean;
  onPick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (enabled) onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

async function searchNominatim(
  query: string,
  signal: AbortSignal,
  opts: { countryBias: boolean }
): Promise<NominatimResult[]> {
  const params = new URLSearchParams({
    format: "json",
    limit: "5",
    q: query,
  });
  if (opts.countryBias) {
    params.set("countrycodes", "ph");
  } else {
    params.set("viewbox", PH_VIEWBOX);
    params.set("bounded", "0");
  }
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?${params.toString()}`,
    { signal, headers: { Accept: "application/json" } }
  );
  if (!res.ok) throw new Error("Search failed");
  return (await res.json()) as NominatimResult[];
}

export default function LocationMapPanel({
  value,
  initialQuery,
  readOnly = false,
  required,
  onChange,
  onAddressChange,
  onCollapse,
}: LocationMapPanelProps) {
  const [pin, setPin] = useState<LatLng | null>(value ?? null);
  const [query, setQuery] = useState(initialQuery ?? "");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [recenter, setRecenter] = useState<[number, number] | null>(null);
  const [mapType, setMapType] = useState<MapType>("default");
  const [editArmed, setEditArmed] = useState(false);
  const [viewArmed, setViewArmed] = useState(false);

  const zoomEnabled = readOnly ? viewArmed : editArmed;

  useEffect(() => {
    setPin(value ? { latitude: round(value.latitude), longitude: round(value.longitude) } : null);
  }, [value]);

  useEffect(() => {
    setQuery(initialQuery ?? "");
  }, [initialQuery]);

  useEffect(() => {
    if (readOnly) {
      setEditArmed(false);
      setViewArmed(false);
    }
  }, [readOnly]);

  const initialCenter: [number, number] = value
    ? [round(value.latitude), round(value.longitude)]
    : [DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng];

  const abortRef = useRef<AbortController | null>(null);

  const armEditing = () => {
    setEditArmed(true);
  };

  const lockEditing = () => {
    setEditArmed(false);
  };

  const runSearch = async () => {
    const q = query.trim();
    if (!q) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      setSearching(true);
      setSearchError(null);
      let data = await searchNominatim(q, controller.signal, { countryBias: true });
      if (data.length === 0) {
        data = await searchNominatim(q, controller.signal, { countryBias: false });
      }
      setResults(data);
      if (data.length === 0) setSearchError("No matches found");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setSearchError("Address search unavailable — click the map to drop a pin");
    } finally {
      setSearching(false);
    }
  };

  const pickResult = (r: NominatimResult) => {
    const lat = parseFloat(r.lat);
    const lng = parseFloat(r.lon);
    const next = { latitude: round(lat), longitude: round(lng) };
    setPin(next);
    setRecenter([lat, lng]);
    setResults([]);
    onChange(next);
  };

  const handlePick = async (lat: number, lng: number) => {
    const next = { latitude: round(lat), longitude: round(lng) };
    setPin(next);
    onChange(next);
    lockEditing();
  };

  const handleClearKeepArmed = () => {
    setPin(null);
    onChange(null);
  };

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return (
    <div className="map-panel">
      <div className="map-search">
        {readOnly ? (
          query ? <input type="text" value={query} disabled /> : null
        ) : (
          <>
            <input
              type="text"
              value={query}
              required={required}
              onChange={(e) => {
                setQuery(e.target.value);
                onAddressChange?.(e.target.value);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  runSearch();
                }
              }}
            />
            <button
              type="button"
              className="btn-map"
              disabled={searching}
              onClick={() => runSearch()}
            >
              {searching ? "Searching..." : "Search"}
            </button>
            {searchError && <p className="map-hint">{searchError}</p>}
            {results.length > 0 && (
              <ul className="map-search-results">
                {results.map((r, i) => (
                  <li key={i} onClick={() => pickResult(r)}>
                    {r.display_name}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      {readOnly && !value ? (
        <div className="map-canvas map-not-set">
          <span className="map-not-set-text">Not set</span>
        </div>
      ) : (
      <div className="map-canvas" style={{ position: "relative" }}>
        <MapContainer
          center={initialCenter}
          zoom={value ? 16 : 13}
          scrollWheelZoom={zoomEnabled}
          doubleClickZoom={zoomEnabled}
          touchZoom={zoomEnabled}
          dragging
        >
          <InteractionToggle enabled={zoomEnabled} />
          <TileLayer
            attribution={
              mapType === "default"
                ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                : '&copy; Esri'
            }
            url={TILE_LAYERS[mapType]}
          />
          {mapType === "satellite" && (
            <TileLayer url={LABEL_TILES} opacity={0.8} zIndex={10} />
          )}
          <Recenter position={recenter} />
          <ClickHandler enabled={!readOnly && editArmed} onPick={handlePick} />
          {pin && <Marker position={[pin.latitude, pin.longitude]} />}
        </MapContainer>

        <div
          className="map-floating-controls"
          style={{
            position: "absolute",
            bottom: 8,
            left: 8,
            zIndex: 1000,
            display: "flex",
            gap: 6,
          }}
        >
          <button
            type="button"
            className="btn-map btn-map-type"
            onClick={() => setMapType(mapType === "default" ? "satellite" : "default")}
            title={mapType === "default" ? "Switch to satellite" : "Switch to default"}
          >
            {mapType === "default" ? <Satellite size={16} /> : <Map size={16} />}
          </button>
        </div>

        {!readOnly && !editArmed && (
          <div
            className="map-edit-lock-overlay"
            role="button"
            tabIndex={0}
            onClick={armEditing}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") armEditing();
            }}
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 1000,
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              background: "rgba(255,255,255,0.3)",
              backdropFilter: "blur(1px)",
              userSelect: "none",
            }}
          >
            <Lock size={20} />
            <span
              className="map-edit-lock-hint"
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: "#1f1f1f",
              }}
            >
              Click to unlock and edit pin location
            </span>
          </div>
        )}

        {readOnly && !viewArmed && (
          <div
            role="button"
            tabIndex={0}
            onClick={() => setViewArmed(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setViewArmed(true);
            }}
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 1000,
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <span
              style={{
                position: "absolute",
                bottom: 8,
                left: "50%",
                transform: "translateX(-50%)",
                background: "rgba(63, 63, 63, 0.55)",
                color: "#fff",
                fontSize: 11,
                fontWeight: 500,
                padding: "4px 12px",
                borderRadius: 6,
                whiteSpace: "nowrap",
                pointerEvents: "none",
              }}
            >
              Click to interact with map
            </span>
          </div>
        )}

        {!readOnly && editArmed && (
          <div
            className="map-edit-armed-badge"
            style={{
              position: "absolute",
              top: 8,
              right: 8,
              zIndex: 1000,
              display: "flex",
              alignItems: "center",
              background: "rgba(40,40,40,0.45)",
              color: "#fff",
              fontSize: 11,
              fontWeight: 500,
              borderRadius: 6,
              overflow: "hidden",
            }}
          >
            <span
              style={{
                padding: "4px 8px",
                whiteSpace: "nowrap",
              }}
            >
              Click map to set pin
            </span>

            {pin && (
              <button
                type="button"
                onClick={handleClearKeepArmed}
                title="Clear pin"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 24,
                  height: 24,
                  background: "transparent",
                  border: "none",
                  borderLeft: "1px solid rgba(255,255,255,0.2)",
                  color: "#fff",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.15)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <Trash2 size={12} />
              </button>
            )}

            <button
              type="button"
              onClick={lockEditing}
              title="Cancel editing"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 24,
                height: 24,
                background: "transparent",
                border: "none",
                borderLeft: "1px solid rgba(255,255,255,0.2)",
                color: "#fff",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.15)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <X size={12} />
            </button>
          </div>
        )}
      </div>
      )}

      <div className="map-panel-footer">
        {!readOnly && editArmed ? (
          <div className="map-coords-editable">
            <div className="coords-field">
              <label>Lng</label>
              <input
                type="text"
                inputMode="decimal"
                value={pin ? pin.longitude : ""}
                placeholder="Longitude"
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === "") {
                    setPin(null);
                    onChange(null);
                    return;
                  }
                  if (!/^-?\d*\.?\d*$/.test(val)) return;
                  const lng = parseFloat(val);
                  if (isNaN(lng)) return;
                  const next = { latitude: pin?.latitude ?? 0, longitude: round(lng) };
                  setPin(next);
                  onChange(next);
                }}
              />
            </div>
            <div className="coords-field">
              <label>Lat</label>
              <input
                type="text"
                inputMode="decimal"
                value={pin ? pin.latitude : ""}
                placeholder="Latitude"
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === "") {
                    setPin(null);
                    onChange(null);
                    return;
                  }
                  if (!/^-?\d*\.?\d*$/.test(val)) return;
                  const lat = parseFloat(val);
                  if (isNaN(lat)) return;
                  const next = { latitude: round(lat), longitude: pin?.longitude ?? 0 };
                  setPin(next);
                  onChange(next);
                }}
              />
            </div>
          </div>
        ) : pin ? (
          <p className="map-coords">
            long-{pin.longitude.toFixed(6)} &nbsp; lat-{pin.latitude.toFixed(6)}
          </p>
        ) : (
          !readOnly && !editArmed && <p className="map-hint">Click the map to unlock, then set a pin.</p>
        )}

        <div className="map-panel-actions">
          {onCollapse && (
            <button type="button" className="btn-map" onClick={onCollapse}>
              Hide map
            </button>
          )}
        </div>
      </div>
    </div>
  );
}