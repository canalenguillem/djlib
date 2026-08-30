import { useCallback, useEffect, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import * as cratesApi from '../api/crates'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { Player } from '../components/Player'
import { PlayIcon, PauseIcon } from '../components/icons'
import { formatTotal } from '../lib/duration'
import { formatDuration } from '../lib/format'
import type { Crate, Track } from '../types/api'

export function CrateDetailPage() {
  const { crateId } = useParams()
  const navigate = useNavigate()
  const id = Number(crateId)

  const [crate, setCrate] = useState<Crate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [playing, setPlaying] = useState<Track | null>(null)
  const [dragged, setDragged] = useState<number | null>(null)

  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')

  const [search, setSearch] = useState('')
  const [results, setResults] = useState<Track[] | null>(null)

  const load = useCallback(async () => {
    try {
      const encontrado = await cratesApi.getCrate(id)
      setCrate(encontrado)
      setName(encontrado.name)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar el crate.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  async function guard(accion: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await accion()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La operacion ha fallado.')
    } finally {
      setBusy(false)
    }
  }

  /** Manda el orden completo, que es lo que espera el servidor. */
  async function aplicarOrden(ordenados: Track[]) {
    if (!crate) return
    const previo = crate
    setCrate({ ...crate, tracks: ordenados }) // respuesta inmediata al arrastrar
    try {
      setCrate(await cratesApi.reorderCrate(id, ordenados.map((t) => t.id)))
    } catch (err) {
      setCrate(previo) // si falla, se deshace
      setError(err instanceof Error ? err.message : 'No se pudo reordenar.')
    }
  }

  function mover(desde: number, hasta: number) {
    if (!crate || hasta < 0 || hasta >= crate.tracks.length) return
    const ordenados = [...crate.tracks]
    const [movida] = ordenados.splice(desde, 1)
    ordenados.splice(hasta, 0, movida)
    void aplicarOrden(ordenados)
  }

  function handleDrop(event: DragEvent, hasta: number) {
    event.preventDefault()
    if (dragged === null || dragged === hasta) return
    mover(dragged, hasta)
    setDragged(null)
  }

  async function buscar(event: FormEvent) {
    event.preventDefault()
    if (!search.trim()) return
    await guard(async () => {
      const pagina = await tracksApi.listTracks({ search: search.trim(), status: 'ready' })
      const yaEstan = new Set(crate?.tracks.map((t) => t.id))
      setResults(pagina.items.filter((t) => !yaEstan.has(t.id)))
    })
  }

  if (loading) return <Loading />
  if (!crate) return <Alert kind="error">{error ?? 'Crate no encontrado.'}</Alert>

  return (
    <div className="stack">
      <Link to="/crates" className="muted">
        ← Crates
      </Link>

      {editing ? (
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault()
            void guard(async () => {
              setCrate(await cratesApi.updateCrate(id, { name: name.trim() }))
              setEditing(false)
            })
          }}
        >
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          <button type="submit" className="btn btn--primary" disabled={busy}>
            Guardar
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setEditing(false)}>
            Cancelar
          </button>
        </form>
      ) : (
        <h1>{crate.name}</h1>
      )}

      <p className="muted">
        {crate.track_count} {crate.track_count === 1 ? 'cancion' : 'canciones'}
        {crate.track_count > 0 && ` · ${formatTotal(crate.total_seconds)}`}
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <div className="crate__actions">
        <button type="button" className="btn btn--ghost" onClick={() => setEditing((v) => !v)}>
          Renombrar
        </button>
        <button
          type="button"
          className="btn btn--ghost btn--danger"
          disabled={busy}
          onClick={() =>
            guard(async () => {
              await cratesApi.deleteCrate(id)
              navigate('/crates', { replace: true })
            })
          }
        >
          Borrar crate
        </button>
      </div>

      <section className="card">
        <h2>Orden del set</h2>
        {crate.tracks.length === 0 ? (
          <p className="muted">
            Vacio. Busca canciones abajo, o filtra la biblioteca y guarda el resultado
            como crate desde alli.
          </p>
        ) : (
          <>
            <p className="muted hint">
              Arrastra para reordenar, o usa las flechas. En el movil, las flechas.
            </p>
            <ol className="setlist">
              {crate.tracks.map((track, indice) => (
                <li
                  key={track.id}
                  className={`setitem ${dragged === indice ? 'setitem--dragging' : ''}`}
                  draggable
                  onDragStart={() => setDragged(indice)}
                  onDragEnd={() => setDragged(null)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => handleDrop(e, indice)}
                >
                  <span className="setitem__pos">{indice + 1}</span>
                  <button
                    type="button"
                    className="track__play"
                    aria-label={`Reproducir ${track.title}`}
                    onClick={() =>
                      setPlaying((actual) => (actual?.id === track.id ? null : track))
                    }
                  >
                    {playing?.id === track.id ? <PauseIcon /> : <PlayIcon />}
                  </button>
                  <div className="track__info">
                    <div className="track__title">{track.title}</div>
                    <div className="track__meta">
                      <span>{track.artist_text ?? 'Artista desconocido'}</span>
                      <span>·</span>
                      <span>{formatDuration(track.duration_seconds)}</span>
                      {track.tags.map((tag) => (
                        <span key={tag.id} className={`chip chip--${tag.kind}`}>
                          {tag.name}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="setitem__controls">
                    <button
                      type="button"
                      className="btn btn--ghost"
                      aria-label="Subir"
                      disabled={indice === 0}
                      onClick={() => mover(indice, indice - 1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      aria-label="Bajar"
                      disabled={indice === crate.tracks.length - 1}
                      onClick={() => mover(indice, indice + 1)}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--danger"
                      disabled={busy}
                      onClick={() =>
                        guard(async () => {
                          setCrate(await cratesApi.removeTrackFromCrate(id, track.id))
                        })
                      }
                    >
                      Quitar
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </section>

      <section className="card">
        <h2>Anadir canciones</h2>
        <form className="inline-form" onSubmit={buscar}>
          <input
            type="search"
            value={search}
            placeholder="Buscar en la biblioteca..."
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn btn--ghost" disabled={busy}>
            Buscar
          </button>
        </form>

        {results !== null &&
          (results.length === 0 ? (
            <p className="muted">Nada que anadir: o no hay coincidencias o ya estan todas.</p>
          ) : (
            <ul className="tracklist">
              {results.map((track) => (
                <li key={track.id} className="track">
                  <div className="track__main">
                    <div className="track__info">
                      <div className="track__title">{track.title}</div>
                      <div className="track__meta">
                        <span>{track.artist_text ?? 'Artista desconocido'}</span>
                        <span>·</span>
                        <span>{formatDuration(track.duration_seconds)}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={busy}
                      onClick={() =>
                        guard(async () => {
                          setCrate(await cratesApi.addTrackToCrate(id, track.id))
                          setResults((prev) => prev?.filter((t) => t.id !== track.id) ?? null)
                        })
                      }
                    >
                      Anadir
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ))}
      </section>

      <Player track={playing} onClose={() => setPlaying(null)} onError={setError} />
    </div>
  )
}
