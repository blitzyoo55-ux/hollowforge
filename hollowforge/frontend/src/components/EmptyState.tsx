import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}

function DefaultEmptyIcon() {
  return (
    <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3.75" y="4.5" width="16.5" height="15" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="9" cy="10" r="1.5" fill="currentColor" />
      <path
        d="M4.5 16l4.2-4.2a1.5 1.5 0 012.1 0L13.5 14.5l1.2-1.2a1.5 1.5 0 012.1 0l2.7 2.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-violet-500/40 bg-gray-900/70 p-10 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-violet-500/40 bg-violet-500/10 text-violet-300">
        {icon ?? <DefaultEmptyIcon />}
      </div>
      <h3 className="text-lg font-semibold text-gray-100">{title}</h3>
      {description && <p className="mt-1 text-sm text-gray-400">{description}</p>}
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
