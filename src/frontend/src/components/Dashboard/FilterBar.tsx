/**
 * FilterBar Component
 *
 * Persistent bottom bar combining filter controls and selection hints.
 * Replaces the draggable sidebar + conditional hint bar.
 *
 * Layout (left → right):
 *   [Tipología ▾] [Estado ▾]  X/Y piezas  [× Limpiar]  |  <selection info when part selected>
 *
 * @module FilterBar
 */

import { useState, useRef, useEffect } from 'react';
import { usePartsStore } from '@/stores/parts.store';
import { TIPOLOGIA_OPTIONS, STATUS_OPTIONS } from '@/constants/parts.constants';
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

  const filteredCount = getFilteredParts().length;
  const totalCount = parts.length;
  const hasFilters = filters.tipologia.length > 0 || filters.status.length > 0;

  return (
    <div className={styles.bar} data-testid="filter-bar">
      {/* ── Filter pills ─────────────────────────── */}
      <FilterDropdown
        label="Tipología"
        icon="⬡"
        options={TIPOLOGIA_OPTIONS}
        value={filters.tipologia}
        onChange={(tipologia) => setFilters({ tipologia })}
      />

      <FilterDropdown
        label="Estado"
        icon="●"
        options={STATUS_OPTIONS}
        value={filters.status}
        onChange={(status) => setFilters({ status })}
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
