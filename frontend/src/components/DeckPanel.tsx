import { useEffect, useRef } from 'react'

import { formatClock } from '../lib/audioEngine'
import type { BeatGrid } from '../lib/beatgrid'
import type { DeckWaveformData } from '../lib/waveform'
import type { Track } from '../types/api'
import { DeckWaveform } from './DeckWaveform'
import { PauseIcon, PlayIcon } from './icons'

export interface DeckControls {
  label: string
  track: Track | null
  loading: boolean
  playing: boolean
  position: number
  duration: number
  tempo: number
  cues: Array<number | null>
  mainCue: number
  waveform: DeckWaveformData | null
  analyzing: boolean
  grid: BeatGrid | null
  /** BPM del otro plato con su tempo aplicado, para poder igualar. */
  otherBpm: number | null
  /** Recorrido del fader en por ciento, como el selector de un CDJ. */
  range: number
  onRange: (valor: number) => void
  onMatch: () => void
  onResetTempo: () => void
  onPlayPause: () => void
  onSeek: (segundos: number) => void
  onTempo: (valor: number) => void
  /** El CUE se usa manteniendolo pulsado: importa cuando se suelta. */
  onCueDown: () => void
  onCueUp: () => void
  onCue: (indice: number) => void
  onClearCue: (indice: number) => void
  /** Empujon del jog: 1 al soltar. */
  onNudge: (factor: number) => void
  onDownbeat: () => void
}

// Cuanto frena o acelera el empujon: lo justo para mover los golpes sin que
// se note el cambio de tono
const EMPUJON = 0.04
// Paso del fader de tempo: 0,05 %, lo fino que hace falta para cuadrar dos
// temas a mano
const PASO_TEMPO = 0.0005
// Cada clic en - o + mueve una centesima de BPM: el ultimo ajuste, cuando
// el fader ya es demasiado basto
const PASO_BPM = 0.01
// Manteniendo pulsado se repite, primero despacio y luego mas rapido
const ESPERA_REPETICION_MS = 400
const CADENCIA_MS = 70

export function DeckPanel(props: DeckControls) {
  const {
    label, track, loading, playing, position, duration, tempo, cues, mainCue, otherBpm, range,
    waveform, analyzing, grid,
  } = props

  // El tempo real al que suena ahora: es lo que hay que igualar entre platos,
  // no el BPM original del tema.
  // El afinado de la rejilla si ya esta: el de la biblioteca es un entero
  const bpm = grid?.bpm ?? track?.bpm ?? null
  const sonando = bpm === null ? null : bpm * tempo
  // El ajuste tiene que caber en el recorrido del fader. Ojo con la asimetria:
  // subir 10 BPM desde 118 son +8,5%, pero bajarlos desde 128 son -7,8%. Por eso
  // el recorrido es seleccionable, igual que en un plato de verdad.
  const limite = range / 100
  const ajuste = bpm && otherBpm ? otherBpm / bpm : null
  const puedeIgualar = ajuste !== null && Math.abs(ajuste - 1) <= limite + 1e-9
  // Cuanto haria falta, para poder explicarlo cuando no cabe
  const necesario = ajuste === null ? null : (ajuste - 1) * 100

  const listo = track !== null && !loading
  // El CUE se ilumina parado en el cue: pulsarlo hara sonar desde ahi
  const enCue = listo && !playing && Math.abs(position - mainCue) < 0.01

  // El porcentaje de tempo es lo que se lee en un plato: 0 % es la velocidad
  // original, +6 % es un 6 % mas rapido.
  const porcentaje = ((tempo - 1) * 100).toFixed(1)
  const textoTempo = `${Number(porcentaje) > 0 ? '+' : ''}${porcentaje} %`

  // El tempo al dia para la repeticion de los botones, que corre fuera del
  // render
  const tempoActual = useRef(tempo)
  tempoActual.current = tempo
  const repeticion = useRef<number | null>(null)

  function limitarTempo(valor: number) {
    return Math.max(1 - limite, Math.min(1 + limite, valor))
  }

  function moverTempo(valor: number) {
    let nuevo = limitarTempo(valor)
    // Un iman muy pequeno en el 0, como el clic del centro del fader del CDJ.
    // Solo al arrastrar: con los botones hay que poder quedarse al lado.
    if (Math.abs(nuevo - 1) < limite * 0.004) nuevo = 1
    props.onTempo(nuevo)
  }

  /** Un paso de - o +: una centesima de BPM, o un 0,01 % si no hay BPM. */
  function pasoFino(sentido: 1 | -1) {
    const delta = bpm ? PASO_BPM / bpm : 0.0001
    const nuevo = limitarTempo(tempoActual.current + sentido * delta)
    tempoActual.current = nuevo
    props.onTempo(nuevo)
  }

  function pararRepeticion() {
    if (repeticion.current !== null) window.clearTimeout(repeticion.current)
    repeticion.current = null
  }

  function empezarRepeticion(sentido: 1 | -1) {
    pararRepeticion()
    pasoFino(sentido)
    const repetir = () => {
      pasoFino(sentido)
      repeticion.current = window.setTimeout(repetir, CADENCIA_MS)
    }
    repeticion.current = window.setTimeout(repetir, ESPERA_REPETICION_MS)
  }

  useEffect(() => pararRepeticion, [])

  function botonFino(sentido: 1 | -1) {
    return (
      <button
        type="button"
        className="pitch__step"
        disabled={!track}
        aria-label={sentido < 0 ? 'Bajar una centésima de BPM' : 'Subir una centésima de BPM'}
        title={`${sentido < 0 ? 'Más lento' : 'Más rápido'}: ${PASO_BPM.toFixed(2)} BPM por clic. Mantén pulsado para seguir.`}
        onPointerDown={(e) => {
          if (e.button !== 0) return
          e.currentTarget.setPointerCapture(e.pointerId)
          empezarRepeticion(sentido)
        }}
        onPointerUp={pararRepeticion}
        onPointerCancel={pararRepeticion}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            pasoFino(sentido)
          }
        }}
      >
        {sentido < 0 ? '−' : '+'}
      </button>
    )
  }

  return (
    <section className="deck card">
      <div className="deck__head">
        <span className="deck__label">{label}</span>
        <div className="deck__title">
          {loading ? (
            <span className="muted">Cargando el audio...</span>
          ) : track ? (
            <>
              <strong>{track.title}</strong>
              <span className="muted">{track.artist_text ?? 'Artista desconocido'}</span>
            </>
          ) : (
            <span className="muted">Sin cancion. Cargala desde la lista de abajo.</span>
          )}
        </div>
      </div>

      <div className="deck__transport">
        <div className="deck__times">
          <span>{formatClock(position)}</span>
          <span className="muted">-{formatClock(Math.max(0, duration - position))}</span>
        </div>
        <div className="deck__bpm">
          {bpm === null ? (
            <span className="muted">sin BPM</span>
          ) : (
            <>
              <strong>{sonando!.toFixed(grid ? 2 : 1)}</strong>
              <span className="muted">BPM{tempo !== 1 && ` · original ${bpm.toFixed(grid ? 2 : 0)}`}</span>
            </>
          )}
        </div>
      </div>

      <DeckWaveform
        data={waveform}
        analyzing={analyzing}
        position={position}
        tempo={tempo}
        grid={grid}
        duration={duration}
        cues={cues}
        mainCue={mainCue}
        onSeek={props.onSeek}
      />

      <div className="deck__deck">
        {/* CUE encima de PLAY, como en un CDJ: la mano no tiene que buscarlos */}
        <div className="deck__buttons">
          <button
            type="button"
            className={`bigbtn bigbtn--cue${enCue ? ' bigbtn--on' : ''}`}
            disabled={!listo}
            title="Sonando: vuelve al cue. Parado: marca el cue aqui, o si ya estas en el, suena mientras lo mantengas"
            onPointerDown={(e) => {
              if (e.button !== 0) return
              // Para enterarse de que se suelta aunque el dedo salga del boton
              e.currentTarget.setPointerCapture(e.pointerId)
              props.onCueDown()
            }}
            onPointerUp={props.onCueUp}
            onPointerCancel={props.onCueUp}
            onKeyDown={(e) => {
              if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) {
                e.preventDefault()
                props.onCueDown()
              }
            }}
            onKeyUp={(e) => {
              if (e.key === ' ' || e.key === 'Enter') props.onCueUp()
            }}
          >
            CUE
          </button>
          <button
            type="button"
            className={`bigbtn bigbtn--play${playing ? ' bigbtn--on' : listo ? ' bigbtn--ready' : ''}`}
            disabled={!listo}
            aria-label={playing ? 'Pausar' : 'Reproducir'}
            onClick={props.onPlayPause}
          >
            {playing ? <PauseIcon /> : <PlayIcon />}
          </button>
        </div>

        <div className="deck__side">
          <div className="deck__pads">
            {cues.map((cue, indice) => (
              <div key={indice} className="pad__wrap">
                <button
                  type="button"
                  className={cue === null ? 'pad' : 'pad pad--set'}
                  disabled={!track}
                  title={
                    cue === null
                      ? 'Marca este punto de la cancion'
                      : `Saltar a ${formatClock(cue)}`
                  }
                  onClick={() => props.onCue(indice)}
                >
                  <span className="pad__num">{indice + 1}</span>
                  <span className="pad__time">{cue === null ? '—' : formatClock(cue)}</span>
                </button>
                {cue !== null && (
                  <button
                    type="button"
                    className="pad__clear"
                    aria-label={`Borrar el cue ${indice + 1}`}
                    onClick={() => props.onClearCue(indice)}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="deck__nudge">
            {[
              { factor: 1 - EMPUJON, texto: '« Frenar', ayuda: 'Mantén pulsado para que el plato vaya un poco más lento y sus golpes se retrasen' },
              { factor: 1 + EMPUJON, texto: 'Empujar »', ayuda: 'Mantén pulsado para que el plato vaya un poco más rápido y sus golpes se adelanten' },
            ].map(({ factor, texto, ayuda }) => (
              <button
                key={texto}
                type="button"
                className="btn btn--ghost nudge"
                disabled={!listo}
                title={ayuda}
                onPointerDown={(e) => {
                  if (e.button !== 0) return
                  e.currentTarget.setPointerCapture(e.pointerId)
                  props.onNudge(factor)
                }}
                onPointerUp={() => props.onNudge(1)}
                onPointerCancel={() => props.onNudge(1)}
                onKeyDown={(e) => {
                  if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) {
                    e.preventDefault()
                    props.onNudge(factor)
                  }
                }}
                onKeyUp={(e) => {
                  if (e.key === ' ' || e.key === 'Enter') props.onNudge(1)
                }}
              >
                {texto}
              </button>
            ))}
            <button
              type="button"
              className="btn btn--ghost nudge"
              disabled={!grid}
              title="Si la línea roja no cae en el primer tiempo del compás, para la aguja en él y pulsa aquí"
              onClick={props.onDownbeat}
            >
              Marcar el 1 aquí
            </button>
          </div>

          <label className="deck__control">
            <span>
              Tempo <strong>{textoTempo}</strong>
              {puedeIgualar && (
                <button type="button" className="deck__match" onClick={props.onMatch}>
                  Igualar al otro plato
                </button>
              )}
              {/* Solo tiene sentido si el tempo esta tocado */}
              {tempo !== 1 && (
                <button
                  type="button"
                  className="deck__match deck__match--reset"
                  title="Devuelve el plato a su velocidad original"
                  onClick={props.onResetTempo}
                >
                  Tempo original{bpm ? ` (${bpm.toFixed(grid ? 2 : 0)})` : ''}
                </button>
              )}
            </span>
            <div className="deck__range">
              <span className="muted">Recorrido</span>
              {[8, 16, 50].map((opcion) => (
                <button
                  key={opcion}
                  type="button"
                  className={opcion === range ? 'rangebtn rangebtn--on' : 'rangebtn'}
                  onClick={() => props.onRange(opcion)}
                >
                  ±{opcion}%
                </button>
              ))}
              {!puedeIgualar && necesario !== null && (
                <span className="muted deck__needed">
                  igualar pide {necesario > 0 ? '+' : ''}
                  {necesario.toFixed(1)} %
                </span>
              )}
            </div>
          </label>
        </div>

        {/* El fader de tempo del CDJ: vertical, con el - arriba y el + abajo.
            Hacia uno mismo, mas rapido. */}
        <div className="pitch">
          {botonFino(-1)}
          <div className="pitch__track">
            <span className="pitch__zero" aria-hidden="true" />
            <input
              type="range"
              className="pitch__fader"
              min={1 - limite}
              max={1 + limite}
              step={PASO_TEMPO}
              value={tempo}
              disabled={!track}
              aria-label="Tempo"
              aria-valuetext={textoTempo}
              title="Arriba, más lento; abajo, más rápido. Doble clic: tempo original"
              onChange={(e) => moverTempo(Number(e.target.value))}
              onDoubleClick={props.onResetTempo}
              onKeyDown={(e) => {
                // Las flechas siguen al cursor: arriba lo sube, y eso es frenar
                const pasos: Record<string, number> = {
                  ArrowUp: -PASO_TEMPO, ArrowLeft: -PASO_TEMPO,
                  ArrowDown: PASO_TEMPO, ArrowRight: PASO_TEMPO,
                  PageUp: -0.01, PageDown: 0.01,
                }
                if (e.key in pasos) {
                  e.preventDefault()
                  moverTempo(tempo + pasos[e.key])
                }
              }}
            />
          </div>
          {botonFino(1)}
          <strong className="pitch__value">{textoTempo}</strong>
          {sonando !== null && <span className="pitch__bpm">{sonando.toFixed(2)} BPM</span>}
        </div>
      </div>
    </section>
  )
}
