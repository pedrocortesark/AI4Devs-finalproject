/**
 * FilterBar Component
 *
 * Persistent bottom bar combining filter controls and selection hints.
 * Replaces the draggable sidebar + conditional hint bar.
 *
 * Layout (left → right):
 *   [Agrupació ▾] [Material ▾]  X/Y piezas  [× Limpiar]  |  <selection info when part selected>
 *
 * Filter options are derived dynamically from the loaded parts data.
 *
 * @module FilterBar
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import { usePartsStore } from '@/stores/parts.store';
import styles from './FilterBar.module.css';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FilterDropdownProps {
  label: string;
  icon: string;
  options: readonly { value: string; label: string; color?: string }[];
  value: string[];
  onChange: (next: string[]) => void;
}

interface FilterBarProps {
  selectedId: string | null;
  showDetailsPanel: boolean;
  onShowDetails: () => void;
}

// ─── FilterDropdown ──────────────────────────────────────────────────────────

function FilterDropdown({ label, icon, options, value, onChange }: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggle = (optValue: string) => {
    if (value.includes(optValue)) {
      onChange(value.filter((v) => v !== optValue));
    } else {
      onChange([...value, optValue]);
    }
  };

  const isActive = value.length > 0;

  return (
    <div className={styles.dropdownAnchor} ref={ref}>
      <button
        className={`${styles.filterPill} ${isActive ? styles.filterPillActive : ''}`}
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{icon}</span>
        <span>{label}</span>
        {isActive && <span className={styles.pillBadge}>{value.length}</span>}
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}>▼</span>
      </button>

      {open && (
        <div className={styles.dropdown} role="listbox" aria-multiselectable="true">
          <div className={styles.dropdownTitle}>{label}</div>
          <div className={styles.dropdownList}>
            {options.map((opt) => {
              const checked = value.includes(opt.value);
              return (
                <div
                  key={opt.value}
                  role="option"
                  aria-selected={checked}
                  className={`${styles.dropdownItem} ${checked ? styles.dropdownItemChecked : ''}`}
                  onClick={() => toggle(opt.value)}
                >
                  <span className={`${styles.checkMark} ${checked ? styles.checkMarkChecked : ''}`}>
                    {checked && '✓'}
                  </span>
                  {opt.color && (
                    <span
                      className={styles.statusDot}
                      style={{ background: opt.color }}
                    />
                  )}
                  <span>{opt.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── FilterBar ────────────────────────────────────────────────────────────────

export function FilterBar({ selectedId, showDetailsPanel, onShowDetails }: FilterBarProps) {
  const { parts, filters, setFilters, clearFilters, getFilteredParts } = usePartsStore();

  const openArchivistPanel = () => {
    window.dispatchEvent(new CustomEvent('archivist:open'));
  };

  // Derive filter options dynamically from loaded parts (unique non-null values, sorted)
  const agrupacioOptions = useMemo(() => {
    const values = [...new Set(parts.map((p) => p.agrupacio).filter((v): v is string => v !== null))].sort();
    return values.map((v) => ({ value: v, label: v }));
  }, [parts]);

  const materialOptions = useMemo(() => {
    // Real stone material from the .3dm "Material" UserString (was wrongly
    // derived from tipologia). Null until geometry processing populates it.
    const values = [...new Set(
      parts.map((p) => p.material).filter((v): v is string => !!v)
    )].sort();
    return values.map((v) => ({ value: v, label: v }));
  }, [parts]);

  const filteredCount = getFilteredParts().length;
  const totalCount = parts.length;
  const hasFilters = filters.agrupacio.length > 0 || filters.material.length > 0;

  return (
    <div className={styles.bar} data-testid="filter-bar">
      {/* ── Filter pills ─────────────────────────── */}
      <FilterDropdown
        label="Agrupació"
        icon="⬡"
        options={agrupacioOptions}
        value={filters.agrupacio}
        onChange={(agrupacio) => setFilters({ agrupacio })}
      />

      <FilterDropdown
        label="Material"
        icon="◈"
        options={materialOptions}
        value={filters.material}
        onChange={(material) => setFilters({ material })}
      />

      {/* ── Counter ──────────────────────────────── */}
      <span
        className={`${styles.counter} ${hasFilters ? styles.counterHighlight : ''}`}
      >
        {hasFilters ? `${filteredCount} / ${totalCount}` : totalCount} piezas
      </span>

      {/* ── Clear button (only when filters active) */}
      {hasFilters && (
        <button className={styles.clearButton} onClick={clearFilters}>
          × Limpiar
        </button>
      )}

      {/* ── Upload button ────────────────────────── */}
      <span className={styles.divider} />
      <a href="/upload" className={styles.uploadButton} title="Subir nuevo archivo .3dm">
        + Subir
      </a>

      {/* ── Archivist button ───────────────────── */}
      <button
        className={styles.archivistButton}
        onClick={openArchivistPanel}
        title="Abrir El Archivista"
      >
        💬 Archivista
      </button>

      {/* ── Selection info (only when part selected and panel not open) ─────── */}
      {selectedId && !showDetailsPanel && (
        <>
          <span className={styles.divider} />
          <div className={styles.selectionInfo}>
            <span className={styles.selectionLabel}>Pieza seleccionada</span>

            <span className={styles.kbdHint}>
              <kbd className={styles.kbd}>F</kbd>
              <span>Zoom</span>
            </span>

            <button className={styles.detailsButton} onClick={onShowDetails}>
              Ver Detalles (D)
            </button>

            <span className={styles.kbdHint}>
              <kbd className={styles.kbd}>ESC</kbd>
              <span>Deseleccionar</span>
            </span>
          </div>
        </>
      )}
    </div>
  );
}
