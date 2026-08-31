import { useState, useEffect, useCallback, useRef } from "react";

const COLORS = {
  default: "#e2e8f0",
  hover: "#d3d9e0",
  dragging: "#aeb8c6",
};

export default function CustomScrollbar() {
  const [scrollState, setScrollState] = useState({ scrollTop: 0, scrollHeight: 0, clientHeight: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const dragStartRef = useRef({ scrollTop: 0, mouseY: 0 });

  const updateScrollState = useCallback(() => {
    setScrollState({
      scrollTop: window.scrollY,
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: window.innerHeight,
    });
  }, []);

  useEffect(() => {
    updateScrollState();
    window.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState, { passive: true });
    return () => {
      window.removeEventListener("scroll", updateScrollState);
      window.removeEventListener("resize", updateScrollState);
    };
  }, [updateScrollState]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartRef.current = {
      scrollTop: window.scrollY,
      mouseY: e.clientY,
    };
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return;
    const { scrollHeight, clientHeight } = scrollState;
    if (scrollHeight <= clientHeight) return;

    const maxScroll = scrollHeight - clientHeight;
    const deltaY = e.clientY - dragStartRef.current.mouseY;
    const scrollDelta = (deltaY / clientHeight) * scrollHeight;
    const newScrollTop = Math.max(0, Math.min(maxScroll, dragStartRef.current.scrollTop + scrollDelta));
    window.scrollTo(0, newScrollTop);
  }, [isDragging, scrollState]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "grabbing";
      document.body.style.userSelect = "none";
    }
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const { scrollTop, scrollHeight, clientHeight } = scrollState;
  const maxScroll = scrollHeight - clientHeight;
  const isVisible = maxScroll > 0;

  const thumbHeight = maxScroll > 0
    ? Math.min(Math.max((clientHeight / scrollHeight) * clientHeight, 20), clientHeight)
    : 40;
  const thumbTop = maxScroll > 0 ? (scrollTop / maxScroll) * (clientHeight - thumbHeight) : 0;

  const thumbColor = isDragging ? COLORS.dragging : isHovered ? COLORS.hover : COLORS.default;

  return (
    <div
      className={`custom-scrollbar ${isVisible ? "visible" : ""}`}
      aria-hidden="true"
    >
      <div className="custom-scrollbar-track" style={{ height: "100vh" }}>
        <div
          className={`custom-scrollbar-thumb ${isDragging ? "dragging" : ""}`}
          style={{
            top: thumbTop,
            height: thumbHeight,
            position: "fixed",
            background: thumbColor,
          }}
          onMouseDown={handleMouseDown}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        />
      </div>
    </div>
  );
}