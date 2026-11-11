import { useEffect, useMemo, useRef, useState } from 'react'

import * as chartsApi from '../api/charts'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { AutoDownloadBar, EstadoDescarga, claveCancion, useAutoDownload, useAlCambiarBusqueda, textoBuscar } from '../components/AutoDownload'
import { PauseIcon, PlayIcon } from '../components/icons'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import { formatDuration } from '../lib/format'
import type { ChartCombined, ChartSource, ChartTrack, SearchCandidate, Version } from '../types/api'

// La sesion elegida, las listas a mano y cuantas sacar, recordadas entre visitas
const CLAVE_SESION = 'charts.sesion'
const CLAVE_FUENTES = 'charts.fuentes'
const CLAVE_CUANTAS = 'charts.cuantas'
const CUANTAS = [50, 100, 200]
const A_MEDIDA = 'medida'

/** Tipos de sesion: cada uno cruza los tops que le pegan. Es lo primero que se
 *  ve, porque es la pregunta que se hace un DJ ("que pongo en el beach club"),
 *  no "que listas de Deezer y Beatport cruzo". */
const SESIONES: { id: string; nombre: string; descripcion: string; fuentes: string[] }[] = [
  {
    id: 'comercial',
    nombre: 'Comercial',
    descripcion: 'Los éxitos que canta todo el mundo: bares, bodas, fiestas. Tops de España, Reino Unido, Alemania y mundial.',
    fuentes: ['deezer:es', 'deezer:world', 'deezer:uk', 'deezer:de'],
  },
  {
    id: 'perreo',
    nombre: 'Reggaeton y latino',
    descripcion: 'Lo que se baila en las discotecas latinas: Club Perreo, Fuego Latino, Reggaeton Hits y el top de España.',
    fuentes: ['deezer:perreo', 'deezer:fuego-latino', 'deezer:reggaeton-hits', 'deezer:es'],
  },
  {
    id: 'beach',
    nombre: 'Beach club',
    descripcion: 'Para la tarde y el atardecer: afro, organic, melodic y deep house, lo que más venden los DJ en Beatport.',
    fuentes: ['beatport:89', 'beatport:93', 'beatport:90', 'beatport:12'],
  },
  {
    id: 'club',
    nombre: 'Club de noche',
    descripcion: 'Tech house y house que pinchan los DJ, cruzado con lo que suena en España para tener temas conocidos.',
    fuentes: ['beatport:top', 'beatport:11', 'beatport:5', 'deezer:es'],
  },
]

type Vista = 'todas' | 'faltan' | 'ambos' | 'cabina' | 'publico'

function enVista(p: ChartTrack, vista: Vista): boolean {
  const ambos = p.groups.length > 1
  if (vista === 'faltan') return !p.already_in_library
  if (vista === 'ambos') return ambos
  if (vista === 'cabina') return !ambos && p.groups.includes('Beatport')
  if (vista === 'publico') return !ambos && p.groups.includes('Deezer')
  return true
}

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
  const [sesion, setSesion] = useState<string | null>(() => leerGuardado<string | null>(CLAVE_SESION, null))
  const [elegidas, setElegidas] = useState<string[]>(() =>
    leerGuardado<string[]>(CLAVE_FUENTES, SESIONES[0].fuentes),
  )
  const [cuantas, setCuantas] = useState<number>(() => leerGuardado(CLAVE_CUANTAS, 100))
  const [verBeatport, setVerBeatport] = useState(false)
  const [resultado, setResultado] = useState<ChartCombined | null>(null)
  // Las listas con las que se ha hecho el resultado que se ve
  const [cruzadas, setCruzadas] = useState<string[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filtro, setFiltro] = useState('')
  const [vista, setVista] = useState<Vista>('todas')

  const auto = useAutoDownload(`charts:${[...cruzadas].sort().join(',')}`, { recordarCrate: false })

  // La cancion con los candidatos abiertos
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
    // Al volver, se ve directamente lo de la ultima vez
    if (sesion) void cruzar(sesion === A_MEDIDA ? elegidas : (SESIONES.find((s) => s.id === sesion)?.fuentes ?? elegidas))
    return () => audio.current?.pause()
    // Solo al entrar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const nombres = useMemo(() => new Map(fuentes.map((f) => [f.id, f])), [fuentes])
  const deezer = fuentes.filter((f) => f.group === 'Deezer')
  const beatport = fuentes.filter((f) => f.group === 'Beatport')
  const reggaeton = fuentes.filter((f) => f.group === 'Reggaeton')
  // Los generos de Beatport elegidos se ven siempre, aunque la lista este plegada
  const beatportVisibles = verBeatport ? beatport : beatport.filter((f) => elegidas.includes(f.id))

  function elegirSesion(id: string) {
    setSesion(id)
    guardar(CLAVE_SESION, id)
    if (id === A_MEDIDA) return
    const lista = SESIONES.find((s) => s.id === id)?.fuentes ?? []
    setElegidas(lista)
    guardar(CLAVE_FUENTES, lista)
    void cruzar(lista)
  }

  function alternar(id: string) {
    const nuevas = elegidas.includes(id) ? elegidas.filter((e) => e !== id) : [...elegidas, id]
    setElegidas(nuevas)
    guardar(CLAVE_FUENTES, nuevas)
  }

  async function cruzar(lista: string[] = elegidas) {
    if (!lista.length) return
    audio.current?.pause()
    setSonando(null)
    setAbierta(null)
    setCargando(true)
    setError(null)
    try {
      setResultado(await chartsApi.combined(lista, cuantas))
      setCruzadas(lista)
      setFiltro('')
      setVista('todas')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las listas.')
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

  // La ultima cancion buscada, para repetirla si cambian version o sitio
  const ultimaBuscada = useRef<[number, ChartTrack] | null>(null)
  useAlCambiarBusqueda(auto, () => {
    if (abierta !== null && ultimaBuscada.current) void buscar(...ultimaBuscada.current)
  })

  async function buscar(indice: number, pista: ChartTrack, version: Version | null = auto.version) {
    ultimaBuscada.current = [indice, pista]
    setAbierta(indice)
    setCandidatos(null)
    setBuscando(true)
    setError(null)
    try {
      const resultado = await tracksApi.previewSearch(pista.title, pista.artist, version, auto.sitio)
      setCandidatos(resultado.candidates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La búsqueda ha fallado.')
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
      setError(err instanceof Error ? err.message : 'No se pudo añadir la canción.')
    } finally {
      setAnadiendo(null)
    }
  }

  const texto = filtro.trim().toLowerCase()
  const items = resultado?.items ?? []
  const visibles = items
    .map((p, indice) => ({ p, indice }))
    .filter(({ p }) => enVista(p, vista))
    .filter(({ p }) => !texto || `${p.title} ${p.artist}`.toLowerCase().includes(texto))
  // Lo que se descarga es lo que se ve
  const aDescargar = visibles.map(({ p }) => p)
  const faltan = items.filter((p) => !p.already_in_library).length
  // Las de reggaeton son de Deezer: lo que escucha el publico, no la cabina
  const dosLados = new Set(cruzadas.map((f) => (f.startsWith('beatport:') ? 'Beatport' : 'Deezer'))).size > 1
  const enAmbos = items.filter((p) => p.groups.length > 1).length
  const sesionVista = SESIONES.find((s) => s.fuentes.join() === cruzadas.join())
  const titulo = sesionVista ? sesionVista.nombre : 'tu selección'
  const nombreTanda = `Lo que suena: ${sesionVista?.nombre ?? cruzadas.map((f) => nombres.get(f)?.name ?? f).join(', ')}`.slice(0, 180)

  const VISTAS: { valor: Vista; nombre: string; titulo: string; cuantas: number }[] = [
    { valor: 'todas', nombre: 'Todas', titulo: 'Toda la lista', cuantas: items.length },
    { valor: 'faltan', nombre: 'Las que me faltan', titulo: 'Las que aún no tienes en la biblioteca', cuantas: faltan },
    ...(dosLados
      ? [
          { valor: 'ambos' as Vista, nombre: 'Suenan en todas partes', titulo: 'La escucha la gente (Deezer) y la pinchan los DJ (Beatport)', cuantas: enAmbos },
          { valor: 'cabina' as Vista, nombre: 'Solo de DJ', titulo: 'Solo en los tops de Beatport', cuantas: items.filter((p) => enVista(p, 'cabina')).length },
          { valor: 'publico' as Vista, nombre: 'Solo del público', titulo: 'Solo en los tops de Deezer', cuantas: items.filter((p) => enVista(p, 'publico')).length },
        ]
      : []),
  ]

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
      <h1>Lo que suena</h1>
      <p className="muted">
        Las canciones de moda para preparar una sesión. Se sacan de los tops de cada día:
        Beatport dice lo que pinchan los DJ y Deezer lo que escucha la gente. Elige el tipo
        de sesión, mira la lista y descárgate las que te falten.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card stack">
        <h2 className="sesiones__titulo">1. ¿Qué sesión preparas?</h2>
        <div className="sesiones">
          {SESIONES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={sesion === s.id ? 'sesion sesion--on' : 'sesion'}
              aria-pressed={sesion === s.id}
              disabled={cargando}
              onClick={() => elegirSesion(s.id)}
            >
              <strong>{s.nombre}</strong>
              <span>{s.descripcion}</span>
            </button>
          ))}
          <button
            type="button"
            className={sesion === A_MEDIDA ? 'sesion sesion--on' : 'sesion'}
            aria-pressed={sesion === A_MEDIDA}
            onClick={() => elegirSesion(A_MEDIDA)}
          >
            <strong>A medida</strong>
            <span>Elige tú las listas: países de Deezer, reggaeton y géneros de Beatport.</span>
          </button>
        </div>

        {sesion === A_MEDIDA && (
          <div className="stack">
            <div className="filters__group">
              <span className="filters__label">Lo que escucha la gente (Deezer)</span>
              <div className="chips">{deezer.map(chip)}</div>
            </div>
            <div className="filters__group">
              <span className="filters__label">Reggaeton y latino (Deezer)</span>
              <div className="chips">{reggaeton.map(chip)}</div>
            </div>
            <div className="filters__group">
              <span className="filters__label">Lo que pinchan los DJ (Beatport)</span>
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
                {cargando ? 'Cargando...' : `Ver la lista (${elegidas.length} ${elegidas.length === 1 ? 'top' : 'tops'})`}
              </button>
              {elegidas.length === 1 && (
                <p className="muted charts__aviso">
                  Con un solo top sale igual que en su web. Lo útil es juntar varios: lo que
                  sale en más de uno es lo que más suena.
                </p>
              )}
            </div>
          </div>
        )}
      </section>

      {cargando && <Loading />}

      {!cargando && !resultado && !sesion && (
        <p className="muted">Elige un tipo de sesión para ver sus canciones.</p>
      )}

      {!cargando && resultado && (
        <section className="card">
          {resultado.errors.map((e) => (
            <Alert key={e.source} kind="error">
              {nombres.get(e.source)?.name ?? e.source}: {e.message}
            </Alert>
          ))}
          <h2 className="sesiones__titulo">2. Las {items.length} que más suenan: {titulo}</h2>
          <p className="muted charts__resumen">
            Arriba, las que salen en más tops y en mejor puesto.
            {dosLados && ' «Suena en todas partes» es que la escucha la gente y además la pinchan los DJ: son las más seguras.'}
            {' '}
            {faltan === 0 ? 'Ya las tienes todas.' : `Te faltan ${faltan}.`}
          </p>

          <div className="chips charts__lados" role="group" aria-label="Qué canciones ver">
            {VISTAS.map((v) => (
              <button
                key={v.valor}
                type="button"
                className={vista === v.valor ? 'chip chip--on' : 'chip'}
                aria-pressed={vista === v.valor}
                title={v.titulo}
                onClick={() => setVista(v.valor)}
              >
                {v.nombre} ({v.cuantas})
              </button>
            ))}
          </div>

          <h2 className="sesiones__titulo">3. Descárgalas</h2>
          <p className="muted charts__resumen">
            Se descargan las que estás viendo ({aDescargar.length}). El servidor las busca una a
            una, así que puedes cerrar la página. También puedes buscar una sola con su botón.
          </p>
          <AutoDownloadBar
            canciones={aDescargar}
            auto={auto}
            nombreTanda={nombreTanda}
            nombreSugerido={sesionVista ? `${sesionVista.nombre} · ${new Date().toLocaleDateString('es-ES', { month: 'short', year: 'numeric' })}` : 'Lo que suena'}
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
          {visibles.length === 0 && <p className="muted">No hay ninguna con este filtro.</p>}
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
                      <span
                        className="badge"
                        title={p.positions
                          .map((pos) => `${nombres.get(pos.source)?.name ?? pos.source}: nº ${pos.position}`)
                          .join('\n')}
                      >
                        {p.positions.length === 1
                          ? `${nombres.get(p.positions[0].source)?.name ?? p.positions[0].source} nº ${p.positions[0].position}`
                          : `en ${p.positions.length} tops · mejor nº ${Math.min(...p.positions.map((x) => x.position))}`}
                      </span>
                      {p.groups.length > 1 && (
                        <span
                          className="badge badge--busy"
                          title="La escucha la gente (Deezer) y la pinchan los DJ (Beatport)"
                        >
                          suena en todas partes
                        </span>
                      )}
                      {p.already_in_library && <span className="badge badge--ok">ya la tienes</span>}
                      <EstadoDescarga estado={auto.estados[claveCancion(p)]} />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={buscando}
                    onClick={() => void buscar(indice, p)}
                  >
                    {buscando && abierta === indice ? 'Buscando...' : textoBuscar(auto)}
                  </button>
                </div>
                {abierta === indice && candidatos !== null && (
                  <SearchCandidates
                    candidates={candidatos}
                    addedIds={anadidos}
                    addingId={anadiendo}
                    onAdd={anadir}
                    version={auto.version}
                    source={auto.sitio}
                    onVersion={(v) => {
                      auto.elegirVersion(v)
                    }}
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
