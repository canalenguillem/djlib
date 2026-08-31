import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import * as cratesApi from '../api/crates'
import * as tagsApi from '../api/tags'
import * as tracksApi from '../api/tracks'
import { AddTrackPanel } from '../components/AddTrackPanel'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { Player } from '../components/Player'
import { TrackRow } from '../components/TrackRow'
import type { Tag, TagKind, Track, TrackSort } from '../types/api'

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
  const [energyMin, setEnergyMin] = useState<number | null>(null)
  const [bpmMin, setBpmMin] = useState('')
  const [bpmMax, setBpmMax] = useState('')
  const [bpmAplicado, setBpmAplicado] = useState<[string, string]>(['', ''])
  const [sort, setSort] = useState<TrackSort>('recent')
  const [playing, setPlaying] = useState<Track | null>(null)
  const [crateName, setCrateName] = useState('')
  const [savingCrate, setSavingCrate] = useState(false)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try {
      const page = await tracksApi.listTracks({
        search: activeSearch,
        tagIds: filterTagIds,
        energyMin: energyMin ?? undefined,
        bpmMin: bpmAplicado[0] ? Number(bpmAplicado[0]) : undefined,
        bpmMax: bpmAplicado[1] ? Number(bpmAplicado[1]) : undefined,
        sort,
      })
      setTracks(page.items)
      setTotal(page.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la biblioteca.')
    } finally {
      setLoading(false)
    }
  }, [activeSearch, filterTagIds, energyMin, bpmAplicado, sort])

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

  const filtering =
    activeSearch !== '' ||
    filterTagIds.length > 0 ||
    energyMin !== null ||
    bpmAplicado[0] !== '' ||
    bpmAplicado[1] !== ''
  // Solo tiene sentido guardar canciones utilizables: las que estan a medias
  // de descargar no se pueden pinchar.
  const readyTracks = tracks.filter((t) => t.status === 'ready')

  async function saveAsCrate() {
    if (!crateName.trim()) return
    setSavingCrate(true)
    setError(null)
    try {
      const crate = await cratesApi.createCrate(
        crateName.trim(),
        readyTracks.map((t) => t.id),
      )
      navigate(`/crates/${crate.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar el crate.')
      setSavingCrate(false)
    }
  }

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

          <div className="filters__group">
            <span className="filters__label">Energia</span>
            <div className="chips">
              {[1, 2, 3, 4, 5].map((nivel) => (
                <button
                  key={nivel}
                  type="button"
                  className={energyMin === nivel ? 'chip chip--on' : 'chip'}
                  aria-pressed={energyMin === nivel}
                  title={`Solo temas de energia ${nivel} o mas`}
                  onClick={() => setEnergyMin((actual) => (actual === nivel ? null : nivel))}
                >
                  {nivel}+
                </button>
              ))}
            </div>
            <span className="filters__label">BPM</span>
            <form
              className="filters__bpm"
              onSubmit={(e) => {
                e.preventDefault()
                setBpmAplicado([bpmMin, bpmMax])
              }}
            >
              <input
                type="number"
                min={20}
                max={400}
                placeholder="desde"
                value={bpmMin}
                onChange={(e) => setBpmMin(e.target.value)}
              />
              <input
                type="number"
                min={20}
                max={400}
                placeholder="hasta"
                value={bpmMax}
                onChange={(e) => setBpmMax(e.target.value)}
              />
              <button type="submit" className="btn btn--ghost">
                Aplicar
              </button>
            </form>
            <span className="filters__label">Orden</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as TrackSort)}>
              <option value="recent">Mas recientes</option>
              <option value="energy_asc">Energia: de menos a mas</option>
              <option value="energy">Energia: de mas a menos</option>
              <option value="bpm">BPM: de menos a mas</option>
              <option value="title">Titulo</option>
            </select>
          </div>

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

          <div className="filters__footer">
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
            {readyTracks.length > 0 && (
              <form
                className="inline-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  void saveAsCrate()
                }}
              >
                <input
                  type="text"
                  value={crateName}
                  placeholder={`Guardar estas ${readyTracks.length} como crate...`}
                  onChange={(e) => setCrateName(e.target.value)}
                />
                <button
                  type="submit"
                  className="btn btn--ghost"
                  disabled={savingCrate || !crateName.trim()}
                >
                  {savingCrate ? 'Guardando...' : 'Guardar crate'}
                </button>
              </form>
            )}
          </div>
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
