import { useEffect, useState } from 'react'

import * as cratesApi from '../api/crates'
import type { CrateSummary } from '../types/api'

// Una sola peticion para todos los desplegables de la pantalla: una lista de
// cien canciones no debe pedir cien veces los crates. Pasado un rato se vuelve
// a pedir, por si se ha creado alguno.
const VIGENCIA_MS = 30_000
let cache: { cuando: number; lista: Promise<CrateSummary[]> } | null = null
// Desplegables montados, para avisarles cuando se crea un crate
const oyentes = new Set<(lista: CrateSummary[]) => void>()

function cargar(): Promise<CrateSummary[]> {
  if (!cache || Date.now() - cache.cuando > VIGENCIA_MS) {
    const lista = cratesApi.listCrates().catch(() => {
      cache = null
      return []
    })
    cache = { cuando: Date.now(), lista }
  }
  return cache.lista
}

/** Vuelve a pedir los crates y actualiza todos los desplegables, p. ej. tras
 *  crear uno. */
export async function refrescarCrates(): Promise<void> {
  cache = null
  const lista = await cargar()
  oyentes.forEach((oyente) => oyente(lista))
}

/** Los crates para elegir en un desplegable. */
export function useCrates(): CrateSummary[] {
  const [crates, setCrates] = useState<CrateSummary[]>([])
  useEffect(() => {
    let vivo = true
    void cargar().then((lista) => vivo && setCrates(lista))
    oyentes.add(setCrates)
    return () => {
      vivo = false
      oyentes.delete(setCrates)
    }
  }, [])
  return crates
}
