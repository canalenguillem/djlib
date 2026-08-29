type AlertKind = 'error' | 'success' | 'info'

interface AlertProps {
  kind?: AlertKind
  children: React.ReactNode
}

export function Alert({ kind = 'info', children }: AlertProps) {
  return (
    <div className={`alert alert--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
