import { NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Boxes, MessageSquareText, Search, Database, GitBranch } from 'lucide-react'
import { getHealth } from '../lib/api'
import { cx } from '../lib/utils'

const links = [
  { to: '/', label: 'Overview', icon: Boxes, end: true },
  { to: '/ingest', label: 'Ingest', icon: GitBranch },
  { to: '/ask', label: 'Ask', icon: MessageSquareText },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/repos', label: 'Repos', icon: Database },
]

export default function NavBar() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    const check = () => {
      getHealth()
        .then((data) => {
          if (!cancelled) {
            setHealth(data)
            setError(false)
          }
        })
        .catch(() => {
          if (!cancelled) setError(true)
        })
    }
    check()
    const id = setInterval(check, 20000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  const healthy = health?.status === 'ok' && health?.chromadb === 'connected' && health?.gemini === 'configured'

  return (
    <header className="sticky top-0 z-50">
      <div className="absolute inset-0 bg-void/70 backdrop-blur-xl border-b border-border" />
      <nav className="relative max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <NavLink to="/" className="flex items-center gap-2.5 group">
          <svg width="26" height="26" viewBox="0 0 32 32" className="shrink-0">
            <circle cx="16" cy="16" r="14.5" fill="#0a0d14" stroke="#7c6fff" strokeWidth="1.4" />
            <line x1="16" y1="16" x2="24" y2="10" stroke="#7c6fff" strokeWidth="0.8" opacity="0.6" />
            <line x1="16" y1="16" x2="8" y2="22" stroke="#7c6fff" strokeWidth="0.8" opacity="0.6" />
            <line x1="16" y1="16" x2="22" y2="23" stroke="#7c6fff" strokeWidth="0.8" opacity="0.6" />
            <circle cx="16" cy="16" r="3" fill="#7c6fff" />
            <circle cx="24" cy="10" r="1.8" fill="#ffb86b" />
            <circle cx="8" cy="22" r="1.8" fill="#4ade80" />
            <circle cx="22" cy="23" r="1.8" fill="#c9c0ff" />
          </svg>
          <span className="font-display font-semibold text-[15px] tracking-tight text-ink group-hover:text-vector-400 transition-colors">
            RepoScan
          </span>
        </NavLink>

        <div className="hidden md:flex items-center gap-1 bg-surface/60 border border-border rounded-full p-1">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx(
                  'flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200',
                  isActive ? 'bg-vector-500 text-void' : 'text-muted hover:text-ink'
                )
              }
            >
              <Icon size={14} strokeWidth={2.2} />
              {label}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span
            className={cx(
              'status-dot',
              error ? 'bg-signal-red' : healthy ? 'bg-signal-green animate-pulse-ring' : 'bg-amber-400'
            )}
          />
          <span className="text-faint hidden sm:inline">
            {error ? 'backend unreachable' : healthy ? 'system nominal' : health ? 'degraded' : 'checking…'}
          </span>
        </div>
      </nav>

      <div className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-surface/90 backdrop-blur-xl border-t border-border flex justify-around py-2">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cx(
                'flex flex-col items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg',
                isActive ? 'text-vector-400' : 'text-faint'
              )
            }
          >
            <Icon size={18} strokeWidth={2.2} />
            {label}
          </NavLink>
        ))}
      </div>
    </header>
  )
}
