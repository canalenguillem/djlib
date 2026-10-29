import { BatchesPanel } from '../components/BatchesPanel'

/** Las tandas que el servidor descarga solo: como van y cuanto queda. */
export function ColaPage() {
  return (
    <div className="stack">
      <h1>En cola</h1>
      <p className="muted">
        Lo que el servidor está bajando de las fuentes por su cuenta, aunque hayas
        cerrado la página o apagado el ordenador. Pulsa una tanda para ver canción
        por canción.
      </p>
      <BatchesPanel todas />
    </div>
  )
}
