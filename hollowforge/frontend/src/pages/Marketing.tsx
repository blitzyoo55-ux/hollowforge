import { Link, useSearchParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import PublishingPilotWorkbench from '../components/publishing/PublishingPilotWorkbench'
import CaptionGenerator from '../components/tools/CaptionGenerator'

export default function Marketing() {
  const [searchParams] = useSearchParams()
  const selectedGenerationIds = searchParams.getAll('generation_id')
  const hasPublishingSelection = selectedGenerationIds.length > 0

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-zinc-100">
          {hasPublishingSelection ? 'Publishing Pilot Workbench' : 'Marketing Automation Tool'}
        </h2>
        <p className="mt-1 text-sm text-zinc-400">
          {hasPublishingSelection
            ? 'Review the selected ready batch, approve a caption per item, and create internal draft publish jobs.'
            : 'Generate atmospheric captions and hashtag packs from image uploads, or launch the publishing pilot from /ready.'}
        </p>
      </header>

      {hasPublishingSelection ? (
        <PublishingPilotWorkbench generationIds={selectedGenerationIds} />
      ) : (
        <div className="space-y-6">
          <div className="space-y-4">
            <EmptyState
              title="No ready batch selected"
              description="Select 1-10 ready items from the Ready to Go queue to open the publishing pilot workbench."
            />
            <div className="flex justify-center">
              <Link
                to="/ready"
                className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-200 transition-colors hover:border-emerald-300/60 hover:bg-emerald-500/15"
              >
                Back to /ready
              </Link>
            </div>
          </div>

          <CaptionGenerator />
        </div>
      )}
    </div>
  )
}
