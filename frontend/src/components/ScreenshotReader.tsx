import { useEffect, useState } from 'react'

import * as recognitionApi from '../api/recognition'
import * as tracksApi from '../api/tracks'
import type { DetectedSong, SearchCandidate } from '../types/api'
import { Alert } from './Alert'
import { SearchCandidates } from './SearchCandidates'

/** Lectura de capturas de pantalla.
 *
 *  Pensado para la lista de Shazam: si lo dejas identificando solo durante la
 *  noche, subes la captura al dia siguiente y salen todas de una vez, en vez de
 *  teclearlas una por una.
 */
export function ScreenshotReader() {
  const [songs, setSongs] = useState<DetectedSong[] | null>(null)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [candidates, setCandidates] = useState<SearchCandidate[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [addedIds, setAddedIds] = useState<string[]>([])
  const [addingId, setAddingId] = useState<string | null>(null)

  async function leer(file: File) {
    setError(null)
    setSongs(null)
    setCandidates(null)
    setOpenIndex(null)
    setReading(true)
    try {
      const resultado = await recognitionApi.readScreenshot(file)
      setSongs(resultado.songs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se ha podido leer la captura.')
    } finally {
      setReading(false)
    }
  }

  // Pegar con Ctrl+V es la forma natural en el escritorio: haces la captura y
  // la pegas sin pasar por guardarla en disco.
  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const imagen = [...(event.clipboardData?.items ?? [])].find((i) =>
        i.type.startsWith('image/'),
      )
      const file = imagen?.getAsFile()
      if (file) {
        event.preventDefault()
        void leer(file)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  async function buscar(index: number, song: DetectedSong) {
    setOpenIndex(index)
    setCandidates(null)
    setSearching(true)
    setError(null)
    try {
      const resultado = await tracksApi.previewSearch(song.title, song.artist)
      setCandidates(resultado.candidates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La busqueda ha fallado.')
    } finally {
      setSearching(false)
    }
  }

  async function anadir(candidate: SearchCandidate) {
    setAddingId(candidate.video_id)
    setError(null)
    try {
      await tracksApi.addFromUrl(candidate.url)
      setAddedIds((prev) => [...prev, candidate.video_id])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAddingId(null)
    }
  }

  return (
    <section className="card">
      <h2>Desde una captura</h2>
      <p className="muted">
        Si dejas Shazam identificando solo durante la noche, sube aqui la captura de
        la lista y saldran todas las canciones de golpe. Tambien vale cualquier otra
        pantalla donde se lean titulos. En el ordenador puedes pegarla con Ctrl+V.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <label className="field">
        <span>Imagen de la captura</span>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          disabled={reading}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void leer(file)
          }}
        />
      </label>

      {reading && <p className="muted">Leyendo la captura...</p>}

      {songs !== null &&
        (songs.length === 0 ? (
          <Alert kind="info">
            No se ha leido ninguna cancion en la imagen. Prueba con una captura donde
            los titulos se vean con claridad.
          </Alert>
        ) : (
          <>
            <p className="muted">
              {songs.length} {songs.length === 1 ? 'cancion leida' : 'canciones leidas'}:
            </p>
            <ul className="detected">
              {songs.map((song, index) => (
                <li key={`${song.title}-${index}`} className="detected__item">
                  <div className="detected__row">
                    <div className="track__info">
                      <div className="track__title">{song.title}</div>
                      <div className="track__meta">
                        <span>{song.artist ?? 'Artista desconocido'}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={searching}
                      onClick={() => buscar(index, song)}
                    >
                      {searching && openIndex === index ? 'Buscando...' : 'Buscar en YouTube'}
                    </button>
                  </div>
                  {openIndex === index && candidates !== null && (
                    <SearchCandidates
                      candidates={candidates}
                      addedIds={addedIds}
                      addingId={addingId}
                      onAdd={anadir}
                    />
                  )}
                </li>
              ))}
            </ul>
          </>
        ))}
    </section>
  )
}
