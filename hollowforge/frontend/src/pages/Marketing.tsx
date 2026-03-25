import CaptionGenerator from '../components/tools/CaptionGenerator'

export default function Marketing() {
  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-zinc-100">Marketing Automation Tool</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Generate atmospheric captions and hashtag packs from image uploads.
        </p>
      </header>

      <CaptionGenerator />
    </div>
  )
}
