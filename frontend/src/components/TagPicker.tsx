import { useState } from 'react'

import type { Tag, TagKind } from '../types/api'

const KIND_LABEL: Record<TagKind, string> = {
  mood: 'Mood',
  style: 'Estilo',
  moment: 'Momento',
}

const KINDS: TagKind[] = ['mood', 'style', 'moment']

interface Props {
  allTags: Tag[]
  selected: number[]
  onSave: (tagIds: number[]) => Promise<void>
  onCancel: () => void
}

/** Editor de etiquetas de una cancion, agrupado por los tres ejes. */
export function TagPicker({ allTags, selected, onSave, onCancel }: Props) {
  const [picked, setPicked] = useState<number[]>(selected)
  const [saving, setSaving] = useState(false)

  function toggle(id: number) {
    setPicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await onSave(picked)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="tagpicker">
      {KINDS.map((kind) => {
        const tags = allTags.filter((t) => t.kind === kind)
        return (
          <div key={kind} className="tagpicker__group">
            <span className="tagpicker__label">{KIND_LABEL[kind]}</span>
            {tags.length === 0 ? (
              <span className="muted">sin etiquetas de este tipo</span>
            ) : (
              <div className="chips">
                {tags.map((tag) => (
                  <button
                    key={tag.id}
                    type="button"
                    className={picked.includes(tag.id) ? 'chip chip--on' : 'chip'}
                    aria-pressed={picked.includes(tag.id)}
                    onClick={() => toggle(tag.id)}
                  >
                    {tag.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      })}
      <div className="tagpicker__actions">
        <button type="button" className="btn btn--primary" disabled={saving} onClick={handleSave}>
          {saving ? 'Guardando...' : 'Guardar etiquetas'}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
