import LocationMapPanel, { LatLng } from "./LocationMapPanel";
import "../../styles/map.css";

interface LocationFieldProps {
  latitude?: number | null;
  longitude?: number | null;
  address?: string;
  disabled?: boolean;
  required?: boolean;
  onChange?: (value: LatLng | null) => void;
  onAddressChange?: (address: string) => void;
}

export default function LocationField({
  latitude,
  longitude,
  address,
  disabled = false,
  required,
  onChange,
  onAddressChange,
}: LocationFieldProps) {
  const hasPin =
    latitude !== null &&
    latitude !== undefined &&
    longitude !== null &&
    longitude !== undefined;

  const value: LatLng | null = hasPin
    ? { latitude: latitude as number, longitude: longitude as number }
    : null;

  return (
    <div className="location-field">
      <LocationMapPanel
        value={value}
        initialQuery={address}
        readOnly={disabled}
        required={required}
        onChange={(loc) => onChange?.(loc)}
        onAddressChange={onAddressChange}
      />
    </div>
  );
}