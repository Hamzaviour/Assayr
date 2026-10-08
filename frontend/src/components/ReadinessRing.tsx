export function ReadinessRing({ value }: { value: number }) {
  const radius = 46
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - Math.min(Math.max(value, 0), 100) / 100)
  return (
    <svg width="108" height="108" viewBox="0 0 108 108" role="img" aria-label={`Readiness ${Math.round(value)} percent`}>
      <circle cx="54" cy="54" r={radius} fill="none" stroke="var(--subtle)" strokeWidth="10" />
      <circle cx="54" cy="54" r={radius} fill="none" stroke="var(--primary)" strokeWidth="10" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset} transform="rotate(-90 54 54)" />
      <text x="54" y="60" textAnchor="middle" fill="var(--text)"
        style={{ font: "800 24px var(--f-display)" }}>{Math.round(value)}%</text>
    </svg>
  )
}
