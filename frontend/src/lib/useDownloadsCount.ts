import { useEffect, useState } from 'react'

import * as batchesApi from '../api/batches'
import { faltan } from '../components/BatchesPanel'

// Sin nada en marcha basta con mirar de vez en cuando; con algo en marcha, a
// menudo, para que el contador baje a la vista
const LENTO_MS = 30_000
const RAPIDO_MS = 5_000

/** Cuantas canciones faltan en las tandas en marcha, para el menu. */
export function useDownloadsCount(): number {
  const [cuenta, setCuenta] = useState(0)
  useEffect(() => {
    let vivo = true
    let temporizador: number | undefined
    async function mirar() {
      let siguiente = LENTO_MS
      try {
        const tandas = await batchesApi.listBatches()
        const total = tandas.filter((t) => t.status === 'active').reduce((n, t) => n + faltan(t), 0)
        if (!vivo) return
        setCuenta(total)
        if (total > 0) siguiente = RAPIDO_MS
      } catch {
        // El contador es un extra: si falla, se reintenta mas tarde
      }
      if (vivo) temporizador = window.setTimeout(() => void mirar(), siguiente)
    }
    void mirar()
    return () => {
      vivo = false
      window.clearTimeout(temporizador)
    }
  }, [])
  return cuenta
}
