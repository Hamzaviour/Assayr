const PATHS: Record<string, string> = {
  asset: "M4 8h16v11H4zM9 8V5h6v3M4 13h16",
  ai: "M7 7h10v10H7zM10 10h4v4h-4zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4",
  compliant:
    "M12 3l2.2 1.6 2.7-.2.9 2.6 2.3 1.5-.8 2.6.8 2.6-2.3 1.5-.9 2.6-2.7-.2L12 21l-2.2-1.6-2.7.2-.9-2.6-2.3-1.5.8-2.6-.8-2.6 2.3-1.5.9-2.6 2.7.2zM8.5 12l2.3 2.3 4.7-4.7",
  at_risk: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5V12l3 2",
  non_compliant: "M8 2.8h8L21.2 8v8L16 21.2H8L2.8 16V8zM9 9l6 6m0-6-6 6",
  in_review: "M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.4a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2z",
  in_progress: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 3.5v17",
  not_started: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
  excluded: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM8 12h8",
  server: "M4 4.5h16v6H4zM4 13.5h16v6H4zM8 7.5h.01M8 16.5h.01",
  shield: "M12 3.2 19.5 6v5.6c0 4.4-3.1 8.2-7.5 9.6-4.4-1.4-7.5-5.2-7.5-9.6V6zM8.6 12.2l2.4 2.4 4.4-4.6",
  offline: "M3 3l18 18M8.6 16.4a5 5 0 0 1 6.8 0M5.2 12.6a10 10 0 0 1 3.6-2.2M18.8 12.6a10 10 0 0 0-2-1.5M2 8.7a15 15 0 0 1 4.4-2.6M22 8.7A15 15 0 0 0 12.9 5M12 19.5h.01",
  home: "M3.5 11 12 4l8.5 7v8.5a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z",
  controls: "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17zM12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z",
  evidence: "M7 3.5h7l4 4V20.5H6.5V3.5zM14 3.5V8h4M9.5 13l2 2 3.5-3.5",
  soa: "M4 3.5h16v17H4zM8 8h8M8 12h8M8 16h5",
  policy: "M5 4.5h10l4 4v12H4v-16zM8 12h8M8 16h6",
  risk: "M3.5 3.5h7v7h-7zM13.5 3.5h7v7h-7zM3.5 13.5h7v7h-7zM13.5 13.5h7v7h-7z",
  audit: "M5 21V4h11l-2 4 2 4H5",
  training: "M3 8.5 12 4l9 4.5-9 4.5zM6.5 10.5V15c0 1.7 2.5 3 5.5 3s5.5-1.3 5.5-3v-4.5M21 8.5V14",
  privacy: "M12 3.2 19.5 6v5.6c0 4.4-3.1 8.2-7.5 9.6-4.4-1.4-7.5-5.2-7.5-9.6V6zM12 9.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM8.8 17c.6-1.6 1.8-2.4 3.2-2.4s2.6.8 3.2 2.4",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 4.3a3.5 3.5 0 0 1 0 6.4M18 14.4c2 .8 3.5 2.8 3.5 5.6",
  theme: "M12 3.5a8.5 8.5 0 1 0 0 17zM12 3.5a8.5 8.5 0 0 1 0 17",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  pass: "M5 12.5 9.5 17 19 7.5",
  warn: "M12 4 2.8 19.5h18.4zM12 10v4m0 3h.01",
  fail: "M6 6l12 12M18 6 6 18",
  skipped: "M5 12h14",
  upload: "M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
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
