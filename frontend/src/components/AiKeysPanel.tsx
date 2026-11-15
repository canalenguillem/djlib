import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import * as aiApi from '../api/ai'
import type { AiProvider, AiSettings } from '../types/api'
import { Alert } from './Alert'

/** Las claves de IA del usuario: una por proveedor, y cual se usa. Hoy sirven
 *  para leer canciones de capturas de pantalla; cada uno paga lo suyo. */
export function AiKeysPanel() {
  const [ajustes, setAjustes] = useState<AiSettings | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    aiApi
      .getAiSettings()
      .then(setAjustes)
      .catch((err) => setError(err instanceof Error ? err.message : 'No se pudieron cargar las claves.'))
  }, [])

  async function elegir(id: AiProvider['id']) {
    setError(null)
    try {
      setAjustes(await aiApi.selectAiProvider(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo elegir el proveedor.')
    }
  }

  return (
    <section className="card stack">
      <h2>Inteligencia artificial</h2>
      <p className="muted">
        Se usa para leer las canciones de una captura de pantalla (Reconocer). Pon la clave de
        tu cuenta de OpenAI, Anthropic o Grok: cada uno paga lo que usa. Puedes poner varias y
        elegir cuál se usa. Las claves se guardan cifradas y no se vuelven a mostrar.
      </p>
      {error && <Alert kind="error">{error}</Alert>}
      {ajustes && (
        <div className="aikeys">
          {ajustes.providers.map((p) => (
            <ProveedorIa
              key={p.id}
              proveedor={p}
              elegido={ajustes.selected === p.id}
              onElegir={() => void elegir(p.id)}
              onCambio={setAjustes}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function ProveedorIa({
  proveedor: p,
  elegido,
  onElegir,
  onCambio,
}: {
  proveedor: AiProvider
  elegido: boolean
  onElegir: () => void
  onCambio: (ajustes: AiSettings) => void
}) {
  const [clave, setClave] = useState('')
  const [modelo, setModelo] = useState(p.model ?? '')
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null)

  useEffect(() => setModelo(p.model ?? ''), [p.model])

  async function guardar(e: FormEvent) {
    e.preventDefault()
    setOcupado(true)
    setAviso(null)
    try {
      onCambio(await aiApi.saveAiKey(p.id, clave.trim() || null, modelo.trim() || null))
      setClave('')
      // Recien puesta, se prueba: asi se sabe ya si vale
      const prueba = await aiApi.testAiKey(p.id)
      setAviso({ ok: prueba.ok, texto: prueba.message })
    } catch (err) {
      setAviso({ ok: false, texto: err instanceof Error ? err.message : 'No se pudo guardar.' })
    } finally {
      setOcupado(false)
    }
  }

  async function probar() {
    setOcupado(true)
    setAviso(null)
    try {
      const prueba = await aiApi.testAiKey(p.id)
      setAviso({ ok: prueba.ok, texto: prueba.message })
    } finally {
      setOcupado(false)
    }
  }

  async function borrar() {
    if (!window.confirm(`¿Borrar tu clave de ${p.name}?`)) return
    setOcupado(true)
    setAviso(null)
    try {
      onCambio(await aiApi.deleteAiKey(p.id))
      setModelo('')
    } catch (err) {
      setAviso({ ok: false, texto: err instanceof Error ? err.message : 'No se pudo borrar.' })
    } finally {
      setOcupado(false)
    }
  }

  return (
    <form className={elegido ? 'aikey aikey--on' : 'aikey'} onSubmit={guardar}>
      <div className="aikey__cabecera">
        <label className="aikey__elegir">
          <input
            type="radio"
            name="proveedor-ia"
            checked={elegido}
            disabled={!p.configured}
            onChange={onElegir}
          />
          <strong>{p.name}</strong>
        </label>
        {elegido && <span className="badge badge--ok">el que se usa</span>}
        {p.configured ? (
          <span className="muted">clave ····{p.key_hint}</span>
        ) : (
          <a className="muted" href={p.console_url} target="_blank" rel="noreferrer">
            Conseguir una clave ↗
          </a>
        )}
      </div>
      <div className="aikey__campos">
        <label className="field">
          <span>{p.configured ? 'Cambiar la clave' : 'Clave'}</span>
          <input
            type="password"
            value={clave}
            autoComplete="off"
            placeholder={p.configured ? 'Déjala vacía para no cambiarla' : 'Pega aquí tu clave'}
            onChange={(e) => setClave(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Modelo</span>
          <input
            value={modelo}
            placeholder={p.default_model}
            onChange={(e) => setModelo(e.target.value)}
          />
        </label>
      </div>
      <div className="aikey__acciones">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={ocupado || (!p.configured && !clave.trim())}
        >
          {ocupado ? 'Un momento...' : 'Guardar'}
        </button>
        {p.configured && (
          <>
            <button type="button" className="btn btn--ghost" disabled={ocupado} onClick={() => void probar()}>
              Probar
            </button>
            <button type="button" className="btn btn--ghost" disabled={ocupado} onClick={() => void borrar()}>
              Borrar
            </button>
          </>
        )}
      </div>
      {aviso && <Alert kind={aviso.ok ? 'success' : 'error'}>{aviso.texto}</Alert>}
    </form>
  )
}
