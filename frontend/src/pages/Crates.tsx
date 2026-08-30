import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import * as cratesApi from '../api/crates'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { formatTotal } from '../lib/duration'
import type { CrateSummary } from '../types/api'

export function CratesPage() {
  const [crates, setCrates] = useState<CrateSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    try {
      setCrates(await cratesApi.listCrates())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar los crates.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      const crate = await cratesApi.createCrate(name.trim())
      setCrates((prev) => [...prev, crate].sort((a, b) => a.name.localeCompare(b.name)))
      setName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el crate.')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="stack">
      <h1>Crates</h1>
      <p className="muted">
        Selecciones de canciones con nombre y orden propio, como las cajas de vinilos
        que se llevaban al bar. A diferencia de un filtro, un crate no cambia solo:
        lo montas una vez y sigue igual la semana que viene.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <section className="card">
        <form className="inline-form" onSubmit={handleCreate}>
          <input
            type="text"
            value={name}
            placeholder="Nombre del crate: Warm-up del sabado"
            onChange={(e) => setName(e.target.value)}
          />
          <button type="submit" className="btn btn--primary" disabled={creating || !name.trim()}>
            {creating ? 'Creando...' : 'Crear'}
          </button>
        </form>
        <p className="muted hint">
          Tambien puedes filtrar la biblioteca por etiquetas y guardar el resultado de
          golpe desde alli.
        </p>
      </section>

      {crates.length === 0 ? (
        <section className="card">
          <p className="muted">Todavia no hay ningun crate.</p>
        </section>
      ) : (
        <ul className="cratelist">
          {crates.map((crate) => (
            <li key={crate.id} className="cratecard">
              <Link to={`/crates/${crate.id}`} className="cratecard__name">
                {crate.name}
              </Link>
              <span className="muted">
                {crate.track_count} {crate.track_count === 1 ? 'cancion' : 'canciones'}
                {crate.track_count > 0 && ` · ${formatTotal(crate.total_seconds)}`}
              </span>
              {crate.description && <p className="cratecard__desc">{crate.description}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
