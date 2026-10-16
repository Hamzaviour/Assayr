import type { BarSegment } from "../components/StatusBar"
import { STATUSES, type StatusArea, type Tone } from "../components/Status"

export function countBy<T>(rows: T[], key: (row: T) => string): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const row of rows) counts[key(row)] = (counts[key(row)] ?? 0) + 1
  return counts
}

/** Segments for every status of an area, in the area's own order, with their shared tones. */
export function statusSegments(area: StatusArea, counts: Record<string, number>): BarSegment[] {
  const table = STATUSES[area] as Record<string, [Tone, string]>
  return Object.entries(table).map(([key, [tone, label]]) => ({ key, label, tone, value: counts[key] ?? 0 }))
}
