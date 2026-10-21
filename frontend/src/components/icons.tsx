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

export function PrevIcon() {
  return (
    <svg {...base} fill="currentColor">
      <rect x="2.5" y="2.5" width="2" height="11" rx="0.8" />
      <path d="M13.5 2.9a.6.6 0 0 0-.93-.5L6 7.5a.6.6 0 0 0 0 1l6.57 5.1a.6.6 0 0 0 .93-.5V2.9Z" />
    </svg>
  )
}

export function NextIcon() {
  return (
    <svg {...base} fill="currentColor">
      <rect x="11.5" y="2.5" width="2" height="11" rx="0.8" />
      <path d="M2.5 2.9a.6.6 0 0 1 .93-.5L10 7.5a.6.6 0 0 1 0 1l-6.57 5.1a.6.6 0 0 1-.93-.5V2.9Z" />
    </svg>
  )
}

export function ShuffleIcon() {
  return (
    <svg {...base} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4.5h2.5c1.5 0 2.3.8 3 2l1 1.5c.7 1.2 1.5 2 3 2H14M2 11.5h2.5c1 0 1.7-.4 2.3-1.1M9.2 5.6c.6-.7 1.3-1.1 2.3-1.1H14" />
      <path d="M12 2.5l2 2-2 2M12 9.5l2 2-2 2" />
    </svg>
  )
}
