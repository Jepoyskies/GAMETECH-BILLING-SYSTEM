import { useEffect, useRef, useState } from "react";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import "../../styles/Filters.css";

interface SearchFilterInputProps {
  value?: string;
  placeholder: string;
  onChange: (value: string | undefined) => void;
}

export default function SearchFilterInput({
  value = "",
  placeholder,
  onChange,
}: SearchFilterInputProps) {
  const [local, setLocal] = useState(value);
  const debounced = useDebouncedValue(local, 350);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    setLocal(value);
  }, [value]);

  useEffect(() => {
    const next = debounced.trim() || undefined;
    const current = value?.trim() || undefined;
    if (next !== current) {
      onChangeRef.current(next);
    }
  }, [debounced, value]);

  return (
    <div className="filter-search-input">
      <input
        type="text"
        placeholder={placeholder}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
      />
      {local && (
        <button
          type="button"
          className="filter-search-clear"
          aria-label="Clear"
          onClick={() => setLocal("")}
        >
          ×
        </button>
      )}
    </div>
  );
}
