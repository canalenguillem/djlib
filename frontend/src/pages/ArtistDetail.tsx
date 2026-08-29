import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import * as artistsApi from '../api/artists'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { formatDuration } from '../lib/format'
import type { Artist, EnrichmentStatus, Track } from '../types/api'

const STATUS_TEXT: Record<EnrichmentStatus, string> = {
  pending: 'Consultando MusicBrainz y Wikipedia...',
  ok: 'Datos de MusicBrainz y Wikipedia',
  not_found: 'Las fuentes externas no lo conocen',
  error: 'Fallo al consultar las fuentes',
  manual: 'Ficha editada a mano',
}

export function ArtistDetailPage() {
  const { artistId } = useParams()
  const navigate = useNavigate()
  const id = Number(artistId)

  const [artist, setArtist] = useState<Artist | null>(null)
  const [tracks, setTracks] = useState<Track[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)

  const [form, setForm] = useState({ name: '', bio: '', country: '', begin_year: '', end_year: '' })

  const load = useCallback(async () => {
    try {
      const [ficha, canciones] = await Promise.all([
        artistsApi.getArtist(id),
        artistsApi.getArtistTracks(id),
      ])
      setArtist(ficha)
      setTracks(canciones)
      setForm({
        name: ficha.name,
        bio: ficha.bio ?? '',
        country: ficha.country ?? '',
        begin_year: ficha.begin_year ? String(ficha.begin_year) : '',
        end_year: ficha.end_year ? String(ficha.end_year) : '',
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la ficha.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  // Si la ficha acaba de crearse, sus datos estan en camino: se espera a que
  // lleguen en vez de dejar al usuario mirando una ficha vacia.
  useEffect(() => {
    if (artist?.enrichment_status !== 'pending') return
    const timer = window.setInterval(() => void load(), 4000)
    return () => window.clearInterval(timer)
  }, [artist?.enrichment_status, load])

  async function handleEnrich(force: boolean) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const actualizado = await artistsApi.enrichArtist(id, force)
      setArtist(actualizado)
      setNotice(
        actualizado.enrichment_status === 'ok'
          ? 'Ficha actualizada desde MusicBrainz y Wikipedia.'
          : STATUS_TEXT[actualizado.enrichment_status],
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo consultar las fuentes.')
    } finally {
      setBusy(false)
    }
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const actualizado = await artistsApi.updateArtist(id, {
        name: form.name.trim(),
        bio: form.bio.trim() || null,
        country: form.country.trim() || null,
        begin_year: form.begin_year ? Number(form.begin_year) : null,
        end_year: form.end_year ? Number(form.end_year) : null,
      })
      setArtist(actualizado)
      setEditing(false)
      setNotice('Ficha guardada. El enriquecido automatico ya no la sobrescribira.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    setBusy(true)
    try {
      await artistsApi.deleteArtist(id)
      navigate('/artists', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo borrar.')
      setBusy(false)
    }
  }

  if (loading) return <Loading />
  if (!artist) return <Alert kind="error">{error ?? 'Artista no encontrado.'}</Alert>

  const years = [artist.begin_year, artist.end_year].filter(Boolean).join(' – ')

  return (
    <div className="stack">
      <Link to="/artists" className="muted">
        ← Artistas
      </Link>
      <h1>{artist.name}</h1>

      {error && <Alert kind="error">{error}</Alert>}
      {notice && <Alert kind="info">{notice}</Alert>}

      <section className="card">
        <div className="artist__head">
          <dl className="datalist">
            {artist.country && (
              <div>
                <dt>Origen</dt>
                <dd>{artist.country}</dd>
              </div>
            )}
            {years && (
              <div>
                <dt>Activo</dt>
                <dd>{years}</dd>
              </div>
            )}
            {artist.artist_type && (
              <div>
                <dt>Tipo</dt>
                <dd>{artist.artist_type === 'Group' ? 'Grupo' : artist.artist_type}</dd>
              </div>
            )}
            <div>
              <dt>Canciones</dt>
              <dd>{artist.track_count}</dd>
            </div>
          </dl>
          <div className="artist__actions">
            <button
              type="button"
              className="btn btn--ghost"
              disabled={busy}
              onClick={() => setEditing((v) => !v)}
            >
              {editing ? 'Cancelar edicion' : 'Editar ficha'}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={busy}
              onClick={() => handleEnrich(artist.enrichment_status === 'manual')}
            >
              {artist.enrichment_status === 'manual'
                ? 'Rehacer desde las fuentes'
                : 'Actualizar desde las fuentes'}
            </button>
            <button type="button" className="btn btn--ghost btn--danger" disabled={busy} onClick={handleDelete}>
              Borrar ficha
            </button>
          </div>
        </div>

        {editing ? (
          <form className="stack" onSubmit={handleSave}>
            <label className="field">
              <span>Nombre</span>
              <input
                type="text"
                value={form.name}
                required
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </label>
            <label className="field">
              <span>Biografia</span>
              <textarea
                rows={6}
                value={form.bio}
                onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))}
              />
            </label>
            <div className="grid-form">
              <label className="field">
                <span>Pais</span>
                <input
                  type="text"
                  value={form.country}
                  onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))}
                />
              </label>
              <label className="field">
                <span>Ano de inicio</span>
                <input
                  type="number"
                  value={form.begin_year}
                  min={1000}
                  max={2999}
                  onChange={(e) => setForm((f) => ({ ...f, begin_year: e.target.value }))}
                />
              </label>
              <label className="field">
                <span>Ano de fin</span>
                <input
                  type="number"
                  value={form.end_year}
                  min={1000}
                  max={2999}
                  onChange={(e) => setForm((f) => ({ ...f, end_year: e.target.value }))}
                />
              </label>
            </div>
            <div>
              <button type="submit" className="btn btn--primary" disabled={busy}>
                Guardar ficha
              </button>
            </div>
          </form>
        ) : (
          <>
            {artist.bio ? (
              <p className="artist__bio">{artist.bio}</p>
            ) : artist.enrichment_status === 'pending' ? (
              <Loading label="Consultando MusicBrainz y Wikipedia..." />
            ) : (
              <p className="muted">Sin biografia. Puedes escribirla tu desde "Editar ficha".</p>
            )}
            <p className="muted artist__source">
              {STATUS_TEXT[artist.enrichment_status]}
              {artist.enrichment_error ? `: ${artist.enrichment_error}` : ''}
              {artist.wikipedia_url && (
                <>
                  {' · '}
                  <a href={artist.wikipedia_url} target="_blank" rel="noreferrer">
                    Wikipedia
                  </a>
                </>
              )}
            </p>
          </>
        )}
      </section>

      {artist.relations.length > 0 && (
        <section className="card">
          <h2>Relaciones</h2>
          <ul className="relations">
            {artist.relations.map((relation) => (
              <li key={relation.id}>
                <span className="badge">{relation.relation_type}</span>
                {relation.related_artist_id ? (
                  <Link to={`/artists/${relation.related_artist_id}`}>{relation.related_name}</Link>
                ) : (
                  <span>{relation.related_name}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h2>En la biblioteca</h2>
        {tracks.length === 0 ? (
          <p className="muted">Ninguna cancion suya todavia.</p>
        ) : (
          <ul className="tracklist">
            {tracks.map((track) => (
              <li key={track.id} className="track">
                <div className="track__main">
                  <div className="track__info">
                    <div className="track__title">{track.title}</div>
                    <div className="track__meta">
                      <span>{formatDuration(track.duration_seconds)}</span>
                      {track.tags.map((tag) => (
                        <span key={tag.id} className={`chip chip--${tag.kind}`}>
                          {tag.name}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
