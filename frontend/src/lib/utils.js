export function timeAgo(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return date.toLocaleDateString()
}

export function formatNumber(n) {
  if (n === null || n === undefined) return '—'
  return new Intl.NumberFormat('en-US').format(n)
}

// "https://github.com/tiangolo/fastapi" -> "tiangolo/fastapi"
export function shortRepoName(url) {
  try {
    const u = new URL(url)
    return u.pathname.replace(/^\/|\/$/g, '')
  } catch {
    return url
  }
}

export const LANGUAGE_COLORS = {
  python: '#7c6fff',
  javascript: '#ffb86b',
  typescript: '#5aa9ff',
  go: '#4ade80',
  rust: '#ff8a65',
  java: '#ff6b6b',
  c: '#c9c0ff',
  cpp: '#c9c0ff',
  ruby: '#ff6b9d',
}

export function languageColor(lang) {
  return LANGUAGE_COLORS[lang?.toLowerCase()] || '#8b93a7'
}

// Parses "[file/path.py:12-45]" style markers out of an LLM answer so the UI
// can render them as inline citation chips instead of raw bracket text.
export function splitAnswerIntoSegments(text) {
  if (!text) return []
  const regex = /\[([^\]\s]+:\d+-\d+)\]/g
  const segments = []
  let lastIndex = 0
  let match
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', value: text.slice(lastIndex, match.index) })
    }
    segments.push({ type: 'citation', value: match[1] })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', value: text.slice(lastIndex) })
  }
  return segments
}

export function cx(...args) {
  return args.filter(Boolean).join(' ')
}
