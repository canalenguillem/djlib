export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  const minutes = Math.floor(seconds / 60)
  const rest = Math.floor(seconds % 60)
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

export function formatSize(bytes: number | null): string {
  if (!bytes) return '—'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value}Z`).toLocaleString('es-ES')
}
