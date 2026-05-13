/**
 * ProgressSteps Component - T-1807
 * 
 * Displays the 8-step StateGraph workflow progress with visual indicators.
 * Custom implementation (no external UI library dependencies).
 * 
 * Visual states:
 * - idle: Gray, waiting
 * - active: Blue, spinning indicator
 * - completed: Green, checkmark
 * - warning: Yellow, warning icon
 * - error: Red, error icon
 */

import type { ProgressStep, StepStatus } from '../types/upload';

interface ProgressStepsProps {
  /**
   * Array of 8 progress steps
   */
  steps: ProgressStep[];
  
  /**
   * Index of currently active step (0-7)
   */
  currentStep: number;
  
  /**
   * Optional className for custom styling
   */
  className?: string;
}

// ── Design Tokens ─────────────────────────────────────────────────────────────
const DS = {
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif',
  bgSurface: '#2C2C2E',
  bgCard: '#1C1C1E',
  borderSubtle: 'rgba(255, 255, 255, 0.08)',
  borderMid: 'rgba(255, 255, 255, 0.14)',
  textPrimary: 'rgba(255, 255, 255, 0.92)',
  textSecondary: 'rgba(255, 255, 255, 0.5)',
  textTertiary: 'rgba(255, 255, 255, 0.3)',
  blue: '#007AFF',
  green: '#34C759',
  yellow: '#FF9F0A',
  red: '#FF453A',
  gray: 'rgba(255, 255, 255, 0.2)',
} as const;

// ── Step Visual Config ────────────────────────────────────────────────────────
interface StepVisualConfig {
  color: string;
  bg: string;
  icon: string;
  spinning?: boolean;
}

const STEP_VISUALS: Record<StepStatus, StepVisualConfig> = {
  idle: {
    color: DS.textTertiary,
    bg: 'rgba(255, 255, 255, 0.06)',
    icon: '○',
  },
  active: {
    color: DS.blue,
    bg: 'rgba(0, 122, 255, 0.12)',
    icon: '◌',
    spinning: true,
  },
  completed: {
    color: DS.green,
    bg: 'rgba(52, 199, 89, 0.12)',
    icon: '✓',
  },
  warning: {
    color: DS.yellow,
    bg: 'rgba(255, 159, 10, 0.12)',
    icon: '⚠',
  },
  error: {
    color: DS.red,
    bg: 'rgba(255, 69, 58, 0.12)',
    icon: '✕',
  },
};

// ── Spinner Animation ─────────────────────────────────────────────────────────
const SPINNER_STYLE: React.CSSProperties = {
  display: 'inline-block',
  width: '12px',
  height: '12px',
  borderRadius: '50%',
  border: '2px solid currentColor',
  borderTopColor: 'transparent',
  animation: 'spin 0.8s linear infinite',
};

// ── Component ─────────────────────────────────────────────────────────────────

export function ProgressSteps({ steps, currentStep, className }: ProgressStepsProps) {
  return (
    <div className={className} style={{ fontFamily: DS.font }}>
      {/* Keyframes for spinner */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
      
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        {steps.map((step, index) => {
          const visual = STEP_VISUALS[step.status];
          const isCurrent = index === currentStep;
          
          return (
            <div
              key={step.nodeName}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                backgroundColor: isCurrent ? DS.bgCard : 'transparent',
                border: `1px solid ${isCurrent ? DS.borderMid : DS.borderSubtle}`,
                transition: 'all 0.2s ease',
              }}
            >
              {/* Step Number/Icon */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: visual.bg,
                  color: visual.color,
                  fontSize: '16px',
                  fontWeight: 600,
                  flexShrink: 0,
                  border: `1.5px solid ${visual.color}40`,
                }}
              >
                {visual.spinning ? (
                  <span style={SPINNER_STYLE} />
                ) : (
                  <span>{visual.icon}</span>
                )}
              </div>
              
              {/* Connector Line (vertical) */}
              {index < steps.length - 1 && (
                <div
                  style={{
                    position: 'absolute',
                    left: '27px',
                    top: '52px',
                    width: '2px',
                    height: '26px',
                    backgroundColor: step.status === 'completed' ? DS.green : DS.borderSubtle,
                    transition: 'background-color 0.3s ease',
                  }}
                />
              )}
              
              {/* Step Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {/* Step Label */}
                <div
                  style={{
                    fontSize: '14px',
                    fontWeight: 600,
                    color: isCurrent ? DS.textPrimary : DS.textSecondary,
                    marginBottom: '2px',
                  }}
                >
                  {step.label}
                </div>
                
                {/* Step Details */}
                {(step.errorMessage || step.status !== 'idle') && (
                  <div
                    style={{
                      fontSize: '12px',
                      color: DS.textTertiary,
                      lineHeight: 1.4,
                    }}
                  >
                    {step.errorMessage || getStatusDescription(step)}
                  </div>
                )}
              </div>
              
              {/* Timing Badge */}
              {step.completedAt && step.startedAt && (
                <div
                  style={{
                    fontSize: '11px',
                    color: DS.textTertiary,
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {formatDuration(step.startedAt, step.completedAt)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Helper Functions ──────────────────────────────────────────────────────────

function getStatusDescription(step: ProgressStep): string {
  switch (step.status) {
    case 'idle':
      return 'Esperando...';
    case 'active':
      return 'Procesando...';
    case 'completed':
      return 'Completado';
    case 'warning':
      return 'Completado con advertencias';
    case 'error':
      return 'Error';
    default:
      return '';
  }
}

function formatDuration(start: string, end: string): string {
  const durationMs = new Date(end).getTime() - new Date(start).getTime();
  const seconds = Math.round(durationMs / 1000);
  
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${seconds}s`;
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}
