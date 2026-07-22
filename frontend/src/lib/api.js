import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const http = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Normalize FastAPI's { detail: "..." } error shape into a plain message.
function unwrap(promise) {
  return promise
    .then((res) => res.data)
    .catch((err) => {
      const detail = err?.response?.data?.detail
      const message = typeof detail === 'string' ? detail : err.message || 'Request failed'
      throw new Error(message)
    })
}

// ---- Module 5: Utility ----
export const getHealth = () => unwrap(http.get('/health'))
export const getLanguages = () => unwrap(http.get('/languages'))
export const getStats = () => unwrap(http.get('/stats'))

// ---- Module 1: Ingestion ----
export const ingestRepo = (repoUrl) => unwrap(http.post('/ingest', { repo_url: repoUrl }))
export const getIngestStatus = (taskId) =>
  unwrap(http.get('/ingest/status', { params: { task_id: taskId } }))

// ---- Module 3: Repo management ----
export const getRepos = () => unwrap(http.get('/repos'))
export const deleteRepo = (repoId) => unwrap(http.delete(`/repos/${encodeURIComponent(repoId)}`))
export const getChunks = (repoId, { limit = 20, offset = 0 } = {}) =>
  unwrap(http.get(`/repos/${encodeURIComponent(repoId)}/chunks`, { params: { limit, offset } }))

// ---- Module 2: Query ----
export const query = (payload) => unwrap(http.post('/query', payload))

// Streams /query/stream via SSE-over-fetch. Calls onToken(text) as chunks arrive,
// onDone(finalPayload) when the `done` event lands, onError(err) on failure.
export async function queryStream(payload, { onToken, onDone, onError, signal }) {
  try {
    const res = await fetch(`${API_BASE_URL}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
    if (!res.ok || !res.body) {
      const body = await res.json().catch(() => null)
      throw new Error(body?.detail || `Stream failed (${res.status})`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''

      for (const raw of events) {
        if (!raw.trim()) continue
        const lines = raw.split('\n')
        let eventName = 'message'
        let dataLine = ''
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          if (line.startsWith('data:')) dataLine += line.slice(5).trim()
        }
        if (!dataLine) continue
        let parsed
        try {
          parsed = JSON.parse(dataLine)
        } catch {
          continue
        }
        if (eventName === 'token') onToken?.(parsed.token ?? '')
        if (eventName === 'done') onDone?.(parsed)
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') onError?.(err)
  }
}

// ---- Module 4: Search ----
export const search = (payload) => unwrap(http.post('/search', payload))
export const searchSimilar = (chunkId, { repoId, topK = 5 } = {}) =>
  unwrap(
    http.get(`/search/similar/${encodeURIComponent(chunkId)}`, {
      params: { repo_id: repoId, top_k: topK },
    })
  )
