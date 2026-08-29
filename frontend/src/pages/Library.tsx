import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import * as tagsApi from '../api/tags'
import * as tracksApi from '../api/tracks'
import { AddTrackPanel } from '../components/AddTrackPanel'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { Player } from '../components/Player'
import { TrackRow } from '../components/TrackRow'
import type { Tag, TagKind, Track } from '../types/api'

const KIND_LABEL: Record<TagKind, string> = {
  mood: 'Mood',
  style: 'Estilo',
  moment: 'Momento',
}
const KINDS: TagKind[] = ['mood', 'style', 'moment']

export function LibraryPage() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [total, setTotal] = useState(0)
  const [allTags, setAllTags] = useState<Tag[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [filterTagIds, setFilterTagIds] = useState<number[]>([])
  const [playing, setPlaying] = useState<Track | null>(null)

  const load = useCallback(async () => {
    try {
      const page = await tracksApi.listTracks({ search: activeSearch, tagIds: filterTagIds })
      setTracks(page.items)
      setTotal(page.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la biblioteca.')
    } finally {
      setLoading(false)
    }
  }, [activeSearch, filterTagIds])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    tagsApi
      .listTags()
      .then(setAllTags)
      .catch(() => undefined)
  }, [])

  // Mientras haya descargas en marcha, refrescamos para ver como avanzan.
  const pendingCount = useMemo(
    () => tracks.filter((t) => t.status === 'pending' || t.status === 'downloading').length,
    [tracks],
  )
  const loadRef = useRef(load)
  loadRef.current = load
  useEffect(() => {
    if (pendingCount === 0) return
    const timer = window.setInterval(() => void loadRef.current(), 3000)
    return () => window.clearInterval(timer)
  }, [pendingCount])

  function toggleFilter(tagId: number) {
    setFilterTagIds((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId],
    )
  }

  const filtering = activeSearch !== '' || filterTagIds.length > 0

  return (
    <div className="stack">
      <h1>Biblioteca</h1>

      <AddTrackPanel onAdded={() => void load()} />

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
              placeholder="Buscar por titulo o artista..."
              onChange={(e) => setSearch(e.target.value)}
            />
            <button type="submit" className="btn btn--ghost">
              Buscar
            </button>
          </form>

          {allTags.length > 0 && (
            <div className="filters__tags">
              {KINDS.map((kind) => {
                const tags = allTags.filter((t) => t.kind === kind)
                if (tags.length === 0) return null
                return (
                  <div key={kind} className="filters__group">
                    <span className="filters__label">{KIND_LABEL[kind]}</span>
                    <div className="chips">
                      {tags.map((tag) => (
                        <button
                          key={tag.id}
                          type="button"
                          className={filterTagIds.includes(tag.id) ? 'chip chip--on' : 'chip'}
                          aria-pressed={filterTagIds.includes(tag.id)}
                          onClick={() => toggleFilter(tag.id)}
                        >
                          {tag.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {filtering && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                setSearch('')
                setActiveSearch('')
                setFilterTagIds([])
              }}
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </section>

      {error && <Alert kind="error">{error}</Alert>}

      {loading ? (
        <Loading />
      ) : (
        <section className="card">
          <div className="library__header">
            <h2>
              {total} {total === 1 ? 'cancion' : 'canciones'}
              {filtering && <span className="muted"> (filtradas)</span>}
            </h2>
          </div>

          {tracks.length === 0 ? (
            <p className="muted">
              {filtering
                ? 'Ninguna cancion coincide con el filtro.'
                : 'La biblioteca esta vacia. Anade la primera desde el panel de arriba.'}
            </p>
          ) : (
            <ul className="tracklist">
              {tracks.map((track) => (
                <TrackRow
                  key={track.id}
                  track={track}
                  allTags={allTags}
                  isPlaying={playing?.id === track.id}
                  onPlay={(t) => setPlaying((current) => (current?.id === t.id ? null : t))}
                  onChanged={(updated) =>
                    setTracks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
                  }
                  onDeleted={(id) => {
                    setTracks((prev) => prev.filter((t) => t.id !== id))
                    setTotal((n) => Math.max(0, n - 1))
                    setPlaying((current) => (current?.id === id ? null : current))
                  }}
                  onError={setError}
                />
              ))}
            </ul>
          )}
        </section>
      )}

      <Player track={playing} onClose={() => setPlaying(null)} onError={setError} />
    </div>
  )
}
