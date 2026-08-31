import { useEffect, useState } from "react";
import { useConfigOptions } from "../../hooks/useConfigOptions";
import { useToast } from "../../context/ToastContext";
import type { ConfigListType, ConfigListModule, ConfigOption } from "../../lib/types";
import { Lock } from "lucide-react";
import "../../styles/ConfigurableListEditor.css";

interface ConfigurableListEditorProps {
  title: string;
  description?: string;
  list_type: ConfigListType;
  module: ConfigListModule;
}

const DEFAULT_COLOR = "#64748b";

export default function ConfigurableListEditor({ title, description, list_type, module }: ConfigurableListEditorProps) {
  const { addToast } = useToast();

  const [showInactive, setShowInactive] = useState(false);
  const { options, loading, error, createOption, updateOption, deactivateOption, reorder } =
    useConfigOptions(list_type, module, true);

  useEffect(() => {
    if (error) addToast(error, "error");
  }, [error]);

  const [newLabel, setNewLabel] = useState("");
  const [newColor, setNewColor] = useState(DEFAULT_COLOR);
  const [saving, setSaving] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editColor, setEditColor] = useState(DEFAULT_COLOR);

  const [dragId, setDragId] = useState<number | null>(null);

  const resetAddForm = () => {
    setNewLabel("");
    setNewColor(DEFAULT_COLOR);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim()) {
      addToast("Name is required", "error");
      return;
    }
    try {
      setSaving(true);
      await createOption({ label: newLabel.trim(), color: newColor });
      addToast("Option added successfully", "success");
      resetAddForm();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to add option", "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (opt: ConfigOption) => {
    setEditingId(opt.id);
    setEditLabel(opt.label);
    setEditColor(opt.color);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async () => {
    if (editingId == null) return;
    const opt = options.find((o) => o.id === editingId);
    if (!opt) return;

    if (opt.hardcoded) {
      if (editLabel.trim() !== opt.label) {
        addToast("Cannot rename hardcoded option", "error");
        return;
      }
      try {
        setSaving(true);
        await updateOption(editingId, { color: editColor });
        addToast("Option updated successfully", "success");
        setEditingId(null);
      } catch (err) {
        addToast(err instanceof Error ? err.message : "Failed to save", "error");
      } finally {
        setSaving(false);
      }
      return;
    }

    if (!editLabel.trim()) {
      addToast("Name is required", "error");
      return;
    }
    try {
      setSaving(true);
      await updateOption(editingId, { label: editLabel.trim(), color: editColor });
      addToast("Option updated successfully", "success");
      setEditingId(null);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to save", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (opt: ConfigOption) => {
    if (opt.hardcoded) {
      addToast("Cannot delete a hardcoded option", "error");
      return;
    }
    if (!confirm(`Deactivate "${opt.label}"? It will no longer appear as a choice. Existing records keep this value.`)) return;
    try {
      await deactivateOption(opt.id);
      addToast("Option deactivated successfully", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to deactivate", "error");
    }
  };

  const handleReactivate = async (opt: ConfigOption) => {
    try {
      await createOption({ label: opt.label, color: opt.color });
      addToast("Option reactivated successfully", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to reactivate", "error");
    }
  };

  const activeOptions = options.filter((o) => o.active);
  const inactiveOptions = options.filter((o) => !o.active);

  const handleDragStart = (id: number) => setDragId(id);
  const handleDragOver = (e: React.DragEvent) => e.preventDefault();

  const handleDrop = async (targetId: number) => {
    if (dragId == null || dragId === targetId) return;
    const ids = activeOptions.map((o) => o.id);
    const fromIdx = ids.indexOf(dragId);
    const toIdx = ids.indexOf(targetId);
    if (fromIdx === -1 || toIdx === -1) return;
    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, dragId);
    setDragId(null);
    try {
      await reorder(ids);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Failed to reorder", "error");
    }
  };

  return (
    <div className="config-list-editor">
      <div className="config-list-editor-header">
        <div>
          <h3>{title}</h3>
          {description && <p className="config-list-editor-desc">{description}</p>}
        </div>
        <label className="config-list-toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Show inactive
        </label>
      </div>

      <div className="config-list-editor-body">
        {loading ? (
          <p className="period-meta">Loading…</p>
        ) : (
          <div className="config-chip-row">
            {activeOptions.map((opt) =>
              editingId === opt.id ? (
                <div key={opt.id} className="config-chip-edit">
                  <input type="color" value={editColor} onChange={(e) => setEditColor(e.target.value)} className="config-color-input" />
                  <input
                    type="text"
                    value={editLabel}
                    onChange={(e) => !opt.hardcoded && setEditLabel(e.target.value)}
                    className="config-label-input"
                    autoFocus
                    readOnly={opt.hardcoded}
                  />
                  {opt.hardcoded && <span title="Hardcoded - label cannot be changed"><Lock className="config-chip-lock" size={12} /></span>}
                  <button type="button" className="btn-submit" disabled={saving} onClick={saveEdit}>Save</button>
                  <button type="button" className="btn-cancel" onClick={cancelEdit}>✕</button>
                </div>
              ) : (
                <div
                  key={opt.id}
                  className={`config-chip ${opt.hardcoded ? "config-chip-hardcoded" : ""}`}
                  draggable
                  onDragStart={() => handleDragStart(opt.id)}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(opt.id)}
                  style={{ backgroundColor: opt.color }}
                  onClick={() => startEdit(opt)}
                >
                  {opt.hardcoded && <span title="Hardcoded"><Lock className="config-chip-lock" size={12} /></span>}
                  {!opt.hardcoded && <span className="config-chip-drag-dot">⠿</span>}
                  <span className="config-chip-label">{opt.label}</span>
                  {!opt.hardcoded && (
                    <button
                      type="button"
                      className="config-chip-remove"
                      onClick={(e) => { e.stopPropagation(); handleDeactivate(opt); }}
                      title="Deactivate"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )
            )}
            {activeOptions.length === 0 && <span className="config-option-empty">No options yet.</span>}
          </div>
        )}

        {showInactive && inactiveOptions.length > 0 && (
          <>
            <div className="config-inactive-divider">Inactive</div>
            <div className="config-chip-row">
              {inactiveOptions.map((opt) => (
                <div key={opt.id} className="config-chip config-chip-inactive" style={{ backgroundColor: opt.color }} onClick={() => handleReactivate(opt)} title="Click to reactivate">
                  <span className="config-chip-label">{opt.label}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <form className="config-add-form" onSubmit={handleAdd}>
        <input type="color" value={newColor} onChange={(e) => setNewColor(e.target.value)} className="config-color-input" />
        <input type="text" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="New option name" className="config-label-input" />
        <button type="submit" className="btn-add" disabled={saving}>+ Add</button>
      </form>
    </div>
  );
}