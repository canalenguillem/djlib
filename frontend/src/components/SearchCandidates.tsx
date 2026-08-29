import { formatDuration } from '../lib/format'
import type { SearchCandidate } from '../types/api'

interface Props {
  candidates: SearchCandidate[]
  addedIds: string[]
  addingId: string | null
  onAdd: (candidate: SearchCandidate) => void
}

/** Resultados de YouTube para que el usuario elija.
 *
 *  Se respeta el orden de relevancia de YouTube en vez de reordenarlos: lo que
 *  hace falta no es adivinar por el usuario, sino que vea la duracion y el
 *  canal y decida. El primer resultado de una busqueda imprecisa suele ser un
 *  mix de una hora, y con la duracion delante eso se ve de un vistazo.
 */
export function SearchCandidates({ candidates, addedIds, addingId, onAdd }: Props) {
  if (candidates.length === 0) {
    return <p className="muted">YouTube no ha devuelto resultados. Prueba con otras palabras.</p>
  }

  return (
    <ul className="candidates">
      {candidates.map((candidate) => {
        const added = addedIds.includes(candidate.video_id)
        const inLibrary = candidate.already_in_library || added
        return (
          <li key={candidate.video_id} className="candidate">
            {candidate.thumbnail_url && (
              <img
                className="candidate__thumb"
                src={candidate.thumbnail_url}
                alt=""
                loading="lazy"
              />
            )}
            <div className="candidate__info">
              <div className="candidate__title">{candidate.title}</div>
              <div className="candidate__meta">
                <span>{candidate.channel ?? 'Canal desconocido'}</span>
                <span>·</span>
                <span className={candidate.too_long ? 'candidate__long' : undefined}>
                  {formatDuration(candidate.duration_seconds)}
                </span>
                {candidate.too_long && (
                  <span className="badge badge--off">parece un mix, no una cancion</span>
                )}
                {inLibrary && <span className="badge badge--ok">ya en la biblioteca</span>}
              </div>
            </div>
            <button
              type="button"
              className="btn btn--primary"
              disabled={inLibrary || addingId !== null}
              onClick={() => onAdd(candidate)}
            >
              {addingId === candidate.video_id ? 'Anadiendo...' : 'Anadir'}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
