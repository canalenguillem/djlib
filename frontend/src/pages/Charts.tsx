import { useEffect, useMemo, useRef, useState } from 'react'

import * as chartsApi from '../api/charts'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { AutoDownloadBar, EstadoDescarga, claveCancion, useAutoDownload } from '../components/AutoDownload'
import { PauseIcon, PlayIcon } from '../components/icons'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import { formatDuration } from '../lib/format'
import type { ChartCombined, ChartSource, ChartTrack, SearchCandidate } from '../types/api'

// Listas elegidas y cuantas sacar, recordadas entre visitas
const CLAVE_FUENTES = 'charts.fuentes'
const CLAVE_CUANTAS = 'charts.cuantas'
const CUANTAS = [50, 100, 200]

/** Combinaciones de partida segun el tipo de bolo. Son solo un atajo: luego
 *  se marca o desmarca lo que se quiera. */
const ATAJOS: { nombre: string; fuentes: string[] }[] = [
  { nombre: 'Comercial', fuentes: ['deezer:es', 'deezer:world', 'deezer:uk', 'deezer:de'] },
  { nombre: 'Beach club', fuentes: ['beatport:89', 'beatport:93', 'beatport:90', 'beatport:12'] },
  { nombre: 'Club', fuentes: ['beatport:top', 'beatport:11', 'beatport:5', 'deezer:es'] },
]

function leerGuardado<T>(clave: string, porDefecto: T): T {
  try {
    const valor = localStorage.getItem(clave)
    return valor === null ? porDefecto : (JSON.parse(valor) as T)
  } catch {
    return porDefecto
  }
}

function guardar(clave: string, valor: unknown) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    // Sin almacenamiento solo se pierde recordarlo
  }
}

export function ChartsPage() {
  const [fuentes, setFuentes] = useState<ChartSource[]>([])
  const [elegidas, setElegidas] = useState<string[]>(() =>
    leerGuardado<string[]>(CLAVE_FUENTES, ATAJOS[0].fuentes),
  )
  const [cuantas, setCuantas] = useState<number>(() => leerGuardado(CLAVE_CUANTAS, 100))
  const [verBeatport, setVerBeatport] = useState(false)
  const [resultado, setResultado] = useState<ChartCombined | null>(null)
  // Las listas con las que se ha hecho el resultado que se ve
  const [cruzadas, setCruzadas] = useState<string[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filtro, setFiltro] = useState('')

  const auto = useAutoDownload(`charts:${[...cruzadas].sort().join(',')}`)

  // La cancion con los candidatos de YouTube abiertos
  const [abierta, setAbierta] = useState<number | null>(null)
  const [candidatos, setCandidatos] = useState<SearchCandidate[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [anadidos, setAnadidos] = useState<string[]>([])
  const [anadiendo, setAnadiendo] = useState<string | null>(null)

  const audio = useRef<HTMLAudioElement | null>(null)
  const [sonando, setSonando] = useState<number | null>(null)

  useEffect(() => {
    chartsApi
      .listSources()
      .then(setFuentes)
      .catch((err) => setError(err instanceof Error ? err.message : 'No se pudieron cargar las listas.'))
    return () => audio.current?.pause()
  }, [])

  const nombres = useMemo(() => new Map(fuentes.map((f) => [f.id, f])), [fuentes])
  const deezer = fuentes.filter((f) => f.group === 'Deezer')
  const beatport = fuentes.filter((f) => f.group === 'Beatport')
  // Los generos de Beatport elegidos se ven siempre, aunque la lista este plegada
  const beatportVisibles = verBeatport ? beatport : beatport.filter((f) => elegidas.includes(f.id))

  function cambiarElegidas(nuevas: string[]) {
    setElegidas(nuevas)
    guardar(CLAVE_FUENTES, nuevas)
  }

  function alternar(id: string) {
    cambiarElegidas(elegidas.includes(id) ? elegidas.filter((e) => e !== id) : [...elegidas, id])
  }

  async function cruzar() {
    audio.current?.pause()
    setSonando(null)
    setAbierta(null)
    setCargando(true)
    setError(null)
    try {
      setResultado(await chartsApi.combined(elegidas, cuantas))
      setCruzadas(elegidas)
      setFiltro('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cruzar las listas.')
    } finally {
      setCargando(false)
    }
  }

  function escuchar(indice: number, pista: ChartTrack) {
    if (!pista.sample_url) return
    if (sonando === indice) {
      audio.current?.pause()
      setSonando(null)
      return
    }
    audio.current?.pause()
    const nuevo = new Audio(pista.sample_url)
    nuevo.onended = () => setSonando(null)
    audio.current = nuevo
    setSonando(indice)
    nuevo.play().catch(() => {
      setSonando(null)
      setError('No se pudo reproducir el fragmento.')
    })
  }

  async function buscar(indice: number, pista: ChartTrack) {
    setAbierta(indice)
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
  const items = resultado?.items ?? []
  const visibles = items
    .map((p, indice) => ({ p, indice }))
    .filter(({ p }) => !texto || `${p.title} ${p.artist}`.toLowerCase().includes(texto))
  const faltan = items.filter((p) => !p.already_in_library).length
  const nombreTanda = `Combinar: ${cruzadas.map((f) => nombres.get(f)?.name ?? f).join(', ')}`.slice(0, 180)

  function chip(f: ChartSource) {
    const on = elegidas.includes(f.id)
    return (
      <button
        key={f.id}
        type="button"
        className={on ? 'chip chip--on' : 'chip'}
        aria-pressed={on}
        onClick={() => alternar(f.id)}
      >
        {f.name}
      </button>
    )
  }

  return (
    <div className="stack">
      <h1>Combinar tops</h1>
      <p className="muted">
        Cruza varios tops en una sola lista, sin repetir: sale antes lo que está en más
        listas y más arriba. Beatport dice qué suena en las cabinas; Deezer, qué escucha
        el público de cada país.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card stack">
        <div className="filters__group">
          <span className="filters__label">Atajos</span>
          <div className="chips">
            {ATAJOS.map((a) => (
              <button
                key={a.nombre}
                type="button"
                className="chip"
                title={a.fuentes.map((f) => nombres.get(f)?.name ?? f).join(', ')}
                onClick={() => cambiarElegidas(a.fuentes)}
              >
                {a.nombre}
              </button>
            ))}
          </div>
        </div>

        <div className="filters__group">
          <span className="filters__label">Deezer</span>
          <div className="chips">{deezer.map(chip)}</div>
        </div>

        <div className="filters__group">
          <span className="filters__label">Beatport</span>
          <div className="chips">
            {beatportVisibles.map(chip)}
            <button type="button" className="btn btn--ghost" onClick={() => setVerBeatport((v) => !v)}>
              {verBeatport ? 'Ver menos' : `Ver los ${beatport.length} géneros`}
            </button>
          </div>
        </div>

        <div className="charts__acciones">
          <label className="field">
            <span>Cuántas</span>
            <select
              value={cuantas}
              onChange={(e) => {
                setCuantas(Number(e.target.value))
                guardar(CLAVE_CUANTAS, Number(e.target.value))
              }}
            >
              {CUANTAS.map((n) => (
                <option key={n} value={n}>
                  Las {n} primeras
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn btn--primary"
            disabled={cargando || elegidas.length === 0}
            onClick={() => void cruzar()}
          >
            {cargando ? 'Cruzando...' : `Cruzar ${elegidas.length} ${elegidas.length === 1 ? 'lista' : 'listas'}`}
          </button>
        </div>
      </section>

      {cargando && <Loading />}

      {!cargando && resultado && (
        <section className="card">
          {resultado.errors.map((e) => (
            <Alert key={e.source} kind="error">
              {nombres.get(e.source)?.name ?? e.source}: {e.message}
            </Alert>
          ))}
          <p className="muted">
            {items.length} canciones, {items.length - faltan} ya en la biblioteca.
          </p>
          <AutoDownloadBar
            canciones={items}
            auto={auto}
            nombreTanda={nombreTanda}
            nombreSugerido="Top combinado"
          />
          <label className="field charts__filtro">
            <span>Buscar en la lista</span>
            <input
              type="search"
              value={filtro}
              placeholder="Título o artista..."
              onChange={(e) => setFiltro(e.target.value)}
            />
          </label>
          {visibles.length === 0 && <p className="muted">Ninguna coincide con la búsqueda.</p>}
          <ul className="detected">
            {visibles.map(({ p, indice }) => (
              <li key={indice} className="detected__item">
                <div className="detected__row">
                  <span className="beatport__pos">{indice + 1}</span>
                  {p.image_url && <img className="beatport__cover" src={p.image_url} alt="" loading="lazy" />}
                  <button
                    type="button"
                    className="track__play"
                    disabled={!p.sample_url}
                    aria-label={sonando === indice ? 'Parar el fragmento' : 'Escuchar el fragmento'}
                    onClick={() => escuchar(indice, p)}
                  >
                    {sonando === indice ? <PauseIcon /> : <PlayIcon />}
                  </button>
                  <div className="track__info">
                    <div className="track__title">
                      {p.name}
                      {p.mix && <span className="muted"> ({p.mix})</span>}
                    </div>
                    <div className="track__meta">
                      <span>{p.artist}</span>
                      {p.bpm && <span>· {p.bpm} BPM</span>}
                      {p.key && <span>· {p.key}</span>}
                      {p.duration_seconds !== null && <span>· {formatDuration(p.duration_seconds)}</span>}
                      {p.positions.map((pos) => (
                        <span key={pos.source} className="badge" title={nombres.get(pos.source)?.group}>
                          {nombres.get(pos.source)?.name ?? pos.source} #{pos.position}
                        </span>
                      ))}
                      {p.already_in_library && <span className="badge badge--ok">ya en la biblioteca</span>}
                      <EstadoDescarga estado={auto.estados[claveCancion(p)]} />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={buscando}
                    onClick={() => void buscar(indice, p)}
                  >
                    {buscando && abierta === indice ? 'Buscando...' : 'Buscar en YouTube'}
                  </button>
                </div>
                {abierta === indice && candidatos !== null && (
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
        </section>
      )}
    </div>
  )
}
