import { useEffect, useState } from "react"

function prefersMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && !window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

/** A number that counts up to its value once; shows the value at once when motion is reduced or unavailable. */
export function CountUp({ value, suffix = "", duration = 900 }: { value: number; suffix?: string; duration?: number }) {
  const [shown, setShown] = useState(() => (prefersMotion() ? 0 : value))
  useEffect(() => {
    if (!prefersMotion()) {
      setShown(value)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      setShown(Math.round(value * (1 - (1 - t) ** 4)))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])
  return (
    <span className="tabular-nums">
      {shown}
      {suffix}
    </span>
  )
}
