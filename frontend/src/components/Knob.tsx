import { useRef } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'

// Recorrido del indicador: de las 7 a las 5, como un potenciometro de mesa
const ANGULO = 135
// Pixeles de arrastre para ir de un extremo al otro
const RECORRIDO_PX = 160

interface Props {
  label: string
  /** Posicion de -1 (todo a la izquierda) a 1, con 0 a las 12. */
  value: number
  /** Texto para lectores de pantalla y para el tooltip, p. ej. "-12 dB". */
  valueText: string
  color: string
  onChange: (valor: number) => void
}

function limitar(valor: number) {
  return Math.max(-1, Math.min(1, valor))
}

/** Potenciometro giratorio. Se mueve arrastrando arriba y abajo, que es lo
 *  que se hace con un raton sobre un boton redondo; doble clic lo devuelve al
 *  centro, como cuando se deja la banda plana. */
export function Knob({ label, value, valueText, color, onChange }: Props) {
  const arrastre = useRef<{ y: number; desde: number } | null>(null)

  function pulsar(e: PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    arrastre.current = { y: e.clientY, desde: value }
  }

  function mover(e: PointerEvent<HTMLDivElement>) {
    if (!arrastre.current) return
    const delta = (arrastre.current.y - e.clientY) / (RECORRIDO_PX / 2)
    let nuevo = limitar(arrastre.current.desde + delta)
    // Un pequeno iman en el centro: es la posicion a la que mas se vuelve
    if (Math.abs(nuevo) < 0.04) nuevo = 0
    onChange(nuevo)
  }

  function teclado(e: KeyboardEvent<HTMLDivElement>) {
    const pasos: Record<string, number> = { ArrowUp: 0.05, ArrowRight: 0.05, ArrowDown: -0.05, ArrowLeft: -0.05 }
    if (e.key in pasos) {
      e.preventDefault()
      onChange(limitar(value + pasos[e.key]))
    } else if (e.key === 'Home') {
      onChange(-1)
    } else if (e.key === 'End') {
      onChange(1)
    } else if (e.key === '0' || e.key === 'Delete') {
      onChange(0)
    }
  }

  const giro = value * ANGULO
  // Arco desde las 12 hasta la posicion, en el color de la banda
  const radio = 17
  const punto = (grados: number) => {
    const rad = ((grados - 90) * Math.PI) / 180
    return `${20 + radio * Math.cos(rad)} ${20 + radio * Math.sin(rad)}`
  }
  const arco =
    Math.abs(value) < 0.005
      ? null
      : `M ${punto(0)} A ${radio} ${radio} 0 0 ${giro > 0 ? 1 : 0} ${punto(giro)}`

  return (
    <div className="knob">
      <div
        className="knob__dial"
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={-1}
        aria-valuemax={1}
        aria-valuenow={Number(value.toFixed(2))}
        aria-valuetext={valueText}
        title={`${label}: ${valueText}. Arrastra arriba o abajo; doble clic para dejarlo plano.`}
        onPointerDown={pulsar}
        onPointerMove={mover}
        onPointerUp={() => (arrastre.current = null)}
        onPointerCancel={() => (arrastre.current = null)}
        onDoubleClick={() => onChange(0)}
        onKeyDown={teclado}
      >
        <svg viewBox="0 0 40 40" aria-hidden="true">
          <path
            d={`M ${punto(-ANGULO)} A ${radio} ${radio} 0 1 1 ${punto(ANGULO)}`}
            className="knob__track"
          />
          {arco && <path d={arco} stroke={color} className="knob__arc" />}
          <circle cx="20" cy="20" r="12" className="knob__cap" />
          <line
            x1="20"
            y1="20"
            x2="20"
            y2="10"
            stroke={color}
            className="knob__pointer"
            transform={`rotate(${giro} 20 20)`}
          />
        </svg>
      </div>
      <span className="knob__label">{label}</span>
    </div>
  )
}
