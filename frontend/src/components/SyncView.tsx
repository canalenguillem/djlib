import { useEffect, useRef } from 'react'

import { BEATS_PER_BAR, beatPosition, modulo } from '../lib/beatgrid'
import { drawDetail } from './DeckWaveform'
import type { DetailOptions } from './DeckWaveform'

export interface SyncDeck extends DetailOptions {
  label: string
  loaded: boolean
}

// Por debajo de esto ya no se oye el desfase entre los bombos
const EN_FASE_MS = 15

/** El tiempo del compas en el que va un plato (0 a 3) y cuanto lleva de el. */
function enCompas(deck: SyncDeck) {
  if (!deck.grid) return null
  const golpe = beatPosition(deck.grid, deck.position)
  return { tiempo: Math.floor(modulo(golpe, BEATS_PER_BAR)), golpe }
}

/** Las dos ondas de detalle una encima de otra con la misma aguja, como en la
 *  pantalla de rekordbox: si los platos van a la par, las lineas de la
 *  rejilla de arriba y las de abajo caen juntas. Entre medias, el medidor de
 *  fase del CDJ. */
export function SyncView({ decks }: { decks: [SyncDeck, SyncDeck] }) {
  const refs = [useRef<HTMLCanvasElement>(null), useRef<HTMLCanvasElement>(null)]

  useEffect(() => {
    decks.forEach((deck, i) => {
      const canvas = refs[i].current
      if (canvas) drawDetail(canvas, deck)
    })
  })

  const [a, b] = decks
  const compas = [enCompas(a), enCompas(b)]

  // Desfase de B respecto a A. En tiempos, entre -2 y 2: con mas, va por
  // delante en el compas siguiente.
  let aviso: { texto: string; bien: boolean } | null = null
  if (compas[0] && compas[1] && a.grid && b.grid) {
    const tiempos = modulo(compas[1].golpe - compas[0].golpe + 2, BEATS_PER_BAR) - 2
    const enteros = Math.round(tiempos)
    const fraccion = tiempos - enteros
    // A milisegundos de reloj, al tempo al que suena A
    const ms = (fraccion * 60 * 1000) / (a.grid.bpm * a.tempo)
    const bpmA = a.grid.bpm * a.tempo
    const bpmB = b.grid.bpm * b.tempo
    const partes: string[] = []
    if (Math.abs(bpmA - bpmB) >= 0.05) {
      partes.push(`B va ${Math.abs(bpmB - bpmA).toFixed(2)} BPM ${bpmB > bpmA ? 'más rápido' : 'más lento'}`)
    }
    if (Math.abs(ms) >= EN_FASE_MS) {
      partes.push(`los golpes de B llegan ${Math.abs(Math.round(ms))} ms ${ms > 0 ? 'antes' : 'tarde'}`)
    }
    if (enteros !== 0) {
      partes.push(`B va ${Math.abs(enteros)} ${Math.abs(enteros) === 1 ? 'tiempo' : 'tiempos'} ${enteros > 0 ? 'por delante' : 'por detrás'} en el compás`)
    }
    aviso = partes.length
      ? { texto: partes.join(' · '), bien: false }
      : { texto: 'En fase: los bombos caen juntos', bien: true }
  }

  return (
    <section className="sync card" aria-label="Comparar los dos platos">
      {decks.map((deck, i) => (
        <div key={deck.label} className="sync__row">
          <span className="sync__label">{deck.label}</span>
          <canvas
            ref={refs[i]}
            className="sync__wave"
            role="img"
            aria-label={`Onda de detalle del plato ${deck.label}`}
          />
          <div className="phase" aria-label={`Tiempo del compás del plato ${deck.label}`}>
            {Array.from({ length: BEATS_PER_BAR }, (_, t) => (
              <span
                key={t}
                className={`phase__beat${compas[i]?.tiempo === t ? (t === 0 ? ' phase__beat--one' : ' phase__beat--on') : ''}`}
              >
                {t + 1}
              </span>
            ))}
          </div>
        </div>
      ))}
      <p className={`sync__status${aviso?.bien ? ' sync__status--ok' : ''}`}>
        {aviso
          ? aviso.texto
          : a.loaded && b.loaded
            ? 'Calculando la rejilla...'
            : 'Carga una canción en cada plato para compararlos.'}
      </p>
    </section>
  )
}
