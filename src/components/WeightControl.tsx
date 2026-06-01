import { useEffect, useRef } from 'react'
import type { FactorWeights } from '../types'
import type { Translation } from '../i18n'

type FactorKey = keyof FactorWeights

const COLORS: Record<FactorKey, string> = {
  price: '#2563eb', // blue
  delivery: '#f59e0b', // amber
  rating: '#10b981', // emerald
}

// Order of segments clockwise from the top of the wheel.
const ORDER: FactorKey[] = ['price', 'delivery', 'rating']
const MIN = 0.03 // smallest allowed slice (3%) so a segment never vanishes

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

// A point on the circle at fraction `frac` (0 = top, clockwise) and `radius`.
function pointAt(cx: number, cy: number, frac: number, radius: number) {
  const theta = frac * 2 * Math.PI
  return { x: cx + radius * Math.sin(theta), y: cy - radius * Math.cos(theta) }
}

// SVG path for a donut segment between two fractions.
function segmentPath(cx: number, cy: number, from: number, to: number, R: number, r: number) {
  const large = to - from > 0.5 ? 1 : 0
  const o1 = pointAt(cx, cy, from, R)
  const o2 = pointAt(cx, cy, to, R)
  const i2 = pointAt(cx, cy, to, r)
  const i1 = pointAt(cx, cy, from, r)
  return [
    `M ${o1.x} ${o1.y}`,
    `A ${R} ${R} 0 ${large} 1 ${o2.x} ${o2.y}`,
    `L ${i2.x} ${i2.y}`,
    `A ${r} ${r} 0 ${large} 0 ${i1.x} ${i1.y}`,
    'Z',
  ].join(' ')
}

export function WeightControl({
  weights,
  onChange,
  t,
}: {
  weights: FactorWeights
  onChange: (w: FactorWeights) => void
  t: Translation
}) {
  const c = t.comparison
  const svgRef = useRef<SVGSVGElement>(null)
  const draggingRef = useRef<0 | 1 | null>(null)

  const labels: Record<FactorKey, string> = {
    price: c.weightPrice,
    delivery: c.weightDelivery,
    rating: c.weightRating,
  }

  const size = 180
  const cx = size / 2
  const cy = size / 2
  const R = 80
  const r = 48
  const handleR = (R + r) / 2

  // Cumulative boundaries (fractions) following ORDER.
  const cum1 = weights.price / 100 // price | delivery
  const cum2 = (weights.price + weights.delivery) / 100 // delivery | rating

  // --- Donut drag: each handle redistributes its two adjacent segments. ---
  useEffect(() => {
    const fracFromEvent = (e: PointerEvent): number => {
      const rect = svgRef.current?.getBoundingClientRect()
      if (!rect) return 0
      const dx = e.clientX - (rect.left + rect.width / 2)
      const dy = e.clientY - (rect.top + rect.height / 2)
      const deg = (Math.atan2(dy, dx) * 180) / Math.PI + 90
      return (((deg % 360) + 360) % 360) / 360
    }

    const onMove = (e: PointerEvent) => {
      if (draggingRef.current === null) return
      const f = fracFromEvent(e)
      if (draggingRef.current === 0) {
        // boundary price|delivery — keep cum2 (and rating) fixed
        const nf = clamp(f, MIN, cum2 - MIN)
        const price = Math.round(nf * 100)
        const delivery = weights.price + weights.delivery - price
        onChange({ price, delivery, rating: weights.rating })
      } else {
        // boundary delivery|rating — keep price (cum1) fixed
        const nf = clamp(f, cum1 + MIN, 1 - MIN)
        const c2 = Math.round(nf * 100)
        onChange({ price: weights.price, delivery: c2 - weights.price, rating: 100 - c2 })
      }
    }
    const onUp = () => {
      draggingRef.current = null
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [weights, cum1, cum2, onChange])

  // --- Slider: set one factor, rescale the other two to keep the sum at 100. ---
  const setWeight = (key: FactorKey, raw: number) => {
    const value = clamp(Math.round(raw), 0, 100)
    const others = ORDER.filter((k) => k !== key)
    const otherSum = weights[others[0]] + weights[others[1]]
    const remaining = 100 - value
    const next: FactorWeights = { ...weights, [key]: value }
    if (otherSum === 0) {
      next[others[0]] = Math.floor(remaining / 2)
      next[others[1]] = remaining - next[others[0]]
    } else {
      next[others[0]] = Math.round((weights[others[0]] / otherSum) * remaining)
      next[others[1]] = remaining - next[others[0]]
    }
    onChange(next)
  }

  const handle1 = pointAt(cx, cy, cum1, handleR)
  const handle2 = pointAt(cx, cy, cum2, handleR)

  const segments: { key: FactorKey; from: number; to: number }[] = [
    { key: 'price', from: 0, to: cum1 },
    { key: 'delivery', from: cum1, to: cum2 },
    { key: 'rating', from: cum2, to: 1 },
  ]

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:gap-6">
      {/* Donut */}
      <svg
        ref={svgRef}
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="shrink-0 touch-none select-none"
      >
        {segments.map((seg) =>
          seg.to - seg.from < 0.0005 ? null : (
            <path key={seg.key} d={segmentPath(cx, cy, seg.from, seg.to, R, r)} fill={COLORS[seg.key]} />
          ),
        )}
        {/* draggable handles */}
        {[
          { idx: 0 as const, p: handle1 },
          { idx: 1 as const, p: handle2 },
        ].map(({ idx, p }) => (
          <circle
            key={idx}
            cx={p.x}
            cy={p.y}
            r={9}
            fill="#fff"
            stroke="#0f172a"
            strokeWidth={2}
            className="cursor-grab"
            style={{ cursor: 'grab' }}
            onPointerDown={(e) => {
              e.preventDefault()
              draggingRef.current = idx
            }}
          />
        ))}
      </svg>

      {/* Legend + sliders */}
      <div className="w-full max-w-xs space-y-3">
        {ORDER.map((key) => (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-slate-600">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[key] }} />
                {labels[key]}
              </span>
              <span className="font-semibold tabular-nums text-slate-900">{weights[key]}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={weights[key]}
              onChange={(e) => setWeight(key, Number(e.target.value))}
              aria-label={labels[key]}
              className="w-full cursor-pointer accent-blue-600"
              style={{ accentColor: COLORS[key] }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
