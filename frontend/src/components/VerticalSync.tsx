import { useEffect, useRef } from 'react'

import { BEATS_PER_BAR, beatPosition, modulo } from '../lib/beatgrid'
import { drawDetail } from './DeckWaveform'
import type { SyncDeck } from './SyncView'

// Por debajo de esto ya no se oye el desfase entre los bombos
const EN_FASE_MS = 15

function enCompas(deck: SyncDeck) {
  if (!deck.grid) return null
  const golpe = beatPosition(deck.grid, deck.position)
  return { tiempo: Math.floor(modulo(golpe, BEATS_PER_BAR)), golpe }
}

/** Las dos ondas de detalle en vertical, una al lado de la otra, en el centro
 *  de la mesa como en Serato o rekordbox en vertical: lo que va a sonar viene
 *  de arriba y la linea roja es lo que suena. Si los platos van a la par, las
 *  lineas de la rejilla de las dos cruzan la roja a la vez. Debajo, el
 *  medidor de fase y un aviso de cuanto se van. */
export function VerticalSync({ decks }: { decks: [SyncDeck, SyncDeck] }) {
  const refs = [useRef<HTMLCanvasElement>(null), useRef<HTMLCanvasElement>(null)]

  useEffect(() => {
    decks.forEach((deck, i) => {
      const canvas = refs[i].current
      if (canvas) drawDetail(canvas, deck)
    })
  })

  const [a, b] = decks
  const compas = [enCompas(a), enCompas(b)]

  let aviso: { texto: string; bien: boolean } | null = null
  if (compas[0] && compas[1] && a.grid && b.grid) {
    const tiempos = modulo(compas[1].golpe - compas[0].golpe + 2, BEATS_PER_BAR) - 2
    const enteros = Math.round(tiempos)
    const ms = ((tiempos - enteros) * 60 * 1000) / (a.grid.bpm * a.tempo)
    const bpmA = a.grid.bpm * a.tempo
    const bpmB = b.grid.bpm * b.tempo
    if (Math.abs(bpmA - bpmB) >= 0.05) {
      aviso = { texto: `B ${bpmB > bpmA ? '+' : '−'}${Math.abs(bpmB - bpmA).toFixed(2)} BPM`, bien: false }
    } else if (Math.abs(ms) >= EN_FASE_MS) {
      aviso = { texto: `B ${ms > 0 ? 'adelantado' : 'retrasado'} ${Math.abs(Math.round(ms))} ms`, bien: false }
    } else if (enteros !== 0) {
      aviso = { texto: `B ${Math.abs(enteros)} ${Math.abs(enteros) === 1 ? 'tiempo' : 'tiempos'} ${enteros > 0 ? 'por delante' : 'por detrás'}`, bien: false }
    } else {
      aviso = { texto: 'En fase', bien: true }
    }
  }

  return (
    <div className="vsync" aria-label="Comparar los dos platos">
      <div className="vsync__ondas">
        {decks.map((deck, i) => (
          <div key={deck.label} className="vsync__carril">
            <canvas
              ref={refs[i]}
              className="vsync__onda"
              role="img"
              aria-label={`Onda de detalle del plato ${deck.label}`}
            />
          </div>
        ))}
        <span className="vsync__aguja" aria-hidden="true" />
      </div>
      <div className="vsync__fases">
        {decks.map((deck, i) => (
          <div key={deck.label} className="phase phase--mini" aria-label={`Tiempo del compás del plato ${deck.label}`}>
            {Array.from({ length: BEATS_PER_BAR }, (_, t) => (
              <span
                key={t}
                className={`phase__beat${compas[i]?.tiempo === t ? (t === 0 ? ' phase__beat--one' : ' phase__beat--on') : ''}`}
              >
                {t + 1}
              </span>
            ))}
          </div>
        ))}
      </div>
      <p className={`vsync__estado${aviso?.bien ? ' vsync__estado--ok' : ''}`}>
        {aviso ? aviso.texto : a.loaded && b.loaded ? 'Calculando...' : 'Carga los dos platos'}
      </p>
    </div>
  )
}
