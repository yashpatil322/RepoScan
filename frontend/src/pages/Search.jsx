import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search as SearchIcon, Radar, FileText } from 'lucide-react'
import { getRepos, getLanguages, search, searchSimilar } from '../lib/api'
import { ErrorBanner, EmptyState, LanguageBadge, ScoreBar, CodeSnippet, Spinner } from '../components/Primitives.jsx'

export default function Search() {
  const [repos, setRepos] = useState([])
  const [languages, setLanguages] = useState([])
  const [q, setQ] = useState('')
  const [repoId, setRepoId] = useState('')
  const [lang, setLang] = useState('')
  const [chunkType, setChunkType] = useState('')
  const [topK, setTopK] = useState(10)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [similarOf, setSimilarOf] = useState(null)

  useEffect(() => {
    getRepos().then((r) => setRepos(r.repos || [])).catch(() => {})
    getLanguages().then((r) => setLanguages(r.languages || [])).catch(() => {})
  }, [])

  async function runSearch(e) {
    e?.preventDefault()
    if (!q.trim()) return
    setLoading(true)
    setError('')
    setSimilarOf(null)
    try {
      const data = await search({
        query: q.trim(),
        repo_id: repoId || null,
        top_k: topK,
        filter_language: lang || null,
        filter_chunk_type: chunkType || null,
      })
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function findSimilar(chunk) {
    setLoading(true)
    setError('')
    setSimilarOf(chunk)
    try {
      const data = await searchSimilar(chunk.chunk_id, { repoId: chunk.repo_id || repoId, topK: 5 })
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-14">
      <p className="eyebrow mb-3">Module 4 · Search</p>
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight">
        Raw similarity search
      </h1>
      <p className="text-muted mt-3 max-w-xl">
        Straight cosine similarity over the vector store, no LLM in the loop — the fastest
        way to see what the index actually retrieves for a phrase.
      </p>

      <form onSubmit={runSearch} className="mt-8 panel-raised p-2 flex items-center gap-2">
        <div className="pl-3 text-faint">
          <SearchIcon size={16} />
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="database connection pooling"
          className="flex-1 bg-transparent px-2 py-3 font-mono text-sm placeholder:text-faint focus:outline-none"
        />
        <button type="submit" disabled={loading} className="btn-primary shrink-0">
          {loading ? <Spinner size={15} className="!text-void" /> : 'Search'}
        </button>
      </form>

      <div className="mt-4 flex flex-wrap gap-3">
        <select value={repoId} onChange={(e) => setRepoId(e.target.value)} className="input-field !w-auto max-w-[200px]">
          <option value="">All repos</option>
          {repos.map((r) => (
            <option key={r.repo_id} value={r.repo_id}>{r.repo_id}</option>
          ))}
        </select>
        <select value={lang} onChange={(e) => setLang(e.target.value)} className="input-field !w-auto max-w-[160px]">
          <option value="">Any language</option>
          {languages.map((l) => (
            <option key={l.language} value={l.language}>{l.language}</option>
          ))}
        </select>
        <select value={chunkType} onChange={(e) => setChunkType(e.target.value)} className="input-field !w-auto max-w-[160px]">
          <option value="">Any chunk type</option>
          <option value="function">function</option>
          <option value="class">class</option>
          <option value="module">module</option>
          <option value="method">method</option>
        </select>
        <label className="flex items-center gap-2 text-xs font-mono text-muted">
          top_k
          <input
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="input-field !w-16 !py-1.5 text-center"
          />
        </label>
      </div>

      <ErrorBanner message={error} />

      {similarOf && (
        <div className="mt-6 chip !py-2 !px-3 border-vector-500/40">
          <Radar size={13} className="text-vector-400" />
          related to <span className="text-ink">{similarOf.name || similarOf.file_path}</span>
        </div>
      )}

      <div className="mt-6">
        {results === null && !loading && (
          <EmptyState icon={SearchIcon} title="Search the index" hint="Results show ranked code chunks with similarity scores." />
        )}

        {loading && (
          <div className="flex justify-center py-16">
            <Spinner />
          </div>
        )}

        <AnimatePresence>
          {!loading && results?.results?.length === 0 && (
            <EmptyState title="No matches" hint="Try a broader phrase or clear the language / chunk-type filters." />
          )}
          {!loading && results?.results?.map((r, i) => (
            <motion.div
              key={r.chunk_id + i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.03 }}
              className="panel p-5 mb-3"
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <FileText size={12} className="text-faint" />
                    <span className="font-mono text-xs text-ink truncate">
                      {r.file_path}:{r.start_line}-{r.end_line}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <LanguageBadge language={r.language} />
                    <span className="chip">{r.chunk_type}</span>
                    {r.name && <span className="chip">{r.name}</span>}
                    {r.repo_id && <span className="chip">{r.repo_id}</span>}
                  </div>
                </div>
                <div className="w-full sm:w-40">
                  <ScoreBar score={r.similarity_score} />
                </div>
              </div>

              <div className="mt-4 rounded-lg bg-void/50 border border-border p-4">
                <CodeSnippet text={r.text} maxLines={8} />
              </div>

              <button
                onClick={() => findSimilar(r)}
                className="btn-ghost text-xs !py-1.5 mt-3"
              >
                <Radar size={13} /> Find similar
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
