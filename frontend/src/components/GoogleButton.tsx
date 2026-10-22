import { useEffect, useRef, useState } from 'react'

import { getAuthConfig } from '../api/auth'

/** Lo minimo de Google Identity Services que se usa aqui. */
interface GoogleId {
  initialize(opciones: { client_id: string; callback: (r: { credential: string }) => void }): void
  renderButton(el: HTMLElement, opciones: Record<string, unknown>): void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } }
  }
}

const SCRIPT = 'https://accounts.google.com/gsi/client'

let cargando: Promise<GoogleId> | null = null

function cargarGoogle(): Promise<GoogleId> {
  cargando ??= new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SCRIPT
    s.async = true
    s.onload = () => (window.google ? resolve(window.google.accounts.id) : reject(new Error('Google')))
    s.onerror = () => {
      cargando = null
      reject(new Error('No se ha podido cargar Google.'))
    }
    document.head.appendChild(s)
  })
  return cargando
}

/** Boton "Acceder con Google". No aparece si el servidor no tiene ID de cliente. */
export function GoogleButton({ onCredential }: { onCredential: (credential: string) => void }) {
  const caja = useRef<HTMLDivElement>(null)
  const [activo, setActivo] = useState(false)
  // El callback de Google se fija una vez: con la ref siempre llama al ultimo
  const aviso = useRef(onCredential)
  aviso.current = onCredential

  useEffect(() => {
    let cancelado = false
    getAuthConfig()
      .then(async ({ google_client_id }) => {
        if (!google_client_id) return
        const id = await cargarGoogle()
        if (cancelado || !caja.current) return
        id.initialize({ client_id: google_client_id, callback: (r) => aviso.current(r.credential) })
        id.renderButton(caja.current, {
          theme: 'filled_black',
          size: 'large',
          text: 'signin_with',
          shape: 'pill',
          locale: 'es',
          width: caja.current.offsetWidth || 300,
        })
        setActivo(true)
      })
      .catch(() => undefined)
    return () => {
      cancelado = true
    }
  }, [])

  return (
    <>
      {activo && <div className="login__separador muted">o</div>}
      <div ref={caja} className="login__google" />
    </>
  )
}
