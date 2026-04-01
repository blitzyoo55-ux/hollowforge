import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import PublishingPilotCard from './PublishingPilotCard'

function renderCard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <PublishingPilotCard
        item={{
          generation_id: 'gen-1',
          image_path: 'images/gen-1.png',
          thumbnail_path: 'thumbs/gen-1.png',
          checkpoint: 'waiIllustriousSDXL_v160.safetensors',
          prompt: 'prompt gen-1',
          created_at: '2026-03-27T00:00:00+00:00',
          approved_caption_id: 'caption-1',
          caption_count: 1,
          publish_job_count: 0,
          latest_publish_status: null,
          latest_animation_status: null,
          latest_animation_score: null,
        }}
        controls={{
          platform: 'pixiv',
          tone: 'teaser',
          channel: 'social_short',
        }}
        readiness={{
          caption_generation_ready: false,
          draft_publish_ready: true,
          degraded_mode: 'draft_only',
          provider: 'openrouter',
          model: 'x-ai/grok-2-vision-1212',
          missing_requirements: ['OPENROUTER_API_KEY'],
          notes: ['Caption generation unavailable'],
        }}
        captionQuery={{
          data: [
            {
              id: 'caption-1',
              generation_id: 'gen-1',
              channel: 'social_short',
              platform: 'pixiv',
              provider: 'openrouter',
              model: 'x-ai/grok-2-vision-1212',
              prompt_version: 'v1',
              tone: 'teaser',
              story: 'caption one',
              hashtags: '#one',
              approved: true,
              created_at: '2026-03-27T00:00:00+00:00',
              updated_at: '2026-03-27T00:00:00+00:00',
            },
          ],
          isLoading: false,
          isError: false,
        }}
        publishJobsQuery={{
          data: [],
          isLoading: false,
          isError: false,
        }}
      />
    </QueryClientProvider>,
  )
}

test('disables caption generation and keeps draft creation available in draft-only mode', () => {
  renderCard()

  expect(screen.getByRole('button', { name: /Generate caption/i })).toBeDisabled()
  expect(
    screen.getByText(/OPENROUTER_API_KEY is not configured/i),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Create draft/i })).toBeEnabled()
})
