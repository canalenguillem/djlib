import { useState } from 'react'
import type { FormEvent } from 'react'

import * as tracksApi from '../api/tracks'
import { Alert } from './Alert'

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
      } else {
        const track = await tracksApi.addFromSearch(title.trim(), artist.trim() || null)
        setTitle('')
        setArtist('')
        setOk(`Buscando y descargando: ${track.request_query}`)
      }
      onAdded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="card">
      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'url'}
          className={mode === 'url' ? 'tab tab--active' : 'tab'}
          onClick={() => setMode('url')}
        >
          Desde un enlace
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'search'}
          className={mode === 'search' ? 'tab tab--active' : 'tab'}
          onClick={() => setMode('search')}
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
            {sending ? 'Anadiendo...' : 'Anadir a la biblioteca'}
          </button>
        </div>
      </form>
    </section>
  )
}
