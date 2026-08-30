import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import * as recognitionApi from '../api/recognition'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import { RecorderError, checkSupport, record } from '../lib/recorder'
import type { RecognitionResult, SearchCandidate } from '../types/api'

// AudD recomienda fragmentos de 2 a 12 segundos: por encima de ahi, con el
// ruido de un bar, falla al generar la huella. 11 deja margen.
const SECONDS = 11
// Por debajo de esto no hay material suficiente para identificar nada, asi que
// no se deja cortar antes aunque se toque el boton.
const MIN_SECONDS = 3

type Phase = 'idle' | 'recording' | 'identifying' | 'done'

export function RecognizePage() {
  const [available, setAvailable] = useState<boolean | null>(null)
  const [support, setSupport] = useState<RecorderError | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [result, setResult] = useState<RecognitionResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [addedIds, setAddedIds] = useState<string[]>([])
  const [addingId, setAddingId] = useState<string | null>(null)

  // Busqueda a mano para cuando no se reconoce pero el usuario lo intuye
  const [manualTitle, setManualTitle] = useState('')
  const [manualArtist, setManualArtist] = useState('')
  const [searching, setSearching] = useState(false)

  const stopper = useRef<{ stop: () => void }>({ stop: () => undefined })

  useEffect(() => {
    recognitionApi
      .getRecognitionStatus()
      .then((estado) => setAvailable(estado.enabled))
      .catch(() => setAvailable(false))
    setSupport(checkSupport())
  }, [])

  async function handleRecord() {
    setError(null)
    setResult(null)
    setAddedIds([])
    setElapsed(0)
    setPhase('recording')
    try {
      const grabacion = await record(SECONDS, setElapsed, stopper.current)
      setPhase('identifying')
      const identificada = await recognitionApi.recognizeAudio(
        grabacion.blob,
        grabacion.filename,
      )
      setResult(identificada)
      if (!identificada.recognized) {
        setManualTitle('')
        setManualArtist('')
      }
      setPhase('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido identificar la cancion.')
      setPhase('idle')
    }
  }

  function handleStop() {
    if (canStop) stopper.current.stop()
  }

  async function handleAdd(candidate: SearchCandidate) {
    setError(null)
    setAddingId(candidate.video_id)
    try {
      await tracksApi.addFromUrl(candidate.url)
      setAddedIds((prev) => [...prev, candidate.video_id])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAddingId(null)
    }
  }

  async function handleManualSearch(event: FormEvent) {
    event.preventDefault()
    if (!manualTitle.trim() && !manualArtist.trim()) return
    setSearching(true)
    setError(null)
    try {
      const encontrados = await tracksApi.previewSearch(
        manualTitle.trim() || null,
        manualArtist.trim() || null,
      )
      setResult({
        recognized: false,
        artist: null,
        title: null,
        album: null,
        release_date: null,
        song_link: null,
        candidates: encontrados.candidates,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La busqueda ha fallado.')
    } finally {
      setSearching(false)
    }
  }

  if (available === null) return <Loading />

  if (!available) {
    return (
      <div className="stack">
        <h1>Reconocer</h1>
        <Alert kind="info">
          El reconocimiento de audio no esta configurado en el servidor. Hace falta
          una clave de AudD en <code>RECOGNITION_API_KEY</code>.
        </Alert>
      </div>
    )
  }

  const recording = phase === 'recording'
  const identifying = phase === 'identifying'
  const remaining = Math.max(0, SECONDS - elapsed)
  const canStop = elapsed >= MIN_SECONDS

  return (
    <div className="stack recognize">
      <h1>Reconocer</h1>

      {support && <Alert kind="error">{support.message}</Alert>}
      {error && <Alert kind="error">{error}</Alert>}

      <section className="card recognize__panel">
        <button
          type="button"
          className={`recorder ${recording ? 'recorder--on' : ''}`}
          disabled={identifying || support !== null}
          onClick={recording ? handleStop : handleRecord}
        >
          {recording ? (
            <>
              <span className="recorder__count">{remaining}</span>
              <span className="recorder__label">
                {canStop ? 'Grabando... toca para parar' : 'Grabando...'}
              </span>
            </>
          ) : identifying ? (
            <>
              <span className="spinner spinner--big" aria-hidden="true" />
              <span className="recorder__label">Identificando...</span>
            </>
          ) : (
            <>
              <span className="recorder__dot" aria-hidden="true" />
              <span className="recorder__label">Grabar {SECONDS} s</span>
            </>
          )}
        </button>

        {recording && (
          <div className="recorder__bar" aria-hidden="true">
            <div
              className="recorder__progress"
              style={{ width: `${Math.min(100, (elapsed / SECONDS) * 100)}%` }}
            />
          </div>
        )}

        <p className="muted recognize__hint">
          Acerca el movil al altavoz y manten pulsado el ambiente unos segundos.
        </p>
      </section>

      {result?.recognized && (
        <section className="card">
          <h2>{result.title}</h2>
          <p className="recognize__artist">{result.artist}</p>
          <p className="muted">
            {[result.album, result.release_date?.slice(0, 4)].filter(Boolean).join(' · ')}
          </p>
          {result.candidates.length > 0 ? (
            <>
              <p className="muted">Elige la version que quieres descargar:</p>
              <SearchCandidates
                candidates={result.candidates}
                addedIds={addedIds}
                addingId={addingId}
                onAdd={handleAdd}
              />
            </>
          ) : (
            <Alert kind="info">
              Identificada, pero la busqueda en YouTube no ha devuelto resultados.
              Prueba a buscarla desde la biblioteca.
            </Alert>
          )}
        </section>
      )}

      {result && !result.recognized && (
        <section className="card">
          <h2>No se ha reconocido</h2>
          <p className="muted">
            Suele pasar con mucho ruido o si suena lejos. Acercate al altavoz y vuelve
            a grabar, o busca lo que creas que es.
          </p>
          <button type="button" className="btn btn--primary" onClick={handleRecord}>
            Reintentar grabacion
          </button>

          <form className="grid-form" onSubmit={handleManualSearch}>
            <label className="field">
              <span>Titulo</span>
              <input
                type="text"
                value={manualTitle}
                placeholder="Lo que hayas pillado"
                onChange={(e) => setManualTitle(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Artista</span>
              <input
                type="text"
                value={manualArtist}
                placeholder="Si lo intuyes"
                onChange={(e) => setManualArtist(e.target.value)}
              />
            </label>
            <div className="grid-form__actions">
              <button
                type="submit"
                className="btn btn--ghost"
                disabled={searching || (!manualTitle.trim() && !manualArtist.trim())}
              >
                {searching ? 'Buscando...' : 'Buscar en YouTube'}
              </button>
            </div>
          </form>

          {result.candidates.length > 0 && (
            <SearchCandidates
              candidates={result.candidates}
              addedIds={addedIds}
              addingId={addingId}
              onAdd={handleAdd}
            />
          )}
        </section>
      )}
    </div>
  )
}
