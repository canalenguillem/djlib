import { useEffect, useState } from 'react'

import * as tracksApi from '../api/tracks'
import { useCrates } from '../lib/crates'
import type { CrateSuggestion } from '../types/api'

interface Props {
  trackId: number
  crateIds: number[]
  pendingCrateId: number | null
  /** Proponer crates segun lo que ya hay en cada uno (al bajar una nueva). */
  sugerir?: boolean
}

/** Desplegable para meter una cancion en un crate o cambiarla de crate. Si
 *  aun se esta descargando, entra en el crate al terminar. */
export function CrateSelect({ trackId, crateIds, pendingCrateId, sugerir = false }: Props) {
  const crates = useCrates()
  const [actuales, setActuales] = useState(crateIds)
  const [pendienteId, setPendienteId] = useState(pendingCrateId)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // La lista se refresca mientras hay descargas: al terminar, el crate
  // apuntado pasa a ser uno de verdad
  const clave = `${crateIds.join(',')}|${pendingCrateId}`
  useEffect(() => {
    setActuales(crateIds)
    setPendienteId(pendingCrateId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])

  // Si esta en varios, se muestra el primero y se avisa de los demas
  const actual = pendienteId ?? actuales[0] ?? null
  const otros = actuales.length - 1

  // Solo mientras no tenga crate: despues ya no hace falta
  const [sugerencias, setSugerencias] = useState<CrateSuggestion[]>([])
  const sinCrate = actual === null
  useEffect(() => {
    if (!sugerir || !sinCrate) {
      setSugerencias([])
      return
    }
    let vivo = true
    tracksApi
      .crateSuggestions(trackId)
      .then((s) => vivo && setSugerencias(s))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [sugerir, sinCrate, trackId])

  async function cambiar(destino: number | null) {
    if (destino === actual) return
    setGuardando(true)
    setError(null)
    try {
      const track = await tracksApi.moveTrackToCrate(trackId, destino, actual)
      setActuales(track.crate_ids)
      setPendienteId(track.pending_crate_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cambiar de crate.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <span className={`crateselect${actual !== null ? ' crateselect--set' : ''}`}>
      <select
        aria-label="Crate"
        title={pendienteId !== null ? 'Entrará en este crate al terminar de descargarse' : 'Crate de la canción'}
        value={actual ?? ''}
        disabled={guardando || crates.length === 0}
        onChange={(e) => void cambiar(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">{crates.length === 0 ? 'No hay crates' : 'Sin crate'}</option>
        {crates.map((crate) => (
          <option key={crate.id} value={crate.id}>
            {crate.name}
          </option>
        ))}
      </select>
      {otros > 0 && (
        <span className="crateselect__more" title="También está en otros crates">
          +{otros}
        </span>
      )}
      {sugerencias.length > 0 && (
        <span className="crateselect__sugerencias">
          <span className="crateselect__more">Sugeridos:</span>
          {sugerencias.map((s) => (
            <button
              key={s.crate_id}
              type="button"
              className="chip"
              title={s.reasons.join(' · ')}
              disabled={guardando}
              onClick={() => void cambiar(s.crate_id)}
            >
              {s.name}
            </button>
          ))}
        </span>
      )}
      {error && <span className="crateselect__error">{error}</span>}
    </span>
  )
}
