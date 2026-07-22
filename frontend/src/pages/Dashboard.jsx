import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, GitBranch, Layers, FileCode2, Sigma } from 'lucide-react'
import EmbeddingField from '../components/EmbeddingField.jsx'
import { getStats, getRepos, getHealth } from '../lib/api'
import { formatNumber, shortRepoName, timeAgo } from '../lib/utils'
import { LanguageBadge, Spinner } from '../components/Primitives.jsx'

const SAMPLE_QUESTIONS = [
  'Where is authentication handled?',
  'How does dependency injection work?',
  'What happens when validation fails?',
  'How are background tasks scheduled?',
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [repos, setRepos] = useState(null)
  const [health, setHealth] = useState(null)
  const [question, setQuestion] = useState('')
  const [pulse, setPulse] = useState(0)

  useEffect(() => {
    getStats().then(setStats).catch(() => setStats(false))
    getRepos().then((r) => setRepos(r.repos || [])).catch(() => setRepos([]))
    getHealth().then(setHealth).catch(() => setHealth(false))
  }, [])

  useEffect(() => {
    const id = setInterval(() => setPulse((p) => p + 1), 4200)
    return () => clearInterval(id)
  }, [])

  const submitQuestion = (e) => {
    e.preventDefault()
    if (!question.trim()) return
    setPulse((p) => p + 1)
    navigate(`/ask?q=${encodeURIComponent(question.trim())}`)
  }

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <EmbeddingField pulse={pulse} className="absolute inset-0 opacity-90" />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(circle at 50% 38%, transparent 0%, transparent 30%, #0a0d14 72%)',
          }}
        />
        <div className="relative max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="eyebrow mb-5"
          >
            AST-aware retrieval · cited answers
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="font-display text-[2.6rem] sm:text-6xl font-semibold leading-[1.05] tracking-tight"
          >
            Ask your codebase
            <br />
            <span className="text-gradient">like it can talk back.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.12 }}
            className="mt-6 text-muted text-lg max-w-xl mx-auto"
          >
            Point RepoScan at any GitHub repo. It parses every file with Tree-sitter, embeds
            each function and class, and answers your questions with the exact file and line.
          </motion.p>

          <motion.form
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            onSubmit={submitQuestion}
            className="mt-10 panel-raised p-2 flex items-center gap-2 max-w-2xl mx-auto"
          >
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Where is the retry logic for failed requests?"
              className="flex-1 bg-transparent px-4 py-3 text-ink placeholder:text-faint font-mono text-sm focus:outline-none"
            />
            <button type="submit" className="btn-primary shrink-0">
              Ask <ArrowRight size={15} />
            </button>
          </motion.form>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-5 flex flex-wrap items-center justify-center gap-2"
          >
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => setQuestion(q)}
                className="text-xs font-mono text-faint hover:text-vector-400 border border-border hover:border-vector-500/40 rounded-full px-3 py-1.5 transition-colors"
              >
                {q}
              </button>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Stats strip */}
      <section className="max-w-6xl mx-auto px-6 -mt-2">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          <StatCard
            icon={GitBranch}
            label="Repos indexed"
            value={stats?.total_repos}
            loading={stats === null}
          />
          <StatCard
            icon={Layers}
            label="Chunks stored"
            value={stats?.total_chunks}
            loading={stats === null}
          />
          <StatCard
            icon={FileCode2}
            label="Files processed"
            value={stats?.total_files_processed}
            loading={stats === null}
          />
          <StatCard
            icon={Sigma}
            label="Languages seen"
            value={stats?.languages?.length}
            loading={stats === null}
          />
        </div>
      </section>

      {/* Recent repos */}
      <section className="max-w-6xl mx-auto px-6 mt-14">
        <div className="flex items-end justify-between mb-5">
          <div>
            <h2 className="font-display text-xl font-semibold">Indexed repositories</h2>
            <p className="text-sm text-muted mt-1">Everything currently queryable, most recent first.</p>
          </div>
          <button onClick={() => navigate('/repos')} className="btn-ghost text-sm">
            View all <ArrowRight size={14} />
          </button>
        </div>

        {repos === null && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}

        {Array.isArray(repos) && repos.length === 0 && (
          <div className="panel p-10 text-center">
            <p className="font-display text-ink">No repositories yet</p>
            <p className="text-sm text-muted mt-1 mb-5">
              Index your first repo to start asking it questions.
            </p>
            <button onClick={() => navigate('/ingest')} className="btn-primary mx-auto">
              Ingest a repo <ArrowRight size={15} />
            </button>
          </div>
        )}

        {Array.isArray(repos) && repos.length > 0 && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...repos]
              .sort((a, b) => new Date(b.ingested_at) - new Date(a.ingested_at))
              .slice(0, 6)
              .map((repo) => (
                <button
                  key={repo.repo_id}
                  onClick={() => navigate(`/repos?focus=${repo.repo_id}`)}
                  className="panel card-hover text-left p-5"
                >
                  <p className="font-mono text-sm text-ink truncate">{shortRepoName(repo.repo_url)}</p>
                  <p className="text-xs text-faint mt-1">{timeAgo(repo.ingested_at)}</p>
                  <div className="flex items-center gap-3 mt-4 text-xs text-muted font-mono">
                    <span>{formatNumber(repo.chunks_stored)} chunks</span>
                    <span>·</span>
                    <span>{formatNumber(repo.files_processed)} files</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {repo.languages_found?.map((l) => (
                      <LanguageBadge key={l} language={l} />
                    ))}
                  </div>
                </button>
              ))}
          </div>
        )}
      </section>

      {health && (
        <section className="max-w-6xl mx-auto px-6 mt-14 mb-10">
          <div className="panel px-5 py-4 flex flex-wrap items-center gap-x-8 gap-y-2 text-xs font-mono text-faint">
            <span className="eyebrow !text-faint">system</span>
            <span>api: <span className="text-muted">{health.api}</span></span>
            <span>chromadb: <span className="text-muted">{health.chromadb}</span></span>
            <span>gemini: <span className="text-muted">{health.gemini}</span></span>
          </div>
        </section>
      )}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, loading }) {
  return (
    <div className="panel px-5 py-4">
      <Icon size={16} className="text-vector-400 mb-3" strokeWidth={2} />
      {loading ? (
        <div className="h-7 w-16 bg-border/60 rounded animate-pulse" />
      ) : (
        <p className="font-display text-2xl font-semibold">{formatNumber(value)}</p>
      )}
      <p className="text-xs text-faint mt-1">{label}</p>
    </div>
  )
}
