/**
 * FiltersSidebar Component
 * 
 * T-0506-FRONT: Filters sidebar orchestration
 * 
 * @module FiltersSidebar
 */

import CheckboxGroup from '../ui/CheckboxGroup';
import { usePartsStore } from '@/stores/parts.store';
import { TIPOLOGIA_OPTIONS, STATUS_OPTIONS } from '@/constants/parts.constants';

/**
 * Container styles for sidebar
 */
const SIDEBAR_CONTAINER_STYLES: React.CSSProperties = {
  padding: '20px',
  backgroundColor: '#1e293b',
  color: '#f1f5f9',
  height: '100%',
  boxSizing: 'border-box',
};

/**
 * Header container styles
 */
const HEADER_CONTAINER_STYLES: React.CSSProperties = {
  marginBottom: '16px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

/**
 * Heading styles
 */
const HEADING_STYLES: React.CSSProperties = {
  fontSize: '13px',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase' as const,
  color: '#94a3b8',
};

/**
 * Clear button styles
 */
const CLEAR_BUTTON_STYLES: React.CSSProperties = {
  padding: '3px 10px',
  fontSize: '12px',
  cursor: 'pointer',
  backgroundColor: 'transparent',
  color: '#64748b',
  border: '1px solid #334155',
  borderRadius: '4px',
};

/**
 * Results counter styles
 */
const COUNTER_STYLES: React.CSSProperties = {
  marginBottom: '20px',
  fontSize: '12px',
  color: '#475569',
  fontFamily: 'monospace',
};

/**
 * Filter section styles
 */
const SECTION_STYLES: React.CSSProperties = {
  marginBottom: '24px',
};

/**
 * Section heading styles
 */
const SECTION_HEADING_STYLES: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 600,
  letterSpacing: '0.1em',
  textTransform: 'uppercase' as const,
  color: '#64748b',
  marginBottom: '10px',
};

/**
 * Placeholder text styles
 */
const PLACEHOLDER_STYLES: React.CSSProperties = {
  fontSize: '12px',
  color: '#475569',
  fontStyle: 'italic',
};

/**
 * FiltersSidebar: Main filter orchestration component
 * 
 * Displays three filter sections:
 * - Tipología (CheckboxGroup)
 * - Estado (CheckboxGroup)
 * - Taller (future implementation)
 * 
 * Counter: Shows "Mostrando X de Y piezas"
 * Clear button: Resets all filters
 * 
 * @example
 * ```tsx
 * <FiltersSidebar />
 * ```
 */
export default function FiltersSidebar() {
  const { parts, filters, setFilters, clearFilters, getFilteredParts } = usePartsStore();
  
  const filteredParts = getFilteredParts();
  const totalCount = parts.length;
  const filteredCount = filteredParts.length;

  const handleTipologiaChange = (tipologia: string[]) => {
    setFilters({ tipologia });
  };

  const handleStatusChange = (status: string[]) => {
    setFilters({ status });
  };

  return (
    <div style={SIDEBAR_CONTAINER_STYLES}>
      <div style={HEADER_CONTAINER_STYLES}>
        <h2 style={HEADING_STYLES}>Filtros</h2>
        <button onClick={clearFilters} style={CLEAR_BUTTON_STYLES}>
          Limpiar filtros
        </button>
      </div>

      {/* Results counter */}
      <div style={COUNTER_STYLES}>
        Mostrando {filteredCount} de {totalCount}
      </div>

      {/* Tipología section */}
      <div style={SECTION_STYLES}>
        <h3 style={SECTION_HEADING_STYLES}>
          Tipología
        </h3>
        <CheckboxGroup
          options={TIPOLOGIA_OPTIONS}
          value={filters.tipologia || []}
          onChange={handleTipologiaChange}
          ariaLabel="Filtro de tipología"
        />
      </div>

      {/* Estado section */}
      <div style={SECTION_STYLES}>
        <h3 style={SECTION_HEADING_STYLES}>
          Estado
        </h3>
        <CheckboxGroup
          options={STATUS_OPTIONS}
          value={filters.status || []}
          onChange={handleStatusChange}
          ariaLabel="Filtro de estado"
        />
      </div>

      {/* Taller section (placeholder) */}
      <div style={SECTION_STYLES}>
        <h3 style={SECTION_HEADING_STYLES}>
          Taller
        </h3>
        <div style={PLACEHOLDER_STYLES}>
          (Próximamente)
        </div>
      </div>
    </div>
  );
}
