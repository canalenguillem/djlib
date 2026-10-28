export type UserRole = 'admin' | 'user'

export type Menu =
  | 'library'
  | 'recognize'
  | 'mixer'
  | 'spotify'
  | 'beatport'
  | 'crates'
  | 'downloads'
  | 'listen'
  | 'artists'
  | 'tags'

export interface User {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  menus: Menu[]
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface CreateUserPayload {
  username: string
  email?: string | null
  password: string
  role: UserRole
}

export interface UpdateUserPayload {
  is_active?: boolean
  role?: UserRole
  menus?: Menu[]
}

export type TrackStatus = 'pending' | 'downloading' | 'ready' | 'error'
export type IngestSource = 'url' | 'search' | 'recognition' | 'upload'
export type TagKind = 'mood' | 'style' | 'moment'

export interface Tag {
  id: number
  kind: TagKind
  name: string
  slug: string
  created_at: string
}

export interface Track {
  id: number
  title: string
  artist_text: string | null
  duration_seconds: number | null
  ingest_source: IngestSource
  request_query: string
  source_url: string | null
  source_site: string | null
  source_video_id: string | null
  status: TrackStatus
  error_message: string | null
  file_size: number | null
  bpm: number | null
  energy: number | null
  thumbnail_url: string | null
  added_by_user_id: number | null
  downloaded_at: string | null
  created_at: string
  updated_at: string
  tags: Tag[]
  artists: ArtistBrief[]
  /** Crates en los que esta, del primero en que entro al ultimo. */
  crate_ids: number[]
  /** Crate al que ira cuando termine de descargarse. */
  pending_crate_id: number | null
}

export interface TrackPage {
  items: Track[]
  total: number
  limit: number
  offset: number
}

export type TrackSort = 'recent' | 'energy' | 'energy_asc' | 'bpm' | 'title'

export interface TrackFilters {
  search?: string
  status?: TrackStatus
  tagIds?: number[]
  energyMin?: number
  bpmMin?: number
  bpmMax?: number
  sort?: TrackSort
  limit?: number
  offset?: number
}

export type EnrichmentStatus = 'pending' | 'ok' | 'youtube' | 'not_found' | 'error' | 'manual'

export interface ArtistBrief {
  id: number
  name: string
  slug: string
}

export interface ArtistRelation {
  id: number
  related_name: string
  relation_type: string
  related_artist_id: number | null
}

export interface Artist {
  id: number
  name: string
  slug: string
  bio: string | null
  country: string | null
  begin_year: number | null
  end_year: number | null
  artist_type: string | null
  musicbrainz_id: string | null
  wikipedia_url: string | null
  image_url: string | null
  channel_url: string | null
  follower_count: number | null
  links: Record<string, string>
  genres: string[]
  enrichment_status: EnrichmentStatus
  enrichment_error: string | null
  enriched_at: string | null
  created_at: string
  updated_at: string
  relations: ArtistRelation[]
  track_count: number
}

export interface ArtistPage {
  items: Artist[]
  total: number
  limit: number
  offset: number
}

export interface SearchCandidate {
  video_id: string
  title: string
  channel: string | null
  duration_seconds: number | null
  url: string
  thumbnail_url: string | null
  already_in_library: boolean
  too_long: boolean
  /** Si ya esta en la biblioteca, cual es y en que crate. */
  track_id: number | null
  crate_ids: number[]
  pending_crate_id: number | null
}

export interface SearchResults {
  query: string
  candidates: SearchCandidate[]
}

export interface RecognitionStatus {
  enabled: boolean
  provider: string | null
  screenshot_enabled: boolean
}

export interface DetectedSong {
  title: string
  artist: string | null
}

export interface ScreenshotResult {
  songs: DetectedSong[]
}

export interface RecognitionResult {
  recognized: boolean
  artist: string | null
  title: string | null
  album: string | null
  release_date: string | null
  song_link: string | null
  candidates: SearchCandidate[]
}

export interface CrateSummary {
  id: number
  name: string
  slug: string
  description: string | null
  created_by_user_id: number | null
  created_at: string
  updated_at: string
  track_count: number
  total_seconds: number
}

export interface Crate extends CrateSummary {
  tracks: Track[]
}

export interface SpotifyStatus {
  enabled: boolean
  connected: boolean
  display_name: string | null
}

export interface PlayedTrack {
  title: string
  artist: string
  album: string | null
  played_at: string | null
  spotify_url: string | null
  image_url: string | null
  already_in_library: boolean
}

export interface SpotifyPlaylist {
  id: string
  name: string
  total: number
  owner: string | null
  image_url: string | null
}

export interface SpotifyPlaylistTracks {
  name: string
  items: PlayedTrack[]
}

export interface ShazamTracks {
  /** Nombre de la playlist; null si la cuenta no tiene ninguna de Shazam. */
  playlist: string | null
  items: PlayedTrack[]
}

/** Forma de onda en tres bandas, un valor de 0 a 255 por tramo. */
export interface Waveform {
  bins: number
  low: number[]
  mid: number[]
  high: number[]
}

export type BatchItemStatus =
  | 'pending'
  | 'searching'
  | 'downloading'
  | 'done'
  | 'already'
  | 'not_found'
  | 'error'
  | 'cancelled'

export interface BatchItem {
  id: number
  position: number
  title: string
  artist: string | null
  status: BatchItemStatus
  video_title: string | null
  track_id: number | null
  message: string | null
}

export interface BatchSummary {
  id: number
  name: string
  crate_id: number | null
  crate_name: string | null
  status: 'active' | 'done' | 'cancelled'
  created_at: string
  total: number
  counts: Partial<Record<BatchItemStatus, number>>
  /** Lo que se esta buscando o descargando ahora mismo. */
  current: string[]
}

export interface Batch extends BatchSummary {
  items: BatchItem[]
}

export type ListenSource = 'player' | 'mixer'

export interface ListenCounts {
  player: number
  mixer: number
}

export interface UserListens {
  user_id: number | null
  username: string | null
  total: ListenCounts
  last_7_days: ListenCounts
  last_listen_at: string | null
}

export interface TopTrack {
  track_id: number
  title: string
  artist_text: string | null
  player: number
  mixer: number
}

export interface ListenStats {
  users: UserListens[]
  top_tracks: TopTrack[]
}

export interface BeatportGenre {
  id: number
  name: string
}

export interface BeatportTrack {
  position: number
  /** Con la mezcla: "Zoolander (Extended Mix)". Es lo que se busca. */
  title: string
  name: string
  mix: string | null
  artist: string
  remixers: string | null
  bpm: number | null
  key: string | null
  genre: string | null
  label: string | null
  length: string | null
  release_date: string | null
  image_url: string | null
  sample_url: string | null
  beatport_url: string
  already_in_library: boolean
}

export interface BeatportTop {
  genre: BeatportGenre | null
  items: BeatportTrack[]
}
