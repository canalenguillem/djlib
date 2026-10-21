import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import * as batchesApi from '../api/batches'
import * as cratesApi from '../api/crates'
import { refrescarCrates, useCrates } from '../lib/crates'
import type { Batch, BatchItem } from '../types/api'

/** Lo minimo para buscar una cancion en YouTube. */
export interface Cancion {
  title: string
  artist: string | null
}

// Cada cuanto se pregunta al servidor como va la tanda
const SONDEO_MS = 3000
// Crate elegido para las descargas automaticas, recordado entre visitas y
// compartido por las capturas y las listas de Spotify
const CLAVE_CRATE = 'djlib.capturas_crate'
// Tandas lanzadas desde cada sitio (una captura, una lista), para ver como van
// al volver aunque se haya cerrado la pagina
const CLAVE_TANDAS = 'djlib.tandas.'

function crateGuardado(): number | null {
  try {
    const valor = Number(localStorage.getItem(CLAVE_CRATE))
    return valor > 0 ? valor : null
  } catch {
    return null
  }
}

function tandasGuardadas(origen: string): number[] {
  try {
    const valor = JSON.parse(localStorage.getItem(CLAVE_TANDAS + origen) ?? '[]')
    return Array.isArray(valor) ? valor.filter((v) => typeof v === 'number') : []
  } catch {
    return []
  }
}

function guardarTandas(origen: string, ids: number[]) {
  try {
    if (ids.length) localStorage.setItem(CLAVE_TANDAS + origen, JSON.stringify(ids))
    else localStorage.removeItem(CLAVE_TANDAS + origen)
  } catch {
    // Sin almacenamiento solo se pierde verlas al volver
  }
}

/** Como va cada cancion en la descarga automatica. */
export type Estado =
  | { tipo: 'en_cola' }
  | { tipo: 'buscando' }
  | { tipo: 'descargando'; titulo: string | null }
  | { tipo: 'lista' }
  | { tipo: 'ya_estaba' }
  | { tipo: 'sin_resultado' }
  | { tipo: 'error'; motivo: string }

const TEXTO_ESTADO: Record<Estado['tipo'], string> = {
  en_cola: 'en cola',
  buscando: 'buscando...',
  descargando: 'descargando',
  lista: 'descargada',
  ya_estaba: 'ya estaba',
  sin_resultado: 'sin resultado',
  error: 'error',
}

function estadoDe(item: BatchItem): Estado | null {
  switch (item.status) {
    case 'pending':
      return { tipo: 'en_cola' }
    case 'searching':
      return { tipo: 'buscando' }
    case 'downloading':
      return { tipo: 'descargando', titulo: item.video_title }
    case 'done':
      return { tipo: 'lista' }
    case 'already':
      return { tipo: 'ya_estaba' }
    case 'not_found':
      return { tipo: 'sin_resultado' }
    case 'error':
      return { tipo: 'error', motivo: item.message ?? 'ha fallado' }
    default:
      // Cancelada: como si no se hubiera pedido
      return null
  }
}

/** Clave para reconocer la misma cancion escrita de dos formas: sin
 *  mayusculas, acentos ni signos. */
export function claveCancion(song: Cancion): string {
  const limpiar = (texto: string | null) =>
    (texto ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim()
  return `${limpiar(song.artist)}|${limpiar(song.title)}`
}

/** Descarga automatica de una lista de canciones. La hace el servidor, en
 *  una tanda: busca cada una en YouTube, baja el primer resultado que no sea
 *  un mix y la mete en el crate elegido. Aqui solo se lanza y se mira como
 *  va, asi que se puede cerrar la pagina o apagar el ordenador.
 *
 *  `origen` identifica de donde salen las canciones (las capturas, una lista
 *  de Spotify concreta): al volver ahi se ve como van sus tandas. */
export function useAutoDownload(origen: string) {
  const [tandas, setTandas] = useState<Batch[]>([])
  const [error, setError] = useState<string | null>(null)

  // Al entrar (o cambiar de lista), las tandas que se lanzaron desde aqui
  useEffect(() => {
    let vivo = true
    setTandas([])
    const ids = tandasGuardadas(origen)
    void Promise.all(ids.map((id) => batchesApi.getBatch(id).catch(() => null))).then((lista) => {
      if (!vivo) return
      const validas = lista.filter((t): t is Batch => t !== null)
      // Las que ya no existen se olvidan
      guardarTandas(origen, validas.map((t) => t.id))
      setTandas(validas)
    })
    return () => {
      vivo = false
    }
  }, [origen])

  const activas = tandas.filter((t) => t.status === 'active').map((t) => t.id)
  const claveActivas = activas.join(',')

  // Mientras haya alguna en marcha, se pregunta como va
  useEffect(() => {
    if (!claveActivas) return
    const ids = claveActivas.split(',').map(Number)
    const temporizador = window.setInterval(() => {
      void Promise.all(ids.map((id) => batchesApi.getBatch(id).catch(() => null))).then((nuevas) => {
        setTandas((prev) =>
          prev.map((t) => nuevas.find((n) => n?.id === t.id) ?? t),
        )
      })
    }, SONDEO_MS)
    return () => window.clearInterval(temporizador)
  }, [claveActivas])

  // Las tandas mas nuevas mandan: una cancion reintentada sale como va ahora
  const estados: Record<string, Estado> = {}
  for (const tanda of [...tandas].sort((a, b) => a.id - b.id)) {
    for (const item of tanda.items) {
      const estado = estadoDe(item)
      if (estado) estados[claveCancion(item)] = estado
    }
  }

  async function descargar(canciones: Cancion[], destino: number | null, nombre: string) {
    const faltan = canciones.filter((c) => {
      const estado = estados[claveCancion(c)]
      return !estado || estado.tipo === 'error'
    })
    if (!faltan.length) return
    setError(null)
    try {
      const tanda = await batchesApi.createBatch(
        nombre,
        destino,
        faltan.map((c) => ({ title: c.title, artist: c.artist })),
      )
      setTandas((prev) => [...prev, tanda])
      guardarTandas(origen, [...tandasGuardadas(origen), tanda.id])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo lanzar la descarga.')
    }
  }

  async function parar() {
    const nuevas = await Promise.all(activas.map((id) => batchesApi.cancelBatch(id).catch(() => null)))
    setTandas((prev) => prev.map((t) => nuevas.find((n) => n?.id === t.id) ?? t))
  }

  /** Las que aun no se han pedido; las de error se reintentan. */
  function pendientes(canciones: Cancion[]): number {
    return canciones.filter((c) => {
      const estado = estados[claveCancion(c)]
      return !estado || estado.tipo === 'error'
    }).length
  }

  // Progreso de lo que esta en marcha
  const enMarcha = tandas.filter((t) => t.status === 'active')
  const progreso = enMarcha.length
    ? {
        total: enMarcha.reduce((n, t) => n + t.total, 0),
        hechas: enMarcha.reduce(
          (n, t) =>
            n + t.total - (t.counts.pending ?? 0) - (t.counts.searching ?? 0) - (t.counts.downloading ?? 0),
          0,
        ),
      }
    : null

  return {
    estados,
    enCola: enMarcha.length > 0,
    progreso,
    error,
    descargar,
    pendientes,
    parar: () => void parar(),
    /** Olvida las tandas de este origen (no las cancela). */
    reiniciar: () => {
      guardarTandas(origen, [])
      setTandas([])
    },
  }
}

export type AutoDownload = ReturnType<typeof useAutoDownload>

const NUEVO = 'nuevo'

/** Barra para elegir crate (o crear uno) y lanzar la descarga de todas. */
export function AutoDownloadBar({
  canciones,
  auto,
  nombreTanda,
  nombreSugerido,
  disabled,
}: {
  canciones: Cancion[]
  auto: AutoDownload
  /** Como se llamara la tanda en el servidor, p. ej. "Spotify: Warm-up". */
  nombreTanda: string
  /** Nombre que se propone al crear un crate nuevo, p. ej. el de la lista. */
  nombreSugerido?: string
  disabled?: boolean
}) {
  const crates = useCrates()
  const [crateId, setCrateId] = useState<number | null>(crateGuardado)
  const [creando, setCreando] = useState(false)
  const [nombre, setNombre] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pendientes = auto.pendientes(canciones)

  function elegir(id: number | null) {
    setCrateId(id)
    try {
      if (id) localStorage.setItem(CLAVE_CRATE, String(id))
      else localStorage.removeItem(CLAVE_CRATE)
    } catch {
      // Sin almacenamiento solo se pierde el recordarlo
    }
  }

  async function crear(e: FormEvent) {
    e.preventDefault()
    if (!nombre.trim()) return
    setGuardando(true)
    setError(null)
    try {
      const crate = await cratesApi.createCrate(nombre.trim())
      await refrescarCrates()
      elegir(crate.id)
      setCreando(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el crate.')
    } finally {
      setGuardando(false)
    }
  }

  // El crate recordado puede haberse borrado
  const elegido = crates.some((c) => c.id === crateId) ? crateId : null

  return (
    <div className="autoload">
      {creando ? (
        <form className="autoload__crate" onSubmit={crear}>
          <span>Crate nuevo</span>
          <input
            value={nombre}
            autoFocus
            placeholder="Nombre del crate"
            aria-label="Nombre del crate nuevo"
            onChange={(e) => setNombre(e.target.value)}
          />
          <button type="submit" className="btn btn--primary" disabled={guardando || !nombre.trim()}>
            {guardando ? 'Creando...' : 'Crear'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setCreando(false)}>
            Cancelar
          </button>
        </form>
      ) : (
        <label className="autoload__crate">
          <span>Meterlas en el crate</span>
          <select
            value={elegido ?? ''}
            disabled={auto.enCola}
            onChange={(e) => {
              if (e.target.value === NUEVO) {
                setNombre(nombreSugerido ?? '')
                setError(null)
                setCreando(true)
              } else {
                elegir(e.target.value ? Number(e.target.value) : null)
              }
            }}
          >
            <option value="">Ninguno, solo a la biblioteca</option>
            {crates.map((crate) => (
              <option key={crate.id} value={crate.id}>
                {crate.name}
              </option>
            ))}
            <option value={NUEVO}>+ Crear uno nuevo...</option>
          </select>
        </label>
      )}
      {auto.enCola ? (
        <button type="button" className="btn btn--ghost" onClick={auto.parar}>
          Parar
        </button>
      ) : (
        <button
          type="button"
          className="btn btn--primary"
          disabled={disabled || creando || pendientes === 0}
          title="Busca cada una en YouTube y descarga el primer resultado que no sea un mix"
          onClick={() => void auto.descargar(canciones, elegido, nombreTanda)}
        >
          {pendientes === canciones.length
            ? `Descargar todas (${pendientes})`
            : `Descargar las que faltan (${pendientes})`}
        </button>
      )}
      {auto.progreso && (
        <p className="autoload__progreso" role="status">
          El servidor las está descargando: {auto.progreso.hechas} de {auto.progreso.total}.
          Puedes cerrar la página o apagar el ordenador; al volver verás cómo han ido.
        </p>
      )}
      {(error ?? auto.error) && <div className="track__error">{error ?? auto.error}</div>}
    </div>
  )
}

/** Marca de como va una cancion en la descarga automatica. */
export function EstadoDescarga({ estado }: { estado: Estado | undefined }) {
  if (!estado) return null
  return (
    <span
      className={`badge autoload__estado autoload__estado--${estado.tipo}`}
      title={
        estado.tipo === 'descargando' && estado.titulo
          ? `Descargando «${estado.titulo}»`
          : estado.tipo === 'error'
            ? estado.motivo
            : undefined
      }
    >
      {TEXTO_ESTADO[estado.tipo]}
    </span>
  )
}
