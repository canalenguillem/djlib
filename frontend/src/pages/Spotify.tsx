import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import * as spotifyApi from '../api/spotify'
import * as tracksApi from '../api/tracks'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { SearchCandidates } from '../components/SearchCandidates'
import type { PlayedTrack, SearchCandidate, SpotifyStatus } from '../types/api'

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

  const [abierta, setAbierta] = useState<number | null>(null)
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

  async function buscar(indice: number, cancion: PlayedTrack) {
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
      await tracksApi.addFromUrl(candidate.url)
      setAnadidos((prev) => [...prev, candidate.video_id])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo anadir la cancion.')
    } finally {
      setAnadiendo(null)
    }
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
          <h2>Ultimas reproducciones</h2>
          {played.length === 0 ? (
            <Alert kind="info">
              Spotify no ha devuelto ninguna reproduccion para esta cuenta. Suele
              significar que no es la cuenta en la que escuchas musica: comprueba el
              nombre de arriba, y si no es la tuya, desconecta y vuelve a conectar
              con la correcta. Tambien sale vacio si no has escuchado nada en Spotify
              ultimamente, porque solo cuenta lo reproducido en la propia aplicacion.
            </Alert>
          ) : (
            <ul className="detected">
              {played.map((cancion, indice) => (
                <li key={`${cancion.artist}-${cancion.title}-${indice}`} className="detected__item">
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
                            <span>{cuando(cancion.played_at)}</span>
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
                      disabled={buscando || cancion.already_in_library}
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
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
