import { useEffect, useRef } from 'react'
import type { KeyboardEvent, MouseEvent } from 'react'

import { drawBands, prepareCanvas } from '../lib/waveform'
import type { DeckWaveformData } from '../lib/waveform'
import { BEATS_PER_BAR, beatPosition, modulo } from '../lib/beatgrid'
import type { BeatGrid } from '../lib/beatgrid'

/** Segundos de reloj que caben en la onda de detalle, como el zoom por
 *  defecto de un CDJ: suficiente para ver venir el siguiente break. */
const DETAIL_SECONDS = 8
// La aguja en blanco, como en el CDJ-3000: el rojo queda para los compases
const PLAYHEAD = '#ffffff'
const CUE = '#8474ff'
// El cue principal va en naranja, como el del CDJ; los de los pads, en morado
const MAIN_CUE = '#ff9f0a'
// Rejilla: cada golpe en blanco tenue y el primero de cada compas en rojo
const BEAT = 'rgba(255, 255, 255, 0.45)'
const BAR = '#ff3b30'

export interface DetailOptions {
  data: DeckWaveformData | null
  position: number
  /** Velocidad del plato: la onda pasa a la velocidad a la que suena, asi la
   *  rejilla de dos platos igualados queda con la misma separacion. */
  tempo: number
  cues: Array<number | null>
  mainCue: number
  grid: BeatGrid | null
}

/** La onda de detalle: 8 segundos de reloj alrededor de una aguja fija. */
export function drawDetail(canvas: HTMLCanvasElement, opciones: DetailOptions) {
  const lienzo = prepareCanvas(canvas)
  if (!lienzo) return
  const { ctx, width, height } = lienzo
  const { data, position, cues, grid } = opciones
  const centro = width / 2
  // Segundos del tema, no del reloj: con el tempo subido caben mas
  const ventana = DETAIL_SECONDS * opciones.tempo
  const segundosPorPixel = ventana / width
  const ratio = window.devicePixelRatio || 1
  const xDe = (segundos: number) => Math.round(centro + (segundos - position) / segundosPorPixel)

  if (data) {
    // La aguja esta quieta en el centro y la cancion pasa por debajo
    const tramosPorPixel = segundosPorPixel * data.rate
    const primero = (position - ventana / 2) * data.rate
    drawBands(ctx, data, width, height, (x) => {
      const start = Math.floor(primero + x * tramosPorPixel)
      return [start, Math.max(start + 1, Math.floor(primero + (x + 1) * tramosPorPixel))]
    })
  }

  if (grid) {
    const periodo = 60 / grid.bpm
    const desde = Math.ceil(beatPosition(grid, position - ventana / 2))
    const hasta = Math.floor(beatPosition(grid, position + ventana / 2))
    for (let golpe = desde; golpe <= hasta; golpe++) {
      const x = xDe(grid.first + golpe * periodo)
      if (modulo(golpe, BEATS_PER_BAR) === 0) {
        ctx.fillStyle = BAR
        ctx.fillRect(x - ratio, 0, 2 * ratio, height)
      } else {
        // Los demas tiempos, solo arriba y abajo para no tapar la onda
        ctx.fillStyle = BEAT
        ctx.fillRect(x, 0, Math.max(1, ratio), height * 0.22)
        ctx.fillRect(x, height * 0.78, Math.max(1, ratio), height * 0.22)
      }
    }
  }

  // Los cues que quedan a la vista, con su numero, como los hot cues del CDJ
  ctx.font = `bold ${10 * ratio}px system-ui, sans-serif`
  cues.forEach((cue, indice) => {
    if (cue === null) return
    const x = xDe(cue)
    if (x < 0 || x > width) return
    ctx.fillStyle = CUE
    ctx.fillRect(x, 0, Math.max(1, ratio), height)
    ctx.fillRect(x, 0, 12 * ratio, 13 * ratio)
    ctx.fillStyle = '#fff'
    ctx.fillText(String(indice + 1), x + 3 * ratio, 10.5 * ratio)
  })

  // El cue principal: una linea con un triangulo arriba y otro abajo
  const xCue = xDe(opciones.mainCue)
  if (xCue >= 0 && xCue <= width) {
    ctx.fillStyle = MAIN_CUE
    ctx.fillRect(xCue, 0, Math.max(1, ratio), height)
    triangulo(ctx, xCue, 0, 5 * ratio)
    triangulo(ctx, xCue, height, -5 * ratio)
  }

  ctx.fillStyle = PLAYHEAD
  ctx.fillRect(Math.round(centro - ratio), 0, 2 * ratio, height)
  triangulo(ctx, Math.round(centro), 0, 6 * ratio)
  triangulo(ctx, Math.round(centro), height, -6 * ratio)
}

interface Props extends DetailOptions {
  /** Mientras se calcula la onda, recien cargada la cancion. */
  analyzing: boolean
  duration: number
  onSeek: (segundos: number) => void
}

/** Triangulo con la punta hacia dentro de la onda; `alto` negativo, abajo. */
function triangulo(ctx: CanvasRenderingContext2D, x: number, y: number, alto: number) {
  ctx.beginPath()
  ctx.moveTo(x - Math.abs(alto), y)
  ctx.lineTo(x + Math.abs(alto), y)
  ctx.lineTo(x, y + alto)
  ctx.fill()
}

function drawOverview(canvas: HTMLCanvasElement, props: Props) {
  const lienzo = prepareCanvas(canvas)
  if (!lienzo) return
  const { ctx, width, height } = lienzo
  const { data, position, duration, cues } = props
  const ratio = window.devicePixelRatio || 1

  if (data) {
    const tramosPorPixel = data.low.length / width
    drawBands(ctx, data, width, height, (x) => {
      const start = Math.floor(x * tramosPorPixel)
      return [start, Math.max(start + 1, Math.floor((x + 1) * tramosPorPixel))]
    })
  }
  if (!duration) return

  // Lo que ya ha sonado, oscurecido, como en la vista general del CDJ
  const aguja = Math.round((position / duration) * width)
  ctx.fillStyle = 'rgba(0, 0, 0, 0.55)'
  ctx.fillRect(0, 0, aguja, height)

  // Triangulos en el borde, para no tapar la onda: los de los pads arriba y
  // el principal abajo
  ctx.fillStyle = CUE
  for (const cue of cues) {
    if (cue !== null) triangulo(ctx, Math.round((cue / duration) * width), 0, 6 * ratio)
  }
  ctx.fillStyle = MAIN_CUE
  triangulo(ctx, Math.round((props.mainCue / duration) * width), height, -6 * ratio)

  ctx.fillStyle = PLAYHEAD
  ctx.fillRect(Math.max(0, aguja - ratio), 0, 2 * ratio, height)
}

/** Las dos ondas de la pantalla de un CDJ: la de detalle, que pasa bajo una
 *  aguja fija, y la vista general de la cancion entera, que sirve tambien
 *  para saltar a cualquier punto. */
export function DeckWaveform(props: Props) {
  const detailRef = useRef<HTMLCanvasElement>(null)
  const overviewRef = useRef<HTMLCanvasElement>(null)
  const { data, analyzing, position, duration, onSeek } = props

  // La mesa ya se repinta a cada fotograma para mover el reloj: las ondas
  // simplemente se redibujan con la posicion nueva.
  useEffect(() => {
    if (detailRef.current) drawDetail(detailRef.current, props)
    if (overviewRef.current) drawOverview(overviewRef.current, props)
  })

  function saltar(e: MouseEvent<HTMLCanvasElement>) {
    if (!duration) return
    const caja = e.currentTarget.getBoundingClientRect()
    onSeek(((e.clientX - caja.left) / caja.width) * duration)
  }

  function teclado(e: KeyboardEvent<HTMLCanvasElement>) {
    if (!duration) return
    const paso = e.key === 'ArrowRight' ? 5 : e.key === 'ArrowLeft' ? -5 : 0
    if (!paso) return
    e.preventDefault()
    onSeek(position + paso)
  }

  const cargando = analyzing && !data ? ' deckwave--loading' : ''

  return (
    <div className="deckwave">
      <canvas
        ref={detailRef}
        className={`deckwave__detail${cargando}`}
        role="img"
        aria-label="Onda de detalle alrededor del punto que suena"
      />
      <canvas
        ref={overviewRef}
        className={`deckwave__overview${cargando}`}
        role="slider"
        tabIndex={0}
        aria-label="Posicion"
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(position)}
        onClick={saltar}
        onKeyDown={teclado}
      />
    </div>
  )
}
