import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import * as tagsApi from '../api/tags'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { CloseIcon } from '../components/icons'
import type { Tag, TagKind } from '../types/api'

const KIND_LABEL: Record<TagKind, string> = {
  mood: 'Mood',
  style: 'Estilo',
  moment: 'Momento de la noche',
}
const KIND_HINT: Record<TagKind, string> = {
  mood: 'chill, euforico, oscuro...',
  style: 'britpop, hip hop, pop espanol...',
  moment: 'warm-up, prime time, cierre...',
}
const KINDS: TagKind[] = ['mood', 'style', 'moment']

export function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<TagKind, string>>({
    mood: '',
    style: '',
    moment: '',
  })
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      setTags(await tagsApi.listTags())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron cargar las etiquetas.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleCreate(event: FormEvent, kind: TagKind) {
    event.preventDefault()
    const name = drafts[kind].trim()
    if (!name) return
    setBusy(true)
    setError(null)
    try {
      const tag = await tagsApi.createTag(kind, name)
      setTags((prev) => [...prev, tag].sort((a, b) => a.name.localeCompare(b.name)))
      setDrafts((prev) => ({ ...prev, [kind]: '' }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear la etiqueta.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(tag: Tag) {
    setBusy(true)
    setError(null)
    try {
      await tagsApi.deleteTag(tag.id)
      setTags((prev) => prev.filter((t) => t.id !== tag.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar la etiqueta.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="stack">
      <h1>Etiquetas</h1>
      <p className="muted">
        El catalogo con el que clasificas las canciones. Al ser cerrado, no acaban
        conviviendo "80s" y "Ochentas" como dos etiquetas distintas.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      {KINDS.map((kind) => {
        const ofKind = tags.filter((t) => t.kind === kind)
        return (
          <section key={kind} className="card">
            <h2>{KIND_LABEL[kind]}</h2>
            <p className="muted">{KIND_HINT[kind]}</p>

            {ofKind.length === 0 ? (
              <p className="muted">Todavia no hay ninguna.</p>
            ) : (
              <div className="chips chips--static">
                {ofKind.map((tag) => (
                  <span key={tag.id} className={`chip chip--${tag.kind}`}>
                    {tag.name}
                    <button
                      type="button"
                      className="chip__remove"
                      aria-label={`Borrar ${tag.name}`}
                      disabled={busy}
                      onClick={() => handleDelete(tag)}
                    >
                      <CloseIcon />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <form className="inline-form" onSubmit={(e) => handleCreate(e, kind)}>
              <input
                type="text"
                value={drafts[kind]}
                placeholder={`Nueva etiqueta de ${KIND_LABEL[kind].toLowerCase()}`}
                onChange={(e) => setDrafts((prev) => ({ ...prev, [kind]: e.target.value }))}
              />
              <button type="submit" className="btn btn--primary" disabled={busy}>
                Anadir
              </button>
            </form>
          </section>
        )
      })}
    </div>
  )
}
