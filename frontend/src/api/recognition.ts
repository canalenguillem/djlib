import type { RecognitionResult, RecognitionStatus, ScreenshotResult } from '../types/api'
import { apiFetch, apiFetchForm } from './client'

export function getRecognitionStatus(): Promise<RecognitionStatus> {
  return apiFetch<RecognitionStatus>('/recognize/status')
}

export function recognizeAudio(blob: Blob, filename: string): Promise<RecognitionResult> {
  const form = new FormData()
  form.append('audio', blob, filename)
  return apiFetchForm<RecognitionResult>('/recognize', form)
}

/** Lee las canciones que aparecen en una captura de pantalla. */
export function readScreenshot(file: File): Promise<ScreenshotResult> {
  const form = new FormData()
  form.append('image', file, file.name)
  return apiFetchForm<ScreenshotResult>('/recognize/screenshot', form)
}
