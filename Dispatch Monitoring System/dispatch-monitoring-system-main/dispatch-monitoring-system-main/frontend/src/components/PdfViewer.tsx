import { useState, useCallback } from "react";
import { X, Loader } from "lucide-react";

interface PdfViewerProps {
  open: boolean;
  file: string;
  onClose: () => void;
}

export default function PdfViewer({ open, file, onClose }: PdfViewerProps) {
  const [loaded, setLoaded] = useState(false);

  const onIframeLoad = useCallback(() => {
    setLoaded(true);
  }, []);

  if (!open) return null;

  return (
    <div className="pdf-fullscreen">
      <button className="pdf-fullscreen-close" onClick={onClose} title="Close">
        <X size={24} />
      </button>
      {!loaded && (
        <div className="pdf-fullscreen-loading">
          <Loader size={40} className="pdf-fullscreen-spinner" />
          <span>Loading PDF...</span>
        </div>
      )}
      <iframe
        src={file}
        className={`pdf-fullscreen-iframe${loaded ? " loaded" : ""}`}
        onLoad={onIframeLoad}
        title="User Manual"
      />
    </div>
  );
}
