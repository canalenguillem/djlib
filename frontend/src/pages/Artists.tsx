import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import * as artistsApi from '../api/artists'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import type { Artist } from '../types/api'

function origin(artist: Artist): string {
  const parts = [artist.country, artist.begin_year ? `desde ${artist.begin_year}` : null]
  return parts.filter(Boolean).join(' · ') || 'sin datos'
}

export function ArtistsPage() {
  const [artists, setArtists] = useState<Artist[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await artistsApi.listArtists(activeSearch)
      setArtists(page.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar.')
    } finally {
      setLoading(false)
    }
  }, [activeSearch])

  useEffect(() => {
    void load()
  }, [load])

  // Consultar MusicBrainz y Wikipedia lleva unos segundos y ocurre en segundo
  // plano: mientras haya fichas sin resolver, se refresca para verlas llegar.
  const pendingCount = useMemo(
    () => artists.filter((a) => a.enrichment_status === 'pending').length,
    [artists],
  )
  const loadRef = useRef(load)
  loadRef.current = load
  useEffect(() => {
    if (pendingCount === 0) return
    const timer = window.setInterval(() => void loadRef.current(), 4000)
    return () => window.clearInterval(timer)
  }, [pendingCount])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const artist = await artistsApi.createArtist(newName.trim())
      setArtists((prev) => [...prev, artist].sort((a, b) => a.name.localeCompare(b.name)))
      setNewName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el artista.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="stack">
      <h1>Artistas</h1>
      <p className="muted">
        Las fichas se crean solas al descargar una cancion y se rellenan con datos de
        MusicBrainz y Wikipedia. Tambien puedes anadir una a mano.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card">
        <div className="filters">
          <form
            className="filters__search"
            onSubmit={(e) => {
              e.preventDefault()
              setActiveSearch(search)
            }}
          >
            <input
              type="search"
              value={search}
              placeholder="Buscar por nombre o biografia..."
              onChange={(e) => setSearch(e.target.value)}
            />
            <button type="submit" className="btn btn--ghost">
              Buscar
            </button>
          </form>
          <form className="inline-form" onSubmit={handleCreate}>
            <input
              type="text"
              value={newName}
              placeholder="Anadir artista a mano"
              onChange={(e) => setNewName(e.target.value)}
            />
            <button type="submit" className="btn btn--primary" disabled={creating}>
              {creating ? 'Creando...' : 'Anadir'}
            </button>
          </form>
        </div>
      </section>

      {loading ? (
        <Loading />
      ) : (
        <section className="card">
          <h2>
            {artists.length} {artists.length === 1 ? 'artista' : 'artistas'}
          </h2>
          {artists.length === 0 ? (
            <p className="muted">
              Todavia no hay fichas. Se crearan al anadir canciones a la biblioteca.
            </p>
          ) : (
            <ul className="artistlist">
              {artists.map((artist) => (
                <li key={artist.id} className="artistcard">
                  <Link to={`/artists/${artist.id}`} className="artistcard__name">
                    {artist.name}
                  </Link>
                  <span className="muted">{origin(artist)}</span>
                  <span className="muted">
                    {artist.track_count}{' '}
                    {artist.track_count === 1 ? 'cancion' : 'canciones'}
                  </span>
                  {artist.bio ? (
                    <p className="artistcard__bio">{artist.bio}</p>
                  ) : (
                    <p className="artistcard__bio muted">
                      {artist.enrichment_status === 'pending'
                        ? 'Consultando MusicBrainz y Wikipedia...'
                        : artist.enrichment_status === 'error'
                          ? 'No se pudieron consultar las fuentes.'
                          : 'Sin biografia todavia.'}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
