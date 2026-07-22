import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, Layers, ChevronLeft, ChevronRight, X, FileText, Database } from 'lucide-react'
import { getRepos, deleteRepo, getChunks } from '../lib/api'
import { formatNumber, shortRepoName, timeAgo } from '../lib/utils'
import { LanguageBadge, Spinner, EmptyState, CodeSnippet, ErrorBanner } from '../components/Primitives.jsx'

export default function Repos() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState(null)
  const [error, setError] = useState('')
  const [confirmId, setConfirmId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [browsing, setBrowsing] = useState(null)

  const load = () => getRepos().then((r) => setRepos(r.repos || [])).catch((e) => setError(e.message))

  useEffect(() => {
    load()
    const focus = searchParams.get('focus')
    if (focus) setBrowsing(focus)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleDelete(repoId) {
    setDeletingId(repoId)
    try {
      await deleteRepo(repoId)
      setRepos((prev) => prev.filter((r) => r.repo_id !== repoId))
      setConfirmId(null)
      if (browsing === repoId) setBrowsing(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-14">
      <p className="eyebrow mb-3">Module 3 · Repo management</p>
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">Indexed repositories</h1>
      <p className="text-muted mt-3 max-w-xl">
        Every repo currently stored in ChromaDB. Browse its chunks or remove it entirely.
      </p>

      <ErrorBanner message={error} />

      {repos === null && (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      )}

      {Array.isArray(repos) && repos.length === 0 && (
        <div className="mt-8">
          <EmptyState icon={Database} title="Nothing indexed yet" hint="Head to Ingest to add your first repository." />
        </div>
      )}

      {Array.isArray(repos) && repos.length > 0 && (
        <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {repos.map((repo) => (
            <div key={repo.repo_id} className="panel card-hover p-5 flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-sm text-ink truncate">{shortRepoName(repo.repo_url)}</p>
                  <p className="text-xs text-faint mt-1">{repo.repo_id}</p>
                </div>
                <button
                  onClick={() => setConfirmId(repo.repo_id)}
                  className="shrink-0 p-2 rounded-lg text-faint hover:text-signal-red hover:bg-signal-red/10 transition-colors"
                  aria-label={`Delete ${repo.repo_id}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>

              <div className="flex items-center gap-3 mt-4 text-xs text-muted font-mono">
                <span>{formatNumber(repo.chunks_stored)} chunks</span>
                <span>·</span>
                <span>{formatNumber(repo.files_processed)} files</span>
              </div>
              <p className="text-xs text-faint mt-1">indexed {timeAgo(repo.ingested_at)}</p>

              <div className="flex flex-wrap gap-1.5 mt-3">
                {repo.languages_found?.map((l) => (
                  <LanguageBadge key={l} language={l} />
                ))}
              </div>

              <button
                onClick={() => setBrowsing(repo.repo_id)}
                className="btn-ghost text-xs !py-1.5 mt-4 w-full"
              >
                <Layers size={13} /> Browse chunks
              </button>

              {confirmId === repo.repo_id && (
                <div className="mt-3 rounded-lg border border-signal-red/30 bg-signal-red/10 p-3">
                  <p className="text-xs text-ink mb-2">Delete this repo and all {formatNumber(repo.chunks_stored)} chunks?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(repo.repo_id)}
                      disabled={deletingId === repo.repo_id}
                      className="text-xs font-medium bg-signal-red text-void rounded-md px-3 py-1.5"
                    >
                      {deletingId === repo.repo_id ? <Spinner size={12} className="!text-void" /> : 'Delete'}
                    </button>
                    <button
                      onClick={() => setConfirmId(null)}
                      className="text-xs font-medium text-muted rounded-md px-3 py-1.5 border border-border"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <AnimatePresence>
        {browsing && <ChunkDrawer repoId={browsing} onClose={() => setBrowsing(null)} />}
      </AnimatePresence>
    </div>
  )
}

function ChunkDrawer({ repoId, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 8

  useEffect(() => {
    setData(null)
    getChunks(repoId, { limit, offset })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [repoId, offset])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] bg-void/70 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        onClick={(e) => e.stopPropagation()}
        className="w-full sm:max-w-2xl h-full bg-surface border-l border-border overflow-y-auto"
      >
        <div className="sticky top-0 bg-surface/95 backdrop-blur border-b border-border px-6 py-5 flex items-center justify-between">
          <div>
            <p className="eyebrow">chunk browser</p>
            <p className="font-mono text-sm text-ink mt-1">{repoId}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg text-faint hover:text-ink hover:bg-border/60">
            <X size={18} />
          </button>
        </div>

        <div className="p-6">
          <ErrorBanner message={error} />
          {!data && !error && (
            <div className="flex justify-center py-16">
              <Spinner />
            </div>
          )}

          {data && (
            <>
              <p className="text-xs text-faint font-mono mb-4">
                showing {data.chunks.length} of {formatNumber(data.total)}
              </p>
              <div className="space-y-3">
                {data.chunks.map((c) => (
                  <div key={c.chunk_id} className="rounded-xl border border-border bg-void/40 p-4">
                    <div className="flex items-center gap-1.5 mb-2">
                      <FileText size={12} className="text-faint" />
                      <span className="font-mono text-xs text-ink truncate">
                        {c.file_path}:{c.start_line}-{c.end_line}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mb-3">
                      <LanguageBadge language={c.language} />
                      <span className="chip">{c.chunk_type}</span>
                      {c.name && <span className="chip">{c.name}</span>}
                      {c.truncated && <span className="chip !text-amber-400 !border-amber-400/30">truncated</span>}
                    </div>
                    <div className="rounded-lg bg-void/60 border border-border p-3">
                      <CodeSnippet text={c.text} maxLines={10} />
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between mt-6">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset((o) => Math.max(0, o - limit))}
                  className="btn-ghost text-xs !py-1.5 disabled:opacity-30"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                <span className="text-xs font-mono text-faint">
                  offset {offset} / {formatNumber(data.total)}
                </span>
                <button
                  disabled={offset + limit >= data.total}
                  onClick={() => setOffset((o) => o + limit)}
                  className="btn-ghost text-xs !py-1.5 disabled:opacity-30"
                >
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}
