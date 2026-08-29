import { useState } from 'react'
import { Link } from 'react-router-dom'

import * as tracksApi from '../api/tracks'
import { formatDuration } from '../lib/format'
import type { Tag, Track, TrackStatus } from '../types/api'
import { PauseIcon, PlayIcon } from './icons'
import { TagPicker } from './TagPicker'

const STATUS_LABEL: Record<TrackStatus, string> = {
  pending: 'en cola',
  downloading: 'descargando',
  ready: 'lista',
  error: 'error',
}

interface Props {
  track: Track
  allTags: Tag[]
  isPlaying: boolean
  onPlay: (track: Track) => void
  onChanged: (track: Track) => void
  onDeleted: (id: number) => void
  onError: (message: string) => void
}

export function TrackRow({
  track,
  allTags,
  isPlaying,
  onPlay,
  onChanged,
  onDeleted,
  onError,
}: Props) {
  const [editingTags, setEditingTags] = useState(false)
  const [busy, setBusy] = useState(false)

  const inProgress = track.status === 'pending' || track.status === 'downloading'

  async function guard(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'La operacion ha fallado.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDownload() {
    await guard(async () => {
      const blob = await tracksApi.fetchTrackFile(track.id)
      const href = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = href
      const name = [track.artist_text, track.title].filter(Boolean).join(' - ')
      link.download = `${name || 'track'}.mp3`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
    })
  }

  return (
    <li className={`track track--${track.status}`}>
      <div className="track__main">
        <button
          type="button"
          className="track__play"
          disabled={track.status !== 'ready' || busy}
          aria-label={isPlaying ? 'Reproduciendo' : `Reproducir ${track.title}`}
          onClick={() => onPlay(track)}
        >
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
        </button>

        <div className="track__info">
          <div className="track__title">{track.title}</div>
          <div className="track__meta">
            {track.artists.length > 0 ? (
              <span className="track__artists">
                {track.artists.map((artist, index) => (
                  <span key={artist.id}>
                    {index > 0 && ', '}
                    <Link to={`/artists/${artist.id}`}>{artist.name}</Link>
                  </span>
                ))}
              </span>
            ) : (
              <span>{track.artist_text ?? 'Artista desconocido'}</span>
            )}
            <span>·</span>
            <span>{formatDuration(track.duration_seconds)}</span>
            {inProgress && (
              <>
                <span>·</span>
                <span className="badge badge--busy">{STATUS_LABEL[track.status]}</span>
              </>
            )}
            {track.status === 'error' && (
              <>
                <span>·</span>
                <span className="badge badge--off">{STATUS_LABEL.error}</span>
              </>
            )}
          </div>
          {track.status === 'error' && track.error_message && (
            <div className="track__error">{track.error_message}</div>
          )}
          {track.tags.length > 0 && (
            <div className="chips chips--static">
              {track.tags.map((tag) => (
                <span key={tag.id} className={`chip chip--${tag.kind}`}>
                  {tag.name}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="track__actions">
          {track.status === 'ready' && (
            <>
              <button type="button" className="btn btn--ghost" disabled={busy} onClick={handleDownload}>
                Descargar
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => setEditingTags((v) => !v)}
              >
                Etiquetas
              </button>
            </>
          )}
          {track.status === 'error' && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={busy}
              onClick={() =>
                guard(async () => onChanged(await tracksApi.retryTrack(track.id)))
              }
            >
              Reintentar
            </button>
          )}
          <button
            type="button"
            className="btn btn--ghost btn--danger"
            disabled={busy}
            onClick={() =>
              guard(async () => {
                await tracksApi.deleteTrack(track.id)
                onDeleted(track.id)
              })
            }
          >
            Borrar
          </button>
        </div>
      </div>

      {editingTags && (
        <TagPicker
          allTags={allTags}
          selected={track.tags.map((t) => t.id)}
          onCancel={() => setEditingTags(false)}
          onSave={async (tagIds) => {
            await guard(async () => {
              onChanged(await tracksApi.setTrackTags(track.id, tagIds))
              setEditingTags(false)
            })
          }}
        />
      )}
    </li>
  )
}
