import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import * as batchesApi from '../api/batches'
import type { Batch, BatchItemStatus, BatchSummary } from '../types/api'

const SONDEO_MS = 4000

const TEXTO: Record<BatchItemStatus, string> = {
  pending: 'en cola',
  searching: 'buscando',
  downloading: 'descargando',
  done: 'descargada',
  already: 'ya estaba',
  not_found: 'sin resultado',
  error: 'error',
  cancelled: 'cancelada',
}

const ESTADO_TANDA: Record<BatchSummary['status'], string> = {
  active: 'en marcha',
  done: 'terminada',
  cancelled: 'parada',
}

function hechas(tanda: BatchSummary): number {
  const c = tanda.counts
  return tanda.total - (c.pending ?? 0) - (c.searching ?? 0) - (c.downloading ?? 0) - (c.cancelled ?? 0)
}

/** Las descargas que el servidor hace solo, para ver al volver como han ido.
 *  Se refresca mientras alguna esta en marcha. `onProgress` avisa cuando
 *  entra algo nuevo en la biblioteca, para recargarla. */
export function BatchesPanel({ onProgress }: { onProgress?: () => void }) {
  const [tandas, setTandas] = useState<BatchSummary[]>([])
  const [abierta, setAbierta] = useState<Batch | null>(null)
  const activas = tandas.some((t) => t.status === 'active')

  useEffect(() => {
    let vivo = true
    let anterior = ''
    async function cargar() {
      try {
        const lista = await batchesApi.listBatches()
        if (!vivo) return
        setTandas(lista)
        // Cuando cambia el recuento, ha entrado o fallado alguna
        const huella = lista.map((t) => `${t.id}:${hechas(t)}`).join(',')
        if (anterior && huella !== anterior) onProgress?.()
        anterior = huella
      } catch {
        // El panel es un extra: si falla, no se ensena
      }
    }
    void cargar()
    if (!activas) return () => void (vivo = false)
    const temporizador = window.setInterval(() => void cargar(), SONDEO_MS)
    return () => {
      vivo = false
      window.clearInterval(temporizador)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activas])

  // El detalle abierto se refresca con el resto
  useEffect(() => {
    if (!abierta) return
    const resumen = tandas.find((t) => t.id === abierta.id)
    if (resumen && hechas(resumen) !== hechas(abierta)) {
      void batchesApi.getBatch(abierta.id).then(setAbierta).catch(() => undefined)
    }
  }, [tandas, abierta])

  // Solo interesan las recientes en marcha o de hoy
  const visibles = tandas.filter(
    (t) => t.status === 'active' || Date.now() - new Date(t.created_at + 'Z').getTime() < 24 * 3600 * 1000,
  )
  if (visibles.length === 0) return null

  return (
    <section className="card batches">
      <h2>Descargas en segundo plano</h2>
      <ul className="batches__list">
        {visibles.map((t) => {
          const n = hechas(t)
          return (
            <li key={t.id} className="batches__item">
              <div className="batches__head">
                <button
                  type="button"
                  className="batches__name"
                  aria-expanded={abierta?.id === t.id}
                  onClick={() =>
                    abierta?.id === t.id
                      ? setAbierta(null)
                      : void batchesApi.getBatch(t.id).then(setAbierta).catch(() => undefined)
                  }
                >
                  <strong>{t.name}</strong>
                  <span className="muted">
                    {n} de {t.total} · {ESTADO_TANDA[t.status]}
                    {t.crate_name && (
                      <>
                        {' · crate '}
                        {t.crate_name}
                      </>
                    )}
                  </span>
                </button>
                {t.crate_id && (
                  <Link className="btn btn--ghost" to={`/crates/${t.crate_id}`}>
                    Ver crate
                  </Link>
                )}
                {t.status === 'active' && (
                  <button
                    type="button"
                    className="btn btn--ghost"
                    title="Lo que esté en cola no se descargará; lo que ya se está descargando termina"
                    onClick={() =>
                      void batchesApi.cancelBatch(t.id).then((c) => {
                        setTandas((prev) => prev.map((x) => (x.id === c.id ? c : x)))
                      })
                    }
                  >
                    Parar
                  </button>
                )}
              </div>
              <progress className="batches__bar" max={t.total} value={n} />
              <div className="batches__counts muted">
                {(Object.keys(TEXTO) as BatchItemStatus[])
                  .filter((k) => t.counts[k])
                  .map((k) => `${t.counts[k]} ${TEXTO[k]}`)
                  .join(' · ')}
              </div>
              {abierta?.id === t.id && (
                <ol className="batches__items">
                  {abierta.items.map((item) => (
                    <li key={item.id}>
                      <span>
                        {item.artist ? `${item.artist} — ` : ''}
                        {item.title}
                      </span>
                      <span
                        className={`badge batches__status batches__status--${item.status}`}
                        title={item.message ?? item.video_title ?? undefined}
                      >
                        {TEXTO[item.status]}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
