import { useCallback, useEffect, useRef, useState } from 'react'

import * as tracksApi from '../api/tracks'
import { AddTrackPanel } from '../components/AddTrackPanel'
import { STATUS_LABEL } from '../components/TrackRow'
import type { Track } from '../types/api'

const RECIENTES = 10

/** Bajar de YouTube una a una: por enlace, buscando por titulo y artista, o
 *  subiendo un fichero propio. Debajo, como van las ultimas que han entrado. */
export function YoutubePage() {
  const [recientes, setRecientes] = useState<Track[]>([])
  // Con resultados de YouTube en pantalla solo se ven esos
  const [enYoutube, setEnYoutube] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setRecientes((await tracksApi.listTracks({ limit: RECIENTES })).items)
    } catch {
      // La lista es un extra: el panel ya avisa si algo falla al anadir
    }
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const pendientes = recientes.filter((t) => t.status === 'pending' || t.status === 'downloading').length
  const cargarRef = useRef(cargar)
  cargarRef.current = cargar
  useEffect(() => {
    if (pendientes === 0) return
    const timer = window.setInterval(() => void cargarRef.current(), 3000)
    return () => window.clearInterval(timer)
  }, [pendientes])

  return (
    <>
      <h1>YouTube</h1>
      <AddTrackPanel onAdded={() => void cargar()} onResults={setEnYoutube} />

      {!enYoutube && recientes.length > 0 && (
        <section className="card">
          <h2>Últimas añadidas</h2>
          <ul className="detected">
            {recientes.map((t) => (
              <li key={t.id} className="detected__item">
                <div className="track__info">
                  <div className="track__title">{t.title}</div>
                  <div className="track__meta">
                    {t.artist_text && <span>{t.artist_text}</span>}
                    {t.status === 'ready' ? (
                      <span className="badge badge--ok">{STATUS_LABEL.ready}</span>
                    ) : t.status === 'error' ? (
                      <span className="badge badge--off" title={t.error_message ?? undefined}>
                        {STATUS_LABEL.error}
                      </span>
                    ) : (
                      <span className="badge badge--busy">{STATUS_LABEL[t.status]}</span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
