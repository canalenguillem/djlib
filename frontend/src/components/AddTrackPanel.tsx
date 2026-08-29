import { useState } from 'react'
import type { FormEvent } from 'react'

import * as tracksApi from '../api/tracks'
import type { SearchCandidate } from '../types/api'
import { Alert } from './Alert'
import { SearchCandidates } from './SearchCandidates'

type Mode = 'url' | 'search'

interface Props {
  onAdded: () => void
}

export function AddTrackPanel({ onAdded }: Props) {
  const [mode, setMode] = useState<Mode>('url')
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  // Buscar no descarga nada: muestra los candidatos y el usuario elige.
  const [candidates, setCandidates] = useState<SearchCandidate[] | null>(null)
  const [addedIds, setAddedIds] = useState<string[]>([])
  const [addingId, setAddingId] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setOk(null)
    setSending(true)
    try {
      if (mode === 'url') {
        const track = await tracksApi.addFromUrl(url.trim())
        setUrl('')
        setOk(`Descargando: ${track.request_query}`)
        onAdded()
      } else {
        const resultados = await tracksApi.previewSearch(title.trim(), artist.trim() || null)
        setCandidates(resultados.candidates)
        setAddedIds([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo completar la operacion.')
    } finally {
      setSending(false)
    }
  }

  async function handleAddCandidate(candidate: SearchCandidate) {
    setError(null)
    setOk(null)
    setAddingId(candidate.video_id)
    try {
      await tracksApi.addFromUrl(candidate.url)
      setAddedIds((prev) => [...prev, candidate.video_id])
      setOk(`Descargando: ${candidate.title}`)
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAddingId(null)
    }
  }

  function changeMode(next: Mode) {
    setMode(next)
    setCandidates(null)
    setError(null)
    setOk(null)
  }

  return (
    <section className="card">
      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'url'}
          className={mode === 'url' ? 'tab tab--active' : 'tab'}
          onClick={() => changeMode('url')}
        >
          Desde un enlace
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'search'}
          className={mode === 'search' ? 'tab tab--active' : 'tab'}
          onClick={() => changeMode('search')}
        >
          Por titulo y artista
        </button>
      </div>

      {error && <Alert kind="error">{error}</Alert>}
      {ok && <Alert kind="success">{ok}</Alert>}

      <form onSubmit={handleSubmit} className="grid-form">
        {mode === 'url' ? (
          <label className="field field--wide">
            <span>Enlace de YouTube</span>
            <input
              type="url"
              value={url}
              required
              placeholder="https://www.youtube.com/watch?v=..."
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
        ) : (
          <>
            <label className="field">
              <span>Titulo</span>
              <input
                type="text"
                value={title}
                required
                placeholder="Song 2"
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Artista (opcional)</span>
              <input
                type="text"
                value={artist}
                placeholder="Blur"
                onChange={(e) => setArtist(e.target.value)}
              />
            </label>
          </>
        )}
        <div className="grid-form__actions">
          <button type="submit" className="btn btn--primary" disabled={sending}>
            {sending
              ? mode === 'url'
                ? 'Anadiendo...'
                : 'Buscando...'
              : mode === 'url'
                ? 'Anadir a la biblioteca'
                : 'Buscar en YouTube'}
          </button>
        </div>
      </form>

      {mode === 'search' && candidates !== null && (
        <SearchCandidates
          candidates={candidates}
          addedIds={addedIds}
          addingId={addingId}
          onAdd={handleAddCandidate}
        />
      )}
    </section>
  )
}
