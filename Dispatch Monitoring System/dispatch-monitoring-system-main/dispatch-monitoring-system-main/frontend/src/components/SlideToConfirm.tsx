import { useRef, useState, useCallback, useEffect, useImperativeHandle, forwardRef } from "react";
import "../styles/SlideToConfirm.css";

interface SlideToConfirmProps {
  label?: string;
  confirmedLabel?: string;
  onConfirm: () => void;
  disabled?: boolean;
  loading?: boolean;
}

export interface SlideToConfirmHandle {
  reset: () => void;
}

const THUMB_WIDTH = 52;
const CONFIRM_THRESHOLD = 0.9;
const SNAP_TRANSITION = "transform 0.25s ease, width 0.25s ease";
const DRAG_TRANSITION = "none";

const SlideToConfirm = forwardRef<SlideToConfirmHandle, SlideToConfirmProps>(function SlideToConfirm(
  {
    label = "Slide to Dispatch",
    confirmedLabel = "Dispatching...",
    onConfirm,
    disabled = false,
    loading = false,
  },
  ref
) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const draggingRef = useRef(false);
  const offsetRef = useRef(0);

  const maxOffset = useCallback(() => {
    const track = trackRef.current;
    if (!track) return 0;
    return track.clientWidth - THUMB_WIDTH - 8;
  }, []);

  const reset = useCallback(() => {
    setOffset(0);
    offsetRef.current = 0;
    setDragging(false);
    draggingRef.current = false;
    setConfirmed(false);
  }, []);

  useImperativeHandle(ref, () => ({ reset }), [reset]);

  const moveTo = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const max = maxOffset();
      let next = clientX - rect.left - THUMB_WIDTH / 2 - 4;
      if (next < 0) next = 0;
      if (next > max) next = max;
      setOffset(next);
      offsetRef.current = next;
    },
    [maxOffset]
  );

  const endDrag = useCallback(() => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    setDragging(false);
    const max = maxOffset();
    const current = offsetRef.current;

    const progress = max > 0 ? current / max : 0;
    if (progress >= CONFIRM_THRESHOLD) {
      setOffset(max);
      offsetRef.current = max;
      setConfirmed(true);
      onConfirm();
    } else {
      setOffset(0);
      offsetRef.current = 0;
    }
  }, [maxOffset, onConfirm]);

  useEffect(() => {
    if (!dragging) return;
    const handleMove = (e: PointerEvent) => moveTo(e.clientX);
    const handleUp = () => endDrag();
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, [dragging, moveTo, endDrag]);

  const startDrag = (e: React.PointerEvent) => {
    if (disabled || loading || confirmed) return;
    e.preventDefault();
    draggingRef.current = true;
    setDragging(true);
    moveTo(e.clientX);
  };

  const isDone = confirmed || loading;
  const progress = maxOffset() > 0 ? offset / maxOffset() : 0;
  const transition = dragging ? DRAG_TRANSITION : SNAP_TRANSITION;

  return (
    <div
      ref={trackRef}
      className={`slide-confirm${disabled ? " disabled" : ""}${isDone ? " confirmed" : ""}`}
    >
      <div
        className="slide-confirm-fill"
        style={{
          width: isDone ? "100%" : `${THUMB_WIDTH + offset}px`,
          transition,
        }}
      />

      <span
        className="slide-confirm-label"
        style={{ opacity: isDone ? 1 : 1 - progress * 0.8 }}
      >
        {isDone ? confirmedLabel : label}
      </span>

      <button
        type="button"
        className="slide-confirm-thumb"
        style={{
          transform: `translateX(${offset}px)`,
          transition,
        }}
        onPointerDown={startDrag}
        disabled={disabled || isDone}
        aria-label={label}
      >
        {isDone ? "✓" : "→"}
      </button>

      {confirmed && !loading && (
        <button
          type="button"
          className="slide-confirm-reset"
          onClick={() => reset()}
        >
          Reset
        </button>
      )}
    </div>
  );
});

export default SlideToConfirm;