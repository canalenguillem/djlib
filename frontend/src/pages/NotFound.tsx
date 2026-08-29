import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="card">
      <h2>Pagina no encontrada</h2>
      <p className="muted">La ruta que buscas no existe.</p>
      <Link to="/library" className="btn btn--primary">
        Volver a la biblioteca
      </Link>
    </div>
  )
}
