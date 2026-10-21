import { useCallback, useEffect, useRef, useState } from 'react'

import * as cratesApi from '../api/crates'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { NextIcon, PauseIcon, PlayIcon, PrevIcon, ShuffleIcon } from '../components/icons'
import { formatClock } from '../lib/audioEngine'
import { useCrates } from '../lib/crates'
import { formatDuration } from '../lib/format'
import type { Crate, Track } from '../types/api'

// El ultimo crate escuchado, para volver directamente a el
const CLAVE_CRATE = 'djlib.escuchar_crate'
// Con mas de esto ya sonado, "anterior" vuelve al principio de la cancion,
// como en cualquier reproductor
const REINICIAR_SI_PASADO = 3

function crateGuardado(): number | null {
  try {
    const valor = Number(localStorage.getItem(CLAVE_CRATE))
    return valor > 0 ? valor : null
  } catch {
    return null
  }
}

/** Orden aleatorio que empieza por `primera`, para no cortar la que suena. */
function barajar(cantidad: number, primera: number): number[] {
  const resto = Array.from({ length: cantidad }, (_, i) => i).filter((i) => i !== primera)
  for (let i = resto.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[resto[i], resto[j]] = [resto[j], resto[i]]
  }
  return [primera, ...resto]
}

/** Reproductor de crates para el movil.
 *
 *  El audio sigue con la pantalla apagada y se controla desde la pantalla de
 *  bloqueo y la notificacion (Media Session). Los mp3 piden la cabecera de
 *  autenticacion, asi que se bajan enteros como blob; la siguiente se baja
 *  mientras suena la actual, para que al terminar empiece sin esperar aunque
 *  el navegador este en segundo plano.
 */
export function ListenPage() {
  const crates = useCrates()
  const [crateId, setCrateId] = useState<number | null>(crateGuardado)
  const [crate, setCrate] = useState<Crate | null>(null)
  const [error, setError] = useState<string | null>(null)

  // `orden` son posiciones en crate.tracks; `actual`, el puesto en `orden`
  const [orden, setOrden] = useState<number[]>([])
  const [actual, setActual] = useState<number | null>(null)
  const [aleatorio, setAleatorio] = useState(false)
  const [sonando, setSonando] = useState(false)
  const [cargando, setCargando] = useState(false)
  const [posicion, setPosicion] = useState(0)
  const [duracion, setDuracion] = useState(0)

  const audio = useRef<HTMLAudioElement>(null)
  // Audio ya bajado, por id de cancion: la actual y la siguiente
  const blobs = useRef(new Map<number, Promise<string>>())

  const pistas = crate?.tracks ?? []
  const pista = actual !== null && orden.length ? pistas[orden[actual]] : null

  // --- Carga del crate ------------------------------------------------------

  useEffect(() => {
    if (crateId === null) return
    let vivo = true
    setError(null)
    cratesApi
      .getCrate(crateId)
      .then((encontrado) => {
        if (!vivo) return
        setCrate(encontrado)
        setOrden(encontrado.tracks.map((_, i) => i))
        setActual(null)
      })
      .catch((err) => vivo && setError(err instanceof Error ? err.message : 'No se pudo cargar el crate.'))
    return () => {
      vivo = false
    }
  }, [crateId])

  function elegirCrate(id: number | null) {
    audio.current?.pause()
    olvidarBlobs([])
    setCrate(null)
    setActual(null)
    setCrateId(id)
    try {
      if (id) localStorage.setItem(CLAVE_CRATE, String(id))
      else localStorage.removeItem(CLAVE_CRATE)
    } catch {
      // Sin almacenamiento solo se pierde el recordarlo
    }
  }

  // --- Audio ----------------------------------------------------------------

  function urlDe(track: Track): Promise<string> {
    let url = blobs.current.get(track.id)
    if (!url) {
      url = tracksApi.fetchTrackFile(track.id).then((blob) => URL.createObjectURL(blob))
      // Si falla, que se pueda reintentar
      url.catch(() => blobs.current.delete(track.id))
      blobs.current.set(track.id, url)
    }
    return url
  }

  /** Libera el audio de todas menos las indicadas: un crate entero en memoria
   *  serian cientos de MB en el movil. */
  function olvidarBlobs(conservar: number[]) {
    for (const [id, url] of blobs.current) {
      if (conservar.includes(id)) continue
      void url.then((u) => URL.revokeObjectURL(u)).catch(() => undefined)
      blobs.current.delete(id)
    }
  }

  const tocar = useCallback(
    async (puesto: number) => {
      const elemento = audio.current
      if (!crate || !elemento || puesto < 0 || puesto >= orden.length) return
      const track = crate.tracks[orden[puesto]]
      const siguiente = puesto + 1 < orden.length ? crate.tracks[orden[puesto + 1]] : null
      setActual(puesto)
      setCargando(true)
      setError(null)
      try {
        const url = await urlDe(track)
        olvidarBlobs([track.id, ...(siguiente ? [siguiente.id] : [])])
        elemento.src = url
        await elemento.play()
        // La siguiente se baja ya, mientras suena esta
        if (siguiente) void urlDe(siguiente).catch(() => undefined)
      } catch (err) {
        // play() rechaza si se ha cambiado de cancion mientras tanto: no es un error
        if (err instanceof DOMException && err.name === 'AbortError') return
        // El navegador no deja empezar a sonar sin un toque: el boton de play ya
        // tiene la cancion cargada
        if (err instanceof DOMException && err.name === 'NotAllowedError') {
          setError('El navegador ha bloqueado el sonido automático: pulsa el botón de play.')
          return
        }
        setError(
          `No se pudo reproducir «${track.title}»: ${err instanceof Error ? err.message : 'error'}`,
        )
      } finally {
        setCargando(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [crate, orden],
  )

  function alternar() {
    const elemento = audio.current
    if (!elemento) return
    if (actual === null) void tocar(0)
    else if (elemento.paused) void elemento.play()
    else elemento.pause()
  }

  function siguiente() {
    if (actual !== null && actual + 1 < orden.length) void tocar(actual + 1)
  }

  function anterior() {
    const elemento = audio.current
    if (!elemento || actual === null) return
    if (elemento.currentTime > REINICIAR_SI_PASADO || actual === 0) elemento.currentTime = 0
    else void tocar(actual - 1)
  }

  function cambiarAleatorio() {
    const nuevo = !aleatorio
    setAleatorio(nuevo)
    // La que suena sigue sonando: se reordena el resto alrededor de ella
    const enCurso = actual !== null ? orden[actual] : 0
    const reordenado = nuevo ? barajar(pistas.length, enCurso) : pistas.map((_, i) => i)
    setOrden(reordenado)
    if (actual !== null) setActual(reordenado.indexOf(enCurso))
  }

  // Los manejadores de la pantalla de bloqueo y del final de cancion se leen
  // de una referencia: se registran una vez y llaman siempre a la version al dia
  const acciones = useRef({ siguiente, anterior, alternar })
  acciones.current = { siguiente, anterior, alternar }

  // Al terminar, la siguiente; al final del crate, se para
  function alTerminar() {
    if (actual !== null && actual + 1 < orden.length) void tocar(actual + 1)
    else setSonando(false)
  }

  // --- Pantalla de bloqueo y notificacion --------------------------------------

  useEffect(() => {
    if (!('mediaSession' in navigator)) return
    const sesion = navigator.mediaSession
    const manejadores: Array<[MediaSessionAction, MediaSessionActionHandler]> = [
      ['play', () => void audio.current?.play()],
      ['pause', () => audio.current?.pause()],
      ['nexttrack', () => acciones.current.siguiente()],
      ['previoustrack', () => acciones.current.anterior()],
      [
        'seekto',
        (detalle) => {
          if (audio.current && detalle.seekTime !== undefined) audio.current.currentTime = detalle.seekTime
        },
      ],
    ]
    for (const [accion, manejador] of manejadores) {
      try {
        sesion.setActionHandler(accion, manejador)
      } catch {
        // Algun navegador no conoce alguna accion
      }
    }
    return () => {
      for (const [accion] of manejadores) {
        try {
          sesion.setActionHandler(accion, null)
        } catch {
          // idem
        }
      }
    }
  }, [])

  useEffect(() => {
    if (!('mediaSession' in navigator) || !pista) return
    navigator.mediaSession.metadata = new MediaMetadata({
      title: pista.title,
      artist: pista.artist_text ?? '',
      album: crate?.name ?? '',
      artwork: pista.thumbnail_url
        ? [{ src: pista.thumbnail_url, sizes: '320x180', type: 'image/jpeg' }]
        : [],
    })
  }, [pista, crate])

  useEffect(() => {
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = sonando ? 'playing' : 'paused'
  }, [sonando])

  // Al salir de la pantalla, el audio guardado se libera
  useEffect(() => () => olvidarBlobs([]), [])

  // --- Pantalla ---------------------------------------------------------------

  return (
    <div className="stack listen">
      <h1>Escuchar</h1>

      <label className="listen__crate">
        <span>Crate</span>
        <select value={crateId ?? ''} onChange={(e) => elegirCrate(e.target.value ? Number(e.target.value) : null)}>
          <option value="">Elige un crate...</option>
          {crates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.track_count})
            </option>
          ))}
        </select>
      </label>

      {error && <Alert kind="error">{error}</Alert>}

      <audio
        ref={audio}
        preload="auto"
        onPlay={() => setSonando(true)}
        onPause={() => setSonando(false)}
        onEnded={alTerminar}
        onLoadedMetadata={(e) => setDuracion(e.currentTarget.duration)}
        onTimeUpdate={(e) => {
          const elemento = e.currentTarget
          setPosicion(elemento.currentTime)
          if ('mediaSession' in navigator && Number.isFinite(elemento.duration)) {
            try {
              navigator.mediaSession.setPositionState({
                duration: elemento.duration,
                position: Math.min(elemento.currentTime, elemento.duration),
                playbackRate: elemento.playbackRate,
              })
            } catch {
              // Valores fuera de rango mientras cambia de cancion
            }
          }
        }}
      />

      {crate && (
        <section className="card listen__now">
          {pista?.thumbnail_url ? (
            <img className="listen__cover" src={pista.thumbnail_url} alt="" />
          ) : (
            <div className="listen__cover listen__cover--empty" aria-hidden="true" />
          )}
          <div className="listen__titles">
            <strong>{pista ? pista.title : crate.name}</strong>
            <span className="muted">
              {pista
                ? pista.artist_text ?? 'Artista desconocido'
                : `${pistas.length} ${pistas.length === 1 ? 'canción' : 'canciones'}`}
            </span>
          </div>

          <input
            type="range"
            className="listen__seek"
            min={0}
            max={duracion || 0}
            step={0.5}
            value={posicion}
            disabled={!pista}
            aria-label="Posición"
            onChange={(e) => {
              if (audio.current) audio.current.currentTime = Number(e.target.value)
            }}
          />
          <div className="listen__times muted">
            <span>{formatClock(posicion)}</span>
            <span>{cargando ? 'cargando...' : `-${formatClock(Math.max(0, duracion - posicion))}`}</span>
          </div>

          <div className="listen__controls">
            <button
              type="button"
              className={`listen__btn listen__btn--small${aleatorio ? ' listen__btn--on' : ''}`}
              aria-pressed={aleatorio}
              aria-label="Aleatorio"
              title="Aleatorio"
              disabled={pistas.length < 2}
              onClick={cambiarAleatorio}
            >
              <ShuffleIcon />
            </button>
            <button type="button" className="listen__btn" aria-label="Anterior" disabled={actual === null} onClick={anterior}>
              <PrevIcon />
            </button>
            <button
              type="button"
              className="listen__btn listen__btn--play"
              aria-label={sonando ? 'Pausar' : 'Reproducir'}
              disabled={pistas.length === 0}
              onClick={alternar}
            >
              {sonando ? <PauseIcon /> : <PlayIcon />}
            </button>
            <button
              type="button"
              className="listen__btn"
              aria-label="Siguiente"
              disabled={actual === null || actual + 1 >= orden.length}
              onClick={siguiente}
            >
              <NextIcon />
            </button>
            <span className="listen__btn--small" aria-hidden="true" />
          </div>
        </section>
      )}

      {crate &&
        (pistas.length === 0 ? (
          <p className="muted">Este crate está vacío.</p>
        ) : (
          <ol className="listen__list">
            {orden.map((indice, puesto) => {
              const track = pistas[indice]
              return (
                <li key={track.id}>
                  <button
                    type="button"
                    className={`listen__item${puesto === actual ? ' listen__item--on' : ''}`}
                    aria-current={puesto === actual ? 'true' : undefined}
                    onClick={() => void tocar(puesto)}
                  >
                    <span className="listen__num">{puesto + 1}</span>
                    <span className="listen__info">
                      <strong>{track.title}</strong>
                      <span className="muted">{track.artist_text ?? 'Artista desconocido'}</span>
                    </span>
                    <span className="muted listen__dur">{formatDuration(track.duration_seconds)}</span>
                  </button>
                </li>
              )
            })}
          </ol>
        ))}
    </div>
  )
}
