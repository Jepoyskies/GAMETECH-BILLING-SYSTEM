import { useState, useEffect, useRef } from "react";

const BGY_API = "https://psgc.gitlab.io/api/barangays/";
const CITY_API = "https://psgc.gitlab.io/api/cities-municipalities/";

interface PSGCItem {
  name: string;
  code?: string;
}

interface BarangayCityAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

let cachedBarangays: PSGCItem[] | null = null;
let cachedCities: PSGCItem[] | null = null;

function usePSGC() {
  const [barangays, setBarangays] = useState<PSGCItem[]>(cachedBarangays ?? []);
  const [cities, setCities] = useState<PSGCItem[]>(cachedCities ?? []);
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;

    if (!cachedBarangays) {
      fetch(BGY_API)
        .then((r) => r.json())
        .then((d) => {
          cachedBarangays = d;
          setBarangays(d);
        })
        .catch(() => {});
    }

    if (!cachedCities) {
      fetch(CITY_API)
        .then((r) => r.json())
        .then((d) => {
          cachedCities = d;
          setCities(d);
        })
        .catch(() => {});
    }
  }, []);

  return { barangays, cities };
}

export default function BarangayCityAutocomplete({
  value,
  onChange,
  disabled,
}: BarangayCityAutocompleteProps) {
  const { barangays, cities } = usePSGC();
  const [suggestions, setSuggestions] = useState<PSGCItem[]>([]);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasBarangay = value.includes(" / ") && barangays.length > 0;
  const selectedBrgy = hasBarangay
    ? barangays.find((b) => b.name === value.split(" / ")[0]) ?? null
    : null;
  const isCityMode = selectedBrgy !== null;

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function handleInput(raw: string) {
    const q = raw.toLowerCase().trim();
    if (q.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    let needle = q;
    let source = barangays;

    if (isCityMode && selectedBrgy) {
      source = cities;
      const prefix = selectedBrgy.name.toLowerCase() + " / ";
      if (q.startsWith(prefix)) {
        needle = q.slice(prefix.length);
      } else {
        source = barangays;
      }
    }

    const filtered = source
      .filter((item) => item.name.toLowerCase().includes(needle))
      .slice(0, 10);

    setSuggestions(filtered);
    setOpen(filtered.length > 0);
  }

  function choose(item: PSGCItem) {
    if (!isCityMode) {
      const val = item.name + " / ";
      onChange(val);
    } else {
      const val = (selectedBrgy?.name ?? "") + " / " + item.name;
      onChange(val);
    }
    setSuggestions([]);
    setOpen(false);
  }

  return (
    <div className="client-autocomplete" ref={containerRef}>
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          handleInput(e.target.value);
        }}
        onFocus={() => {
          if (suggestions.length > 0) setOpen(true);
        }}
        onBlur={() => {
          setTimeout(() => setOpen(false), 150);
        }}
        disabled={disabled}
        placeholder={disabled ? "" : isCityMode ? "Type city..." : "Type barangay..."}
        autoComplete="off"
      />
      {open && (
        <ul className="autocomplete-list">
          {suggestions.map((item) => (
            <li
              key={item.code || item.name}
              className="autocomplete-item"
              onMouseDown={(e) => {
                e.preventDefault();
                choose(item);
              }}
            >
              <span className="autocomplete-name">{item.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
