import type { RecognitionResult, RecognitionStatus } from '../types/api'
import { apiFetch, apiFetchForm } from './client'

export function getRecognitionStatus(): Promise<RecognitionStatus> {
  return apiFetch<RecognitionStatus>('/recognize/status')
}

export function recognizeAudio(blob: Blob, filename: string): Promise<RecognitionResult> {
  const form = new FormData()
  form.append('audio', blob, filename)
  return apiFetchForm<RecognitionResult>('/recognize', form)
}
