import { useRef } from 'react'
import type { PointerEvent } from 'react'

// Un plato a 33 1/3 rpm da 0,555 vueltas por segundo: 200 grados
const GRADOS_POR_SEGUNDO = 200
// Arrastrando, cuanto frena o acelera el plato que suena
const EMPUJON = 0.1
// Si se deja de mover sin soltar, el plato vuelve a su velocidad
const QUIETO_MS = 120

interface Props {
  label: string
  position: number
  playing: boolean
  disabled: boolean
  /** Empujon mientras suena: 1 es soltarlo. */
  onNudge: (factor: number) => void
  /** Parado, girar el plato mueve la aguja como en un CDJ. */
  onSeek: (segundos: number) => void
}

/** La rueda del CDJ. Gira con la musica y se puede coger: sonando, girarla
 *  hacia delante empuja el plato y hacia atras lo frena, que es como se
 *  cuadran los golpes a mano; parado, mueve la aguja para buscar el punto de
 *  entrada. */
export function Jog({ label, position, playing, disabled, onNudge, onSeek }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const arrastre = useRef<{ angulo: number; posicion: number } | null>(null)
  const quieto = useRef<number | null>(null)

  function angulo(e: PointerEvent<HTMLDivElement>): number {
    const caja = ref.current!.getBoundingClientRect()
    return (Math.atan2(e.clientY - (caja.top + caja.height / 2), e.clientX - (caja.left + caja.width / 2)) * 180) / Math.PI
  }

  function pulsar(e: PointerEvent<HTMLDivElement>) {
    if (disabled || e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    arrastre.current = { angulo: angulo(e), posicion: position }
  }

  function mover(e: PointerEvent<HTMLDivElement>) {
    const previo = arrastre.current
    if (!previo) return
    const ahora = angulo(e)
    // El giro mas corto entre las dos lecturas, para no saltar al pasar por 180
    let giro = ahora - previo.angulo
    if (giro > 180) giro -= 360
    if (giro < -180) giro += 360
    if (Math.abs(giro) < 0.5) return
    previo.angulo = ahora
    if (playing) {
      onNudge(giro > 0 ? 1 + EMPUJON : 1 - EMPUJON)
      if (quieto.current !== null) window.clearTimeout(quieto.current)
      quieto.current = window.setTimeout(() => onNudge(1), QUIETO_MS)
    } else {
      previo.posicion = Math.max(0, previo.posicion + giro / GRADOS_POR_SEGUNDO)
      onSeek(previo.posicion)
    }
  }

  function soltar() {
    if (!arrastre.current) return
    arrastre.current = null
    if (quieto.current !== null) window.clearTimeout(quieto.current)
    quieto.current = null
    if (playing) onNudge(1)
  }

  const giro = (position * GRADOS_POR_SEGUNDO) % 360

  return (
    <div
      ref={ref}
      className={`jog${playing ? ' jog--on' : ''}${disabled ? ' jog--off' : ''}`}
      role="slider"
      aria-label={`Rueda del plato ${label}`}
      aria-valuenow={Math.round(position)}
      title={
        playing
          ? 'Gírala hacia delante para empujar el plato o hacia atrás para frenarlo'
          : 'Gírala para mover la aguja y buscar el punto de entrada'
      }
      onPointerDown={pulsar}
      onPointerMove={mover}
      onPointerUp={soltar}
      onPointerCancel={soltar}
    >
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="jog__borde" cx="50" cy="50" r="48" />
        <g transform={`rotate(${giro} 50 50)`}>
          <circle className="jog__vinilo" cx="50" cy="50" r="42" />
          {[0, 90, 180, 270].map((a) => (
            <rect key={a} className="jog__surco" x="49" y="10" width="2" height="12" transform={`rotate(${a + 45} 50 50)`} />
          ))}
          <line className="jog__marca" x1="50" y1="50" x2="50" y2="9" />
        </g>
        <circle className="jog__centro" cx="50" cy="50" r="13" />
        <text className="jog__letra" x="50" y="55" textAnchor="middle">
          {label}
        </text>
      </svg>
    </div>
  )
}
