import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import * as spotifyApi from '../api/spotify'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import type { PlayedTrack, SearchCandidate, ShazamTracks, SpotifyStatus } from '../types/api'

type Vista = 'recientes' | 'shazam'

const ERRORES: Record<string, string> = {
  access_denied: 'Has cancelado el permiso en Spotify.',
  estado_no_valido: 'La autorizacion ha caducado. Vuelve a intentarlo.',
  respuesta_incompleta: 'Spotify ha devuelto una respuesta incompleta.',
  canje: 'No se pudo completar el intercambio con Spotify. Revisa la Redirect URI.',
}

function cuando(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('es-ES', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export function SpotifyPage() {
  const [params, setParams] = useSearchParams()
  const [status, setStatus] = useState<SpotifyStatus | null>(null)
  const [played, setPlayed] = useState<PlayedTrack[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const [vista, setVista] = useState<Vista>('recientes')
  const [shazam, setShazam] = useState<ShazamTracks | null>(null)
  const [cargandoShazam, setCargandoShazam] = useState(false)
  // La cancion con los candidatos abiertos: vista e indice, p. ej. "shazam-3"
  const [abierta, setAbierta] = useState<string | null>(null)
  const [candidatos, setCandidatos] = useState<SearchCandidate[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [anadidos, setAnadidos] = useState<string[]>([])
  const [anadiendo, setAnadiendo] = useState<string | null>(null)

  // La vuelta del callback trae el resultado en la URL
  useEffect(() => {
    const fallo = params.get('error')
    if (fallo) setError(ERRORES[fallo] ?? `Spotify ha devuelto: ${fallo}`)
    if (params.get('connected')) setAviso('Cuenta de Spotify conectada.')
    if (fallo || params.get('connected')) setParams({}, { replace: true })
  }, [params, setParams])

  const cargar = useCallback(async () => {
    try {
      const estado = await spotifyApi.getSpotifyStatus()
      setStatus(estado)
      if (estado.connected) {
        const recientes = await spotifyApi.recentlyPlayed()
        setPlayed(recientes.items)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo consultar Spotify.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  async function conectar() {
    setBusy(true)
    setError(null)
    try {
      const { url } = await spotifyApi.startAuthorization()
      window.location.href = url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo iniciar la conexion.')
      setBusy(false)
    }
  }

  async function desconectar() {
    setBusy(true)
    try {
      await spotifyApi.disconnectSpotify()
      setPlayed(null)
      setAviso('Cuenta desconectada.')
      await cargar()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo desconectar.')
    } finally {
      setBusy(false)
    }
  }

  async function verShazam() {
    setVista('shazam')
    setAbierta(null)
    if (shazam !== null || cargandoShazam) return
    setCargandoShazam(true)
    setError(null)
    try {
      setShazam(await spotifyApi.shazamTracks())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo leer la playlist de Shazam.')
      setVista('recientes')
    } finally {
      setCargandoShazam(false)
    }
  }

  async function buscar(indice: string, cancion: PlayedTrack) {
    setAbierta(indice)
    setCandidatos(null)
    setBuscando(true)
    setError(null)
    try {
      const resultado = await tracksApi.previewSearch(cancion.title, cancion.artist)
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
      const nueva = await tracksApi.addFromUrl(candidate.url)
      setAnadidos((prev) => [...prev, candidate.video_id])
      return nueva
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAnadiendo(null)
    }
  }

  function lista(canciones: PlayedTrack[], prefijo: Vista) {
    return (
      <ul className="detected">
        {canciones.map((cancion, posicion) => {
          const indice = `${prefijo}-${posicion}`
          return (
            <li key={indice} className="detected__item">
              <div className="detected__row">
                {cancion.image_url && (
                  <img className="track__thumb" src={cancion.image_url} alt="" loading="lazy" />
                )}
                <div className="track__info">
                  <div className="track__title">{cancion.title}</div>
                  <div className="track__meta">
                    <span>{cancion.artist}</span>
                    {cancion.played_at && (
                      <>
                        <span>·</span>
                        <span>
                          {prefijo === 'shazam' ? 'shazameada el ' : ''}
                          {cuando(cancion.played_at)}
                        </span>
                      </>
                    )}
                    {cancion.already_in_library && (
                      <span className="badge badge--ok">ya en la biblioteca</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn--ghost"
                  disabled={buscando}
                  onClick={() => buscar(indice, cancion)}
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
          )
        })}
      </ul>
    )
  }

  if (loading) return <Loading />

  if (!status?.enabled) {
    return (
      <div className="stack">
        <h1>Spotify</h1>
        <Alert kind="info">
          Spotify no esta configurado en el servidor. Hacen falta{' '}
          <code>SPOTIFY_CLIENT_ID</code> y <code>SPOTIFY_CLIENT_SECRET</code>.
        </Alert>
      </div>
    )
  }

  return (
    <div className="stack">
      <h1>Spotify</h1>
      <p className="muted">
        Trae lo ultimo que has escuchado en Spotify y buscalo en YouTube para
        anadirlo a la biblioteca. Solo se pide permiso de lectura de tus
        reproducciones; no se toca nada de tu cuenta.
      </p>

      {error && <Alert kind="error">{error}</Alert>}
      {aviso && <Alert kind="success">{aviso}</Alert>}

      <section className="card">
        {status.connected ? (
          <div className="spotify__cuenta">
            <span>
              Conectado como <strong>{status.display_name ?? 'tu cuenta'}</strong>
            </span>
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={desconectar}>
              Desconectar
            </button>
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => void cargar()}>
              Actualizar
            </button>
          </div>
        ) : (
          <>
            <p className="muted">
              Al conectar te llevara a Spotify para que autorices la lectura de tus
              reproducciones recientes.
            </p>
            <div>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={conectar}>
                {busy ? 'Abriendo Spotify...' : 'Conectar con Spotify'}
              </button>
            </div>
          </>
        )}
      </section>

      {played !== null && (
        <section className="card">
          <div className="spotify__vistas" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={vista === 'recientes'}
              className={vista === 'recientes' ? 'rangebtn rangebtn--on' : 'rangebtn'}
              onClick={() => {
                setVista('recientes')
                setAbierta(null)
              }}
            >
              Últimas reproducciones
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={vista === 'shazam'}
              className={vista === 'shazam' ? 'rangebtn rangebtn--on' : 'rangebtn'}
              onClick={() => void verShazam()}
            >
              Shazam
            </button>
          </div>
          {vista === 'shazam' ? (
            cargandoShazam ? (
              <Loading />
            ) : shazam?.playlist == null ? (
              <Alert kind="info">
                No hay ninguna playlist de Shazam en esta cuenta de Spotify. En el móvil,
                abre Shazam, ve a Ajustes y conecta Spotify: a partir de entonces lo que
                reconozca se guarda en la playlist «My Shazam Tracks» y saldrá aquí.
              </Alert>
            ) : shazam.items.length === 0 ? (
              <Alert kind="info">La playlist «{shazam.playlist}» está vacía.</Alert>
            ) : (
              <>
                <p className="muted">
                  Las últimas {shazam.items.length} de «{shazam.playlist}», de la más
                  reciente a la más antigua.
                </p>
                {lista(shazam.items, 'shazam')}
              </>
            )
          ) : played.length === 0 ? (
            <Alert kind="info">
              Spotify no ha devuelto ninguna reproduccion para esta cuenta. Suele
              significar que no es la cuenta en la que escuchas musica: comprueba el
              nombre de arriba, y si no es la tuya, desconecta y vuelve a conectar
              con la correcta. Tambien sale vacio si no has escuchado nada en Spotify
              ultimamente, porque solo cuenta lo reproducido en la propia aplicacion.
            </Alert>
          ) : (
            lista(played, 'recientes')
          )}
        </section>
      )}
    </div>
  )
}
