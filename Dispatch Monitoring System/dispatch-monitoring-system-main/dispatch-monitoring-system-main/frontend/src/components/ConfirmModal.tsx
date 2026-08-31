import { createPortal } from "react-dom";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: "default" | "danger";
}

export default function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  variant = "default",
}: ConfirmModalProps) {
  if (!open) return null;

  const modal = (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className={`form-modal ${variant === "danger" ? "danger" : ""}`}>
          <div className="form-header">
            <h2>{title}</h2>
          </div>
          <div className="form-body">
            <p className="delete-warning">{message}</p>
          </div>
          <div className="form-footer">
            <button type="button" className="btn-cancel" onClick={onCancel}>
              {cancelLabel}
            </button>
            <button
              type="button"
              className={variant === "danger" ? "btn-delete-submit" : "btn-submit"}
              onClick={onConfirm}
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}