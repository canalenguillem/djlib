import { useEffect, useRef, useState } from 'react'

import * as tracksApi from '../api/tracks'
import { drawBands, prepareCanvas } from '../lib/waveform'
import type { Waveform as WaveformData } from '../types/api'

// La onda de una cancion no cambia: se pide una vez por sesion. Se guarda la
// promesa, no el resultado, para que dos filas iguales no la pidan dos veces.
const cache = new Map<number, Promise<WaveformData>>()

function load(trackId: number): Promise<WaveformData> {
  let pending = cache.get(trackId)
  if (!pending) {
    pending = tracksApi.fetchWaveform(trackId)
    // Si falla, que se pueda reintentar la proxima vez que se monte la fila
    pending.catch(() => cache.delete(trackId))
    cache.set(trackId, pending)
  }
  return pending
}

function draw(canvas: HTMLCanvasElement, data: WaveformData) {
  const lienzo = prepareCanvas(canvas)
  if (!lienzo) return
  const { ctx, width, height } = lienzo
  const perColumn = data.bins / width
  drawBands(ctx, data, width, height, (x) => {
    const start = Math.floor(x * perColumn)
    return [start, Math.max(start + 1, Math.floor((x + 1) * perColumn))]
  })
}

interface Props {
  trackId: number
}

/** Vista general de la cancion, como la franja superior de la pantalla de un
 *  CDJ: se ve donde estan los breaks, las subidas y cuando entra el bombo. */
export function Waveform({ trackId }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [data, setData] = useState<WaveformData | null>(null)
  const [failed, setFailed] = useState(false)

  // Solo se pide cuando la fila esta a punto de verse: una biblioteca larga no
  // tiene por que calcular de golpe la onda de canciones que nadie ha mirado.
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let cancelled = false
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        observer.disconnect()
        load(trackId)
          .then((result) => {
            if (!cancelled) setData(result)
          })
          .catch(() => {
            if (!cancelled) setFailed(true)
          })
      },
      { rootMargin: '200px' },
    )
    observer.observe(canvas)
    return () => {
      cancelled = true
      observer.disconnect()
    }
  }, [trackId])

  // Se repinta al cambiar el ancho, para que la onda nunca salga estirada
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !data) return
    draw(canvas, data)
    const observer = new ResizeObserver(() => draw(canvas, data))
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [data])

  if (failed) return null

  return (
    <canvas
      ref={canvasRef}
      className={data ? 'waveform' : 'waveform waveform--loading'}
      role="img"
      aria-label="Forma de onda de la cancion"
    />
  )
}
