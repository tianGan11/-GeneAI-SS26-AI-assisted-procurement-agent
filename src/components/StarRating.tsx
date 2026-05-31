import { useState } from 'react'

export function StarRating({
  value,
  onChange,
  readOnly = false,
  size = 'md',
}: {
  value: number
  onChange?: (value: number) => void
  readOnly?: boolean
  size?: 'sm' | 'md'
}) {
  const [hover, setHover] = useState(0)
  const display = hover || value
  const px = size === 'sm' ? 'text-base' : 'text-2xl'

  return (
    <div className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={readOnly}
          onClick={() => onChange?.(star)}
          onMouseEnter={() => !readOnly && setHover(star)}
          onMouseLeave={() => !readOnly && setHover(0)}
          className={`${px} leading-none transition-colors ${
            readOnly ? 'cursor-default' : 'cursor-pointer'
          } ${star <= display ? 'text-amber-400' : 'text-slate-300'}`}
          aria-label={`${star} star`}
        >
          ★
        </button>
      ))}
    </div>
  )
}
