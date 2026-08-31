export type UserRole = 'admin' | 'user'

export interface User {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
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
}

export interface TrackPage {
  items: Track[]
  total: number
  limit: number
  offset: number
}

export type TrackSort = 'recent' | 'energy' | 'energy_asc' | 'title'

export interface TrackFilters {
  search?: string
  status?: TrackStatus
  tagIds?: number[]
  energyMin?: number
  sort?: TrackSort
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
