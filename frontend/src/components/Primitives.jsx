import { Loader2, Inbox } from 'lucide-react'
import { languageColor, cx } from '../lib/utils'

export function Spinner({ size = 16, className = '' }) {
  return <Loader2 size={size} className={cx('animate-spin text-vector-400', className)} />
}

export function LanguageBadge({ language }) {
  if (!language) return null
  return (
    <span className="chip">
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: languageColor(language) }} />
      {language}
    </span>
  )
}

export function ScoreBar({ score = 0 }) {
  const pct = Math.round(score * 100)
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="h-1.5 flex-1 rounded-full bg-void/80 overflow-hidden border border-border">
        <div
          className="h-full rounded-full bg-gradient-to-r from-vector-600 to-vector-400"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[11px] text-faint w-9 text-right">{pct}%</span>
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, hint, action }) {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-16 px-6">
      <div className="w-12 h-12 rounded-2xl bg-surface border border-border flex items-center justify-center">
        <Icon size={20} className="text-faint" strokeWidth={1.6} />
      </div>
      <div>
        <p className="font-display text-ink font-medium">{title}</p>
        {hint && <p className="text-sm text-muted mt-1 max-w-xs">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

export function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div className="rounded-xl border border-signal-red/30 bg-signal-red/10 px-4 py-3 text-sm text-signal-red font-mono">
      {message}
    </div>
  )
}

export function CodeSnippet({ text, maxLines = 12 }) {
  const lines = (text || '').split('\n')
  const clipped = lines.slice(0, maxLines)
  const hasMore = lines.length > maxLines
  return (
    <pre className="mono-scroll text-[12.5px] leading-relaxed text-ink/90 overflow-x-auto">
      <code>
        {clipped.join('\n')}
        {hasMore && '\n…'}
      </code>
    </pre>
  )
}

const STAGES = ['queued', 'cloning', 'parsing', 'embedding', 'completed']

export function IngestStages({ status }) {
  const failed = status === 'failed'
  const currentIdx = STAGES.indexOf(status)
  return (
    <div className="flex items-center gap-1.5 w-full">
      {STAGES.map((stage, idx) => {
        const done = !failed && currentIdx > idx
        const active = !failed && currentIdx === idx
        return (
          <div key={stage} className="flex-1 flex flex-col gap-1.5">
            <div
              className={cx(
                'h-1.5 rounded-full transition-colors duration-500',
                done || active ? 'bg-vector-500' : 'bg-border',
                failed && idx === STAGES.length - 1 && 'bg-signal-red'
              )}
            />
            <span
              className={cx(
                'text-[10px] font-mono capitalize',
                active ? 'text-vector-400' : done ? 'text-muted' : 'text-faint'
              )}
            >
              {stage}
            </span>
          </div>
        )
      })}
    </div>
  )
}
