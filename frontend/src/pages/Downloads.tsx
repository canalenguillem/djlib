import { useCallback, useEffect, useMemo, useState } from 'react'

import * as cratesApi from '../api/crates'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { Player } from '../components/Player'
import { PauseIcon, PlayIcon } from '../components/icons'
import { formatDuration } from '../lib/format'
import { guardarFichero, nombreCancion } from '../lib/guardar'
import type { CrateSummary, Track, TrackFilters } from '../types/api'

const POR_PAGINA = 50
// Lo mas que el servidor mete en un zip, y lo mas que da de una vez
const MAXIMO = 500

/** Llevarse a casa lo que ya esta en el servidor: se busca, se marca y se baja
 *  todo junto en un zip. */
export function DownloadsPage() {
  const [search, setSearch] = useState('')
  const [buscado, setBuscado] = useState('')
  const [crates, setCrates] = useState<CrateSummary[]>([])
  const [crateId, setCrateId] = useState<number | null>(null)
  const [pagina, setPagina] = useState(0)
  const [tracks, setTracks] = useState<Track[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Por id y en el orden en que se marcan, que es el orden dentro del zip
  const [elegidas, setElegidas] = useState<Map<number, Track>>(new Map())
  const [ocupado, setOcupado] = useState(false)
  const [playing, setPlaying] = useState<Track | null>(null)
  const [bajando, setBajando] = useState<number | null>(null)

  // Dentro de un crate, en el orden del set; buscando, por titulo
  const filtros = useMemo<TrackFilters>(
    () => ({
      search: buscado,
      crateId: crateId ?? undefined,
      status: 'ready',
      sort: crateId ? 'crate' : buscado ? 'title' : 'recent',
    }),
    [buscado, crateId],
  )
  const crate = crates.find((c) => c.id === crateId) ?? null

  useEffect(() => {
    cratesApi
      .listCrates()
      .then(setCrates)
      .catch(() => undefined)
  }, [])

  const cargar = useCallback(async () => {
    try {
      const page = await tracksApi.listTracks({
        ...filtros,
        limit: POR_PAGINA,
        offset: pagina * POR_PAGINA,
      })
      setTracks(page.items)
      setTotal(page.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo buscar en el servidor.')
    } finally {
      setLoading(false)
    }
  }, [filtros, pagina])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const paginas = Math.ceil(total / POR_PAGINA)
  const todasMarcadas = tracks.length > 0 && tracks.every((t) => elegidas.has(t.id))

  function marcar(lista: Track[], si: boolean) {
    setElegidas((prev) => {
      const nuevas = new Map(prev)
      for (const t of lista) {
        if (si) nuevas.set(t.id, t)
        else nuevas.delete(t.id)
      }
      return nuevas
    })
  }

  async function marcarEncontradas() {
    setOcupado(true)
    try {
      const page = await tracksApi.listTracks({ ...filtros, limit: MAXIMO })
      marcar(page.items, true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron marcar.')
    } finally {
      setOcupado(false)
    }
  }

  async function descargar() {
    setOcupado(true)
    setError(null)
    try {
      const blob = await tracksApi.exportTracks([...elegidas.keys()])
      // Si lo marcado es justo un crate, el zip se llama como el
      const soloElCrate =
        crate && elegidas.size === total && tracks.every((t) => elegidas.has(t.id)) && !buscado
      guardarFichero(blob, soloElCrate ? `${crate.name}.zip` : `djwill-${elegidas.size}-canciones.zip`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo preparar el zip.')
    } finally {
      setOcupado(false)
    }
  }

  async function bajarUna(track: Track) {
    setBajando(track.id)
    setError(null)
    try {
      const blob = await tracksApi.fetchTrackMp3(track.id)
      guardarFichero(blob, nombreCancion(track, blob))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo descargar.')
    } finally {
      setBajando(null)
    }
  }

  const demasiadas = elegidas.size > MAXIMO

  return (
    <div className="stack">
      <h1>Descargas</h1>
      <p className="muted">
        Busca entre lo que ya está en el servidor, marca las canciones y bájalas
        todas juntas en un .zip, en mp3.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card stack">
        <form
          className="filters__search descargas__buscar"
          onSubmit={(e) => {
            e.preventDefault()
            setBuscado(search.trim())
            setPagina(0)
          }}
        >
          <input
            type="search"
            value={search}
            placeholder="Buscar por título o artista..."
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            aria-label="Crate"
            value={crateId ?? ''}
            onChange={(e) => {
              setCrateId(e.target.value ? Number(e.target.value) : null)
              setPagina(0)
            }}
          >
            <option value="">Todos los crates</option>
            {crates.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.track_count})
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn--ghost">
            Buscar
          </button>
        </form>

        <div className="descargas__barra">
          <span className="muted">
            {elegidas.size === 0
              ? 'Ninguna marcada'
              : `${elegidas.size} ${elegidas.size === 1 ? 'marcada' : 'marcadas'}`}
          </span>
          {total > tracks.length && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={ocupado}
              onClick={() => void marcarEncontradas()}
            >
              Marcar las {Math.min(total, MAXIMO)} encontradas
            </button>
          )}
          {elegidas.size > 0 && (
            <button type="button" className="btn btn--ghost" onClick={() => setElegidas(new Map())}>
              Desmarcar todas
            </button>
          )}
          <button
            type="button"
            className="btn btn--primary"
            disabled={ocupado || elegidas.size === 0 || demasiadas}
            onClick={() => void descargar()}
          >
            {ocupado ? 'Preparando...' : 'Descargar .zip'}
          </button>
        </div>
        {demasiadas && (
          <p className="muted">Como mucho {MAXIMO} canciones por zip: desmarca algunas.</p>
        )}
      </section>

      <section className="card">
        {loading ? (
          <Loading />
        ) : tracks.length === 0 ? (
          <p className="muted">
            {buscado || crate
              ? 'No hay nada descargado que coincida.'
              : 'Todavía no hay canciones descargadas.'}
          </p>
        ) : (
          <>
            <label className="check descargas__todas">
              <input
                type="checkbox"
                checked={todasMarcadas}
                onChange={() => marcar(tracks, !todasMarcadas)}
              />
              {crate && !buscado
                ? `${total} en «${crate.name}»`
                : buscado || crate
                  ? `${total} encontradas`
                  : `${total} en el servidor`}
              {paginas > 1 && <span className="muted"> · marcar las de esta página</span>}
            </label>
            <ul className="detected">
              {tracks.map((t) => (
                <li key={t.id} className="detected__item">
                  <div className="detected__row">
                    <input
                      type="checkbox"
                      aria-label={`Marcar ${t.title}`}
                      checked={elegidas.has(t.id)}
                      onChange={(e) => marcar([t], e.target.checked)}
                    />
                    <button
                      type="button"
                      className="track__play"
                      aria-label={playing?.id === t.id ? 'Parar' : 'Escuchar'}
                      onClick={() => setPlaying((actual) => (actual?.id === t.id ? null : t))}
                    >
                      {playing?.id === t.id ? <PauseIcon /> : <PlayIcon />}
                    </button>
                    <div className="track__info">
                      <div className="track__title">{t.title}</div>
                      <div className="track__meta">
                        {t.artist_text && <span>{t.artist_text}</span>}
                        {t.duration_seconds !== null && <span>· {formatDuration(t.duration_seconds)}</span>}
                        {t.bpm && <span>· {t.bpm} BPM</span>}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={bajando !== null}
                      title="Bajar solo esta, en mp3"
                      onClick={() => void bajarUna(t)}
                    >
                      {bajando === t.id ? 'Bajando...' : 'Descargar'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
            {paginas > 1 && (
              <nav className="pager" aria-label="Paginas">
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={pagina === 0}
                  onClick={() => setPagina(pagina - 1)}
                >
                  ← Anterior
                </button>
                <span className="muted">
                  Página {pagina + 1} de {paginas}
                </span>
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={pagina >= paginas - 1}
                  onClick={() => setPagina(pagina + 1)}
                >
                  Siguiente →
                </button>
              </nav>
            )}
          </>
        )}
      </section>

      <Player track={playing} onClose={() => setPlaying(null)} onError={setError} />
    </div>
  )
}
