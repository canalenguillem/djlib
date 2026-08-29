/** Iconos en SVG en lugar de caracteres tipo "▶" o "✕": esos dependen de las
 *  fuentes instaladas y en algunos sistemas se ven como un recuadro vacio. */

const base = {
  viewBox: '0 0 16 16',
  width: 14,
  height: 14,
  'aria-hidden': true,
  focusable: false,
} as const

export function PlayIcon() {
  return (
    <svg {...base} fill="currentColor">
      <path d="M4.5 2.6a.6.6 0 0 1 .92-.5l7 5.4a.6.6 0 0 1 0 1l-7 5.4a.6.6 0 0 1-.92-.5V2.6Z" />
    </svg>
  )
}

export function PauseIcon() {
  return (
    <svg {...base} fill="currentColor">
      <rect x="3.5" y="2.5" width="3.2" height="11" rx="1" />
      <rect x="9.3" y="2.5" width="3.2" height="11" rx="1" />
    </svg>
  )
}

export function CloseIcon() {
  return (
    <svg {...base} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
    </svg>
  )
}
