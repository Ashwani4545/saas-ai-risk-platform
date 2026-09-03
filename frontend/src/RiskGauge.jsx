const SIZE = 168
const STROKE = 12
const RADIUS = (SIZE - STROKE) / 2
const CIRC = 2 * Math.PI * RADIUS
const ARC_FRACTION = 0.75 // ~270deg sweep, like a physical gauge

function bandFor(score) {
  if (score >= 0.66) return { color: 'var(--risk-high)', label: 'High' }
  if (score >= 0.33) return { color: 'var(--risk-mid)', label: 'Medium' }
  return { color: 'var(--risk-low)', label: 'Low' }
}

export default function RiskGauge({ score = null, loading = false }) {
  const clamped = score === null ? 0 : Math.max(0, Math.min(1, score))
  const band = score === null ? { color: 'var(--panel-border)', label: '—' } : bandFor(clamped)

  const sweep = CIRC * ARC_FRACTION
  const filled = sweep * clamped
  const rotateStart = 135 // start angle so the gap sits at the bottom

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--panel-border)"
          strokeWidth={STROKE}
          strokeDasharray={`${sweep} ${CIRC}`}
          strokeLinecap="round"
          transform={`rotate(${rotateStart} ${SIZE / 2} ${SIZE / 2})`}
        />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={band.color}
          strokeWidth={STROKE}
          strokeDasharray={`${filled} ${CIRC}`}
          strokeLinecap="round"
          transform={`rotate(${rotateStart} ${SIZE / 2} ${SIZE / 2})`}
          style={{ transition: 'stroke-dasharray 0.6s cubic-bezier(0.22, 1, 0.36, 1), stroke 0.3s ease' }}
        />
        <text
          x="50%"
          y="46%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="var(--font-mono)"
          fontSize="30"
          fontWeight="600"
          fill="var(--text-primary)"
        >
          {loading ? '···' : score === null ? '—' : clamped.toFixed(2)}
        </text>
        <text
          x="50%"
          y="64%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="var(--font-display)"
          fontSize="11"
          letterSpacing="0.08em"
          fill="var(--text-muted)"
        >
          RISK SCORE
        </text>
      </svg>
      <span
        className="pill"
        style={{ background: `color-mix(in srgb, ${band.color} 16%, transparent)`, color: band.color }}
      >
        {band.label} risk
      </span>
    </div>
  )
}
