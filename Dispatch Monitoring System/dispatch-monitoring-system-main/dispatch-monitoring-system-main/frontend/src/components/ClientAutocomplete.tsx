import { useState, useEffect, useRef } from "react";
import api from "../lib/api";
import type { CustomerSuggestion } from "../lib/types";
import "../styles/Autocomplete.css";

interface ClientAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSelect: (customer: CustomerSuggestion) => void;
  onBlur?: () => void;
  disabled?: boolean;
  required?: boolean;
  placeholder?: string;
  className?: string;
}

export default function ClientAutocomplete({
  value,
  onChange,
  onSelect,
  onBlur,
  disabled,
  required,
  placeholder,
  className,
}: ClientAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<CustomerSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const skipNextLookup = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (disabled) return;
    if (skipNextLookup.current) {
      skipNextLookup.current = false;
      return;
    }
    const q = value.trim();
    if (q.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const res = await api.get(`/customers/search?q=${encodeURIComponent(q)}`);
        if (cancelled) return;
        setSuggestions(res.data.data);
        setOpen(res.data.data.length > 0);
        setActiveIndex(-1);
      } catch {
        if (!cancelled) {
          setSuggestions([]);
          setOpen(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [value, disabled]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsFocused(false);
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const choose = (c: CustomerSuggestion) => {
    skipNextLookup.current = true;
    onSelect(c);
    setOpen(false);
    setSuggestions([]);
    setActiveIndex(-1);
  };

  const suggestionMeta = (c: CustomerSuggestion) => {
    const parts = [c.contact_number];
    if (c.account_number) parts.push(c.account_number);
    if (c.email) parts.push(c.email);
    parts.push(c.address);
    return parts.join(" · ");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      choose(suggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setIsFocused(false);
    }
  };

  return (
    <div className={`client-autocomplete${className ? ` ${className}` : ""}`} ref={containerRef}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => {
          setIsFocused(true);
          if (suggestions.length > 0) {
            setOpen(true);
          }
        }}
        onBlur={() => {
          setTimeout(() => {
            setIsFocused(false);
            setOpen(false);
          }, 0);
          onBlur?.();
        }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        required={required}
        placeholder={placeholder}
        autoComplete="off"
      />
      {open && isFocused && (
        <ul className="autocomplete-list">
          {suggestions.map((c, i) => (
            <li
              key={c.id}
              className={i === activeIndex ? "autocomplete-item active" : "autocomplete-item"}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(c);
              }}
            >
              <span className="autocomplete-name">{c.name}</span>
              <span className="autocomplete-meta">
                {suggestionMeta(c)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {loading && <span className="autocomplete-loading">…</span>}
    </div>
  );
}
