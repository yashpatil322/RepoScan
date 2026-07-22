import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { SendHorizonal, Zap, ZapOff, FileText, Sparkles } from 'lucide-react'
import { getRepos, query, queryStream } from '../lib/api'
import { splitAnswerIntoSegments } from '../lib/utils'
import { ErrorBanner, ScoreBar, LanguageBadge, Spinner, EmptyState } from '../components/Primitives.jsx'

export default function Ask() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState([])
  const [repoId, setRepoId] = useState('')
  const [topK, setTopK] = useState(5)
  const [streaming, setStreaming] = useState(true)
  const [question, setQuestion] = useState(searchParams.get('q') || '')
  const [thread, setThread] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    getRepos().then((r) => setRepos(r.repos || [])).catch(() => setRepos([]))
  }, [])

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) handleAsk(q)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread, loading])

  async function handleAsk(overrideQuestion) {
    const q = (overrideQuestion ?? question).trim()
    if (!q || loading) return
    setError('')
    setQuestion('')
    setLoading(true)

    const entry = { id: Date.now(), question: q, answer: '', sources: [], citations: [], done: false }
    setThread((prev) => [...prev, entry])

    const payload = { question: q, repo_id: repoId || null, top_k: topK }

    if (streaming) {
      abortRef.current = new AbortController()
      await queryStream(payload, {
        signal: abortRef.current.signal,
        onToken: (token) => {
          setThread((prev) =>
            prev.map((t) => (t.id === entry.id ? { ...t, answer: t.answer + token } : t))
          )
        },
        onDone: (final) => {
          setThread((prev) =>
            prev.map((t) =>
              t.id === entry.id
                ? { ...t, sources: final.sources || [], citations: final.citations || [], done: true }
                : t
            )
          )
          setLoading(false)
        },
        onError: (err) => {
          setError(err.message)
          setLoading(false)
        },
      })
    } else {
      try {
        const data = await query(payload)
        setThread((prev) =>
          prev.map((t) =>
            t.id === entry.id
              ? { ...t, answer: data.answer, sources: data.sources, citations: data.citations, done: true }
              : t
          )
        )
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
  }

  const canAsk = useMemo(() => question.trim().length >= 3, [question])

  return (
    <div className="max-w-4xl mx-auto px-6 py-14">
      <p className="eyebrow mb-3">Module 2 · Query</p>
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">Ask a question</h1>
      <p className="text-muted mt-3 max-w-xl">
        Retrieves the most relevant code chunks by cosine similarity, then hands them to
        Gemini to write a cited answer.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <select
          value={repoId}
          onChange={(e) => setRepoId(e.target.value)}
          className="input-field !w-auto max-w-[220px]"
        >
          <option value="">All repos</option>
          {repos.map((r) => (
            <option key={r.repo_id} value={r.repo_id}>
              {r.repo_id}
            </option>
          ))}
        </select>

        <label className="flex items-center gap-2 text-xs font-mono text-muted">
          top_k
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="input-field !w-16 !py-1.5 text-center"
          />
        </label>

        <button
          onClick={() => setStreaming((s) => !s)}
          className="btn-ghost text-xs !py-1.5"
          title="Toggle streaming responses"
        >
          {streaming ? <Zap size={13} /> : <ZapOff size={13} />}
          {streaming ? 'streaming on' : 'streaming off'}
        </button>
      </div>

      <ErrorBanner message={error} />

      <div className="mt-8 space-y-8">
        {thread.length === 0 && !loading && (
          <EmptyState
            icon={Sparkles}
            title="No questions yet"
            hint='Try "Where is authentication handled?" or ask about a repo you just indexed.'
          />
        )}

        <AnimatePresence>
          {thread.map((turn) => (
            <motion.div
              key={turn.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="space-y-4"
            >
              <div className="flex justify-end">
                <div className="bg-vector-500/10 border border-vector-500/25 rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] font-mono text-sm text-ink">
                  {turn.question}
                </div>
              </div>

              <div className="panel-raised p-6">
                <AnswerBody text={turn.answer} />
                {!turn.done && (
                  <div className="flex items-center gap-2 mt-3 text-faint text-xs font-mono">
                    <Spinner size={13} /> thinking in tokens…
                  </div>
                )}

                {turn.sources?.length > 0 && (
                  <div className="mt-6 pt-6 border-t border-border">
                    <p className="eyebrow mb-3">sources</p>
                    <div className="grid sm:grid-cols-2 gap-3">
                      {turn.sources.map((s, i) => (
                        <div key={i} className="rounded-xl border border-border bg-void/40 p-3.5">
                          <div className="flex items-center gap-1.5 mb-1.5 min-w-0">
                            <FileText size={12} className="text-faint shrink-0" />
                            <span className="font-mono text-xs text-ink truncate">
                              {s.file_path}:{s.start_line}-{s.end_line}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 mb-2">
                            <LanguageBadge language={s.language} />
                            <span className="chip">{s.chunk_type}</span>
                            {s.name && <span className="chip">{s.name}</span>}
                          </div>
                          <ScoreBar score={s.similarity_score} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleAsk()
        }}
        className="sticky bottom-4 mt-8 panel-raised p-2 flex items-center gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about the indexed code…"
          className="flex-1 bg-transparent px-4 py-3 font-mono text-sm placeholder:text-faint focus:outline-none"
        />
        <button type="submit" disabled={!canAsk || loading} className="btn-primary shrink-0">
          {loading ? <Spinner size={15} className="!text-void" /> : <SendHorizonal size={15} />}
        </button>
      </form>
    </div>
  )
}

function AnswerBody({ text }) {
  const segments = splitAnswerIntoSegments(text)
  if (!text) return <p className="text-faint font-mono text-sm">…</p>
  return (
    <p className="text-[15px] leading-relaxed text-ink/95 whitespace-pre-wrap">
      {segments.map((seg, i) =>
        seg.type === 'citation' ? (
          <span
            key={i}
            className="inline-flex mx-0.5 items-center rounded-md bg-vector-500/15 border border-vector-500/30 px-1.5 py-0.5 font-mono text-[12.5px] text-vector-200 align-middle"
          >
            {seg.value}
          </span>
        ) : (
          <span key={i}>{seg.value}</span>
        )
      )}
    </p>
  )
}
