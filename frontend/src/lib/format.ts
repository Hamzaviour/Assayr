const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** "2026-02-04" or an ISO timestamp → "4 Feb 2026" (the calendar date as written, no timezone shift). */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}
