import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GitBranch, CheckCircle2, XCircle, ArrowRight, Loader2 } from 'lucide-react'
import { ingestRepo, getIngestStatus, getLanguages } from '../lib/api'
import { IngestStages, Spinner, ErrorBanner } from '../components/Primitives.jsx'
import { formatNumber } from '../lib/utils'

const STORAGE_KEY = 'reposcan.ingest.tasks'

function loadTasks() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []
  } catch {
    return []
  }
}
function saveTasks(tasks) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks.slice(0, 10)))
}

export default function Ingest() {
  const [repoUrl, setRepoUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState(loadTasks)
  const [languages, setLanguages] = useState(null)
  const pollRefs = useRef({})

  useEffect(() => {
    getLanguages().then(setLanguages).catch(() => setLanguages(false))
  }, [])

  useEffect(() => {
    tasks
      .filter((t) => t.status !== 'completed' && t.status !== 'failed')
      .forEach((t) => startPolling(t.task_id))
    return () => Object.values(pollRefs.current).forEach(clearInterval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updateTask(taskId, patch) {
    setTasks((prev) => {
      const next = prev.map((t) => (t.task_id === taskId ? { ...t, ...patch } : t))
      saveTasks(next)
      return next
    })
  }

  function startPolling(taskId) {
    if (pollRefs.current[taskId]) return
    const id = setInterval(async () => {
      try {
        const data = await getIngestStatus(taskId)
        updateTask(taskId, data)
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRefs.current[taskId])
          delete pollRefs.current[taskId]
        }
      } catch (err) {
        updateTask(taskId, { status: 'failed', error: err.message })
        clearInterval(pollRefs.current[taskId])
        delete pollRefs.current[taskId]
      }
    }, 2000)
    pollRefs.current[taskId] = id
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!repoUrl.trim()) return
    setSubmitting(true)
    try {
      const data = await ingestRepo(repoUrl.trim())
      const task = { ...data, progress: null }
      setTasks((prev) => {
        const next = [task, ...prev.filter((t) => t.task_id !== task.task_id)]
        saveTasks(next)
        return next
      })
      setRepoUrl('')
      startPolling(data.task_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-14">
      <p className="eyebrow mb-3">Module 1 · Ingestion</p>
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">
        Bring a repository into the index
      </h1>
      <p className="text-muted mt-3 max-w-xl">
        RepoScan clones the repo, parses every source file at function and class boundaries
        with Tree-sitter, embeds each chunk, and stores it in ChromaDB. Large repos take a
        few minutes — you can leave this page and come back.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 panel-raised p-2 flex items-center gap-2">
        <div className="pl-3 text-faint">
          <GitBranch size={16} />
        </div>
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/tiangolo/fastapi"
          className="flex-1 bg-transparent px-2 py-3 font-mono text-sm placeholder:text-faint focus:outline-none"
        />
        <button type="submit" disabled={submitting} className="btn-primary shrink-0">
          {submitting ? <Loader2 size={15} className="animate-spin" /> : <>Index repo <ArrowRight size={15} /></>}
        </button>
      </form>
      <ErrorBanner message={error} />

      {languages && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {languages.languages.map((l) => (
            <span key={l.language} className="chip">
              {l.language}
            </span>
          ))}
        </div>
      )}

      <div className="mt-12">
        <h2 className="font-display text-lg font-semibold mb-4">Ingestion history</h2>
        {tasks.length === 0 && (
          <p className="text-sm text-faint">Nothing indexed in this browser yet.</p>
        )}
        <div className="space-y-4">
          <AnimatePresence>
            {tasks.map((task) => (
              <motion.div
                key={task.task_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="panel p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-mono text-sm text-ink truncate">{task.repo_url}</p>
                    <p className="text-xs text-faint mt-1 truncate">{task.message}</p>
                  </div>
                  {task.status === 'completed' && (
                    <CheckCircle2 size={18} className="text-signal-green shrink-0" />
                  )}
                  {task.status === 'failed' && (
                    <XCircle size={18} className="text-signal-red shrink-0" />
                  )}
                  {task.status !== 'completed' && task.status !== 'failed' && (
                    <Spinner size={18} />
                  )}
                </div>

                <div className="mt-4">
                  <IngestStages status={task.status} />
                </div>

                {task.progress && (
                  <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs font-mono text-muted">
                    {Object.entries(task.progress).map(([k, v]) => (
                      <span key={k}>
                        {k.replaceAll('_', ' ')}: <span className="text-ink">{formatNumber(v)}</span>
                      </span>
                    ))}
                  </div>
                )}

                {task.result && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {task.result.languages_found?.map((l) => (
                      <span key={l} className="chip">{l}</span>
                    ))}
                    <span className="chip">repo_id: {task.repo_id}</span>
                  </div>
                )}

                {task.error && (
                  <p className="mt-3 text-xs font-mono text-signal-red">{task.error}</p>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
