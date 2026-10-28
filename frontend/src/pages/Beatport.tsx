import { useEffect, useRef, useState } from 'react'

import * as beatportApi from '../api/beatport'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { AutoDownloadBar, EstadoDescarga, claveCancion, useAutoDownload } from '../components/AutoDownload'
import { PauseIcon, PlayIcon } from '../components/icons'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import type { BeatportGenre, BeatportTop, BeatportTrack, SearchCandidate } from '../types/api'

// Genero elegido, recordado entre visitas ('' es el top general)
const CLAVE_GENERO = 'beatport.genero'

/** "2026-10-23" a "23/10/2026", sin pasar por zonas horarias. */
function fecha(iso: string): string {
  const [anio, mes, dia] = iso.slice(0, 10).split('-')
  return dia && mes && anio ? `${dia}/${mes}/${anio}` : iso
}

function generoGuardado(): number | null {
  try {
    const valor = Number(localStorage.getItem(CLAVE_GENERO))
    return valor > 0 ? valor : null
  } catch {
    return null
  }
}

export function BeatportPage() {
  const [generos, setGeneros] = useState<BeatportGenre[]>([])
  const [genero, setGenero] = useState<number | null>(generoGuardado)
  const [top, setTop] = useState<BeatportTop | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filtro, setFiltro] = useState('')

  // Cada genero guarda sus propias tandas, para ver como van al volver
  const auto = useAutoDownload(`beatport:${genero ?? 'top'}`)

  // La cancion con los candidatos de YouTube abiertos
  const [abierta, setAbierta] = useState<number | null>(null)
  const [candidatos, setCandidatos] = useState<SearchCandidate[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [anadidos, setAnadidos] = useState<string[]>([])
  const [anadiendo, setAnadiendo] = useState<string | null>(null)

  // El fragmento de Beatport que esta sonando
  const audio = useRef<HTMLAudioElement | null>(null)
  const [sonando, setSonando] = useState<number | null>(null)

  useEffect(() => {
    beatportApi
      .listGenres()
      .then(setGeneros)
      .catch(() => undefined)
    return () => audio.current?.pause()
  }, [])

  useEffect(() => {
    let vivo = true
    setCargando(true)
    setError(null)
    setAbierta(null)
    setFiltro('')
    beatportApi
      .top100(genero)
      .then((datos) => vivo && setTop(datos))
      .catch((err) => vivo && setError(err instanceof Error ? err.message : 'No se pudo leer Beatport.'))
      .finally(() => vivo && setCargando(false))
    return () => {
      vivo = false
    }
  }, [genero])

  function elegirGenero(id: number | null) {
    setGenero(id)
    try {
      if (id) localStorage.setItem(CLAVE_GENERO, String(id))
      else localStorage.removeItem(CLAVE_GENERO)
    } catch {
      // Sin almacenamiento solo se pierde el recordarlo
    }
  }

  function escuchar(pista: BeatportTrack) {
    if (!pista.sample_url) return
    if (sonando === pista.position) {
      audio.current?.pause()
      setSonando(null)
      return
    }
    audio.current?.pause()
    const nuevo = new Audio(pista.sample_url)
    nuevo.onended = () => setSonando(null)
    audio.current = nuevo
    setSonando(pista.position)
    nuevo.play().catch(() => {
      setSonando(null)
      setError('No se pudo reproducir el fragmento de Beatport.')
    })
  }

  async function buscar(pista: BeatportTrack) {
    setAbierta(pista.position)
    setCandidatos(null)
    setBuscando(true)
    setError(null)
    try {
      const resultado = await tracksApi.previewSearch(pista.title, pista.artist)
      setCandidatos(resultado.candidates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La busqueda ha fallado.')
    } finally {
      setBuscando(false)
    }
  }

  async function anadir(candidate: SearchCandidate) {
    setAnadiendo(candidate.video_id)
    setError(null)
    try {
      const nueva = await tracksApi.addFromUrl(candidate.url, auto.crateElegido)
      setAnadidos((prev) => [...prev, candidate.video_id])
      return nueva
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAnadiendo(null)
    }
  }

  const texto = filtro.trim().toLowerCase()
  const pistas = (top?.items ?? []).filter(
    (p) =>
      !texto ||
      `${p.title} ${p.artist} ${p.remixers ?? ''} ${p.label ?? ''}`.toLowerCase().includes(texto),
  )
  const nombreGenero = generos.find((g) => g.id === genero)?.name ?? top?.genre?.name

  return (
    <div className="stack">
      <h1>Beatport</h1>
      <p className="muted">
        Lo más vendido en Beatport, la tienda donde compran música la mayoría de DJs.
        Escucha el fragmento, y si te interesa búscalo en YouTube para bajarlo.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card">
        <div className="beatport__filtros">
          <label className="field">
            <span>Género</span>
            <select
              value={genero ?? ''}
              onChange={(e) => elegirGenero(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Top 100 general</option>
              {generos.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Buscar en la lista</span>
            <input
              type="search"
              value={filtro}
              placeholder="Título, artista o sello..."
              onChange={(e) => setFiltro(e.target.value)}
            />
          </label>
        </div>

        {cargando ? (
          <Loading />
        ) : top && top.items.length > 0 ? (
          <>
            <AutoDownloadBar
              canciones={top.items}
              auto={auto}
              nombreTanda={`Beatport: ${nombreGenero ?? 'Top 100'}`}
              nombreSugerido={`Beatport ${nombreGenero ?? 'Top 100'}`}
            />
            {pistas.length === 0 && <p className="muted">Ninguna coincide con la búsqueda.</p>}
            <ul className="detected">
              {pistas.map((p) => (
                <li key={p.position} className="detected__item">
                  <div className="detected__row">
                    <span className="beatport__pos">{p.position}</span>
                    {p.image_url && (
                      <img className="beatport__cover" src={p.image_url} alt="" loading="lazy" />
                    )}
                    <button
                      type="button"
                      className="track__play"
                      disabled={!p.sample_url}
                      aria-label={sonando === p.position ? 'Parar el fragmento' : 'Escuchar el fragmento'}
                      title="Fragmento de Beatport"
                      onClick={() => escuchar(p)}
                    >
                      {sonando === p.position ? <PauseIcon /> : <PlayIcon />}
                    </button>
                    <div className="track__info">
                      <div className="track__title">
                        {p.name}
                        {p.mix && <span className="muted"> ({p.mix})</span>}
                      </div>
                      <div className="track__meta">
                        <span>{p.artist}</span>
                        {p.remixers && <span>· remix {p.remixers}</span>}
                        {p.label && <span>· {p.label}</span>}
                        {p.bpm && <span>· {p.bpm} BPM</span>}
                        {p.key && <span>· {p.key}</span>}
                        {p.length && <span>· {p.length}</span>}
                        {p.release_date && (
                          <span title="Fecha de publicación en Beatport">· {fecha(p.release_date)}</span>
                        )}
                        {!genero && p.genre && <span className="badge">{p.genre}</span>}
                        {p.already_in_library && (
                          <span className="badge badge--ok">ya en la biblioteca</span>
                        )}
                        <EstadoDescarga estado={auto.estados[claveCancion(p)]} />
                      </div>
                    </div>
                    <a
                      className="btn btn--ghost"
                      href={p.beatport_url}
                      target="_blank"
                      rel="noreferrer"
                      title="Ver en Beatport"
                    >
                      Beatport
                    </a>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={buscando}
                      onClick={() => void buscar(p)}
                    >
                      {buscando && abierta === p.position ? 'Buscando...' : 'Buscar en YouTube'}
                    </button>
                  </div>
                  {abierta === p.position && candidatos !== null && (
                    <SearchCandidates
                      candidates={candidatos}
                      addedIds={anadidos}
                      addingId={anadiendo}
                      onAdd={anadir}
                    />
                  )}
                </li>
              ))}
            </ul>
          </>
        ) : (
          !error && <Alert kind="info">Beatport no ha devuelto ninguna canción.</Alert>
        )}
      </section>
    </div>
  )
}
