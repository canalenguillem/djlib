import { useEffect, useState } from 'react'

import { getListenStats } from '../api/listens'
import type { ListenCounts, ListenStats } from '../types/api'
import { Alert } from './Alert'
import { Loading } from './Loading'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value}Z`).toLocaleString('es-ES')
}

/** "12 (3 esta semana)": el total y lo reciente de un mismo origen. */
function Cifra({ total, semana }: { total: number; semana: number }) {
  return (
    <>
      {total}
      {semana > 0 && <span className="muted"> ({semana} esta semana)</span>}
    </>
  )
}

function suma(c: ListenCounts): number {
  return c.player + c.mixer
}

/** Cuanto escucha cada usuario, separando el reproductor de las mezclas. */
export function ListenStatsPanel() {
  const [stats, setStats] = useState<ListenStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getListenStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : 'No se pudieron cargar las escuchas.'))
  }, [])

  return (
    <section className="card">
      <h2>Escuchas</h2>
      <p className="muted">
        Cuenta cuando una canción ha sonado al menos 30 segundos (o la mitad, si es más corta).
        «Reproductor» es la biblioteca, los crates y Escuchar; «Mezclas», los platos del mezclador.
      </p>
      {error && <Alert kind="error">{error}</Alert>}
      {!stats && !error && <Loading />}
      {stats && stats.users.length === 0 && <p className="muted">Todavía no ha escuchado nada nadie.</p>}
      {stats && stats.users.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="table users-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Reproductor</th>
                  <th>Mezclas</th>
                  <th>Total</th>
                  <th>Última escucha</th>
                </tr>
              </thead>
              <tbody>
                {stats.users.map((u) => (
                  <tr key={u.user_id ?? 'borrado'}>
                    <td data-label="Usuario">{u.username ?? <span className="muted">usuario borrado</span>}</td>
                    <td data-label="Reproductor">
                      <Cifra total={u.total.player} semana={u.last_7_days.player} />
                    </td>
                    <td data-label="Mezclas">
                      <Cifra total={u.total.mixer} semana={u.last_7_days.mixer} />
                    </td>
                    <td data-label="Total">
                      <Cifra total={suma(u.total)} semana={suma(u.last_7_days)} />
                    </td>
                    <td data-label="Última escucha" className="muted">
                      {formatDate(u.last_listen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>Lo más escuchado</h3>
          <div className="table-wrap">
            <table className="table users-table">
              <thead>
                <tr>
                  <th>Canción</th>
                  <th>Reproductor</th>
                  <th>Mezclas</th>
                </tr>
              </thead>
              <tbody>
                {stats.top_tracks.map((t) => (
                  <tr key={t.track_id}>
                    <td data-label="Canción">
                      {t.title}
                      {t.artist_text && <span className="muted"> · {t.artist_text}</span>}
                    </td>
                    <td data-label="Reproductor">{t.player}</td>
                    <td data-label="Mezclas">{t.mixer}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
