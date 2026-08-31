import { formatClock } from '../lib/audioEngine'
import type { Track } from '../types/api'
import { PauseIcon, PlayIcon } from './icons'

export interface DeckControls {
  label: string
  track: Track | null
  loading: boolean
  playing: boolean
  position: number
  duration: number
  tempo: number
  volume: number
  cues: Array<number | null>
  onPlayPause: () => void
  onSeek: (segundos: number) => void
  onTempo: (valor: number) => void
  onVolume: (valor: number) => void
  onCue: (indice: number) => void
  onClearCue: (indice: number) => void
}

export function DeckPanel(props: DeckControls) {
  const {
    label, track, loading, playing, position, duration, tempo, volume, cues,
  } = props

  const avance = duration > 0 ? (position / duration) * 100 : 0
  // El porcentaje de tempo es lo que se lee en un plato: 0 % es la velocidad
  // original, +6 % es un 6 % mas rapido.
  const porcentaje = ((tempo - 1) * 100).toFixed(1)

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
        <button
          type="button"
          className="deck__play"
          disabled={!track || loading}
          aria-label={playing ? 'Pausar' : 'Reproducir'}
          onClick={props.onPlayPause}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="deck__times">
          <span>{formatClock(position)}</span>
          <span className="muted">-{formatClock(Math.max(0, duration - position))}</span>
        </div>
      </div>

      {/* Barra de posicion: pinchar en ella salta a ese punto */}
      <div
        className="deck__progress"
        role="slider"
        tabIndex={0}
        aria-label="Posicion"
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(position)}
        onClick={(e) => {
          if (!duration) return
          const caja = e.currentTarget.getBoundingClientRect()
          props.onSeek(((e.clientX - caja.left) / caja.width) * duration)
        }}
      >
        <div className="deck__played" style={{ width: `${avance}%` }} />
      </div>

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

      <label className="deck__control">
        <span>
          Tempo <strong>{Number(porcentaje) > 0 ? `+${porcentaje}` : porcentaje} %</strong>
        </span>
        <input
          type="range"
          min={0.92}
          max={1.08}
          step={0.001}
          value={tempo}
          onChange={(e) => props.onTempo(Number(e.target.value))}
        />
      </label>

      <label className="deck__control">
        <span>Volumen</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(e) => props.onVolume(Number(e.target.value))}
        />
      </label>
    </section>
  )
}
