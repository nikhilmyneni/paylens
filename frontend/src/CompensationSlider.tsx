import { useId } from 'react'
import type { CSSProperties } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  currentAnnual: number
  expectedAnnual?: number | null
  currency: string
}

export function CompensationSlider({ value, onChange, currentAnnual, expectedAnnual, currency }: Props) {
  const id = useId()
  const format = (amount: number, decimals = 0) => new Intl.NumberFormat('en-IN', {
    style: 'currency', currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(amount)
  const anchor = Math.max(currentAnnual, expectedAnnual ?? 0, 1)
  const unit = anchor >= 10000 ? 1000 : 100
  const minimum = Math.max(1, Math.floor(currentAnnual * .5 / unit) * unit)
  const maximum = Math.max(minimum + unit, Math.ceil(anchor * 1.5 / unit) * unit)
  const amount = Number(value)
  const valid = value.trim() !== '' && Number.isFinite(amount) && amount > 0
  const sliderAmount = Math.min(maximum, Math.max(minimum, valid ? amount : minimum))
  const position = (sliderAmount - minimum) / (maximum - minimum) * 100
  const outside = valid && (amount < minimum || amount > maximum)
  const delta = valid && currentAnnual > 0 ? (amount - currentAnnual) / currentAnnual * 100 : null
  const expectedPosition = expectedAnnual == null ? null : Math.min(100, Math.max(0, (expectedAnnual - minimum) / (maximum - minimum) * 100))

  return <fieldset className="compensation-picker">
    <legend>Proposed annual pay ({currency})</legend>
    <div className="compensation-picker-heading">
      <output htmlFor={`${id}-range ${id}-exact`} className="compensation-picker-amount">
        {valid ? format(amount, amount % 1 ? 2 : 0) : 'Enter an amount'}
      </output>
      <span className="compensation-picker-delta">{delta == null ? 'Annual full-time equivalent' : `${delta > 0 ? '+' : ''}${delta.toFixed(1)}% from current pay`}</span>
    </div>
    <div className="compensation-range-shell" style={{ '--range-progress': `${position}%` } as CSSProperties}>
      <input id={`${id}-range`} className="compensation-range" type="range"
        aria-label="Adjust proposed annual pay" aria-valuetext={`${format(sliderAmount)} annual full-time equivalent`}
        aria-describedby={`${id}-help`} min={minimum} max={maximum} step="0.01" value={sliderAmount}
        onChange={event => onChange(event.target.value)} />
      {expectedPosition != null && <span className="compensation-range-marker" aria-hidden="true" style={{ left: `${expectedPosition}%` }} />}
    </div>
    <div className="compensation-range-limits" aria-hidden="true"><span>{format(minimum)}</span><span>{format(maximum)}</span></div>
    <p className="compensation-range-help" id={`${id}-help`}>Drag to adjust, or enter an exact amount. This range is a selection aid, not the compensation band.</p>
    <div className="compensation-reference-row">
      <div><span>Current pay</span><strong>{format(currentAnnual)}</strong></div>
      {expectedAnnual != null && <button type="button" className="compensation-expected" onClick={() => onChange(String(expectedAnnual))}>
        <span>Use expected pay</span><strong>{format(expectedAnnual)}</strong>
      </button>}
    </div>
    <label className="compensation-exact" htmlFor={`${id}-exact`}>Exact annual amount ({currency})
      <input id={`${id}-exact`} type="number" required min="0.01" step="0.01" inputMode="decimal"
        value={value} onChange={event => onChange(event.target.value)} />
    </label>
    {outside && <p className="compensation-range-help">Your exact amount is outside the slider range. The entered amount will be saved.</p>}
  </fieldset>
}
