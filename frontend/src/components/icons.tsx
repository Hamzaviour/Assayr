const PATHS: Record<string, string> = {
  compliant:
    "M12 3l2.2 1.6 2.7-.2.9 2.6 2.3 1.5-.8 2.6.8 2.6-2.3 1.5-.9 2.6-2.7-.2L12 21l-2.2-1.6-2.7.2-.9-2.6-2.3-1.5.8-2.6-.8-2.6 2.3-1.5.9-2.6 2.7.2zM8.5 12l2.3 2.3 4.7-4.7",
  at_risk: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5V12l3 2",
  non_compliant: "M8 2.8h8L21.2 8v8L16 21.2H8L2.8 16V8zM9 9l6 6m0-6-6 6",
  in_review: "M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.4a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2z",
  in_progress: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 3.5v17",
  not_started: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
  excluded: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8 12h8",
  home: "M3.5 11 12 4l8.5 7v8.5a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z",
  controls: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z",
  evidence: "M7 3.5h7l4 4V20.5H6.5V3.5zM14 3.5V8h4M9.5 13l2 2 3.5-3.5",
  soa: "M4 3.5h16v17H4zM8 8h8M8 12h8M8 16h5",
  policy: "M5 4.5h10l4 4v12H4v-16zM8 12h8M8 16h6",
  risk: "M3.5 3.5h7v7h-7zM13.5 3.5h7v7h-7zM3.5 13.5h7v7h-7zM13.5 13.5h7v7h-7z",
  audit: "M5 21V4h11l-2 4 2 4H5",
  theme: "M12 3.5a8.5 8.5 0 1 0 0 17zM12 3.5a8.5 8.5 0 0 1 0 17",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
}

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path d={PATHS[name] ?? PATHS.not_started} />
    </svg>
  )
}
