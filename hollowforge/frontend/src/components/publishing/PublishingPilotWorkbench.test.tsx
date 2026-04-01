import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  getCaptionVariants,
  getPublishJobs,
  getReadyPublishItems,
  getPublishingReadiness,
} from '../../api/client'
import PublishingPilotWorkbench from './PublishingPilotWorkbench'

vi.mock('../../api/client', () => ({
  getCaptionVariants: vi.fn(),
  getPublishJobs: vi.fn(),
  getReadyPublishItems: vi.fn(),
  getPublishingReadiness: vi.fn(),
}))

vi.mock('./PublishingPilotCard', () => ({
  default: ({
    item,
    controls,
    captionQuery,
    publishJobsQuery,
    readinessState,
  }: {
    item: { generation_id: string }
    controls: { platform: string; tone: string; channel: string }
    captionQuery: { data: unknown[]; isLoading: boolean; isError: boolean }
    publishJobsQuery: { data: unknown[]; isLoading: boolean; isError: boolean }
    readinessState?: string
  }) => (
    <div data-testid={`publishing-card-${item.generation_id}`}>
      <div>{item.generation_id}</div>
      <div>{`${controls.platform}|${controls.tone}|${controls.channel}`}</div>
      <div>{`captions:${captionQuery.data.length}`}</div>
      <div>{`jobs:${publishJobsQuery.data.length}`}</div>
      <div>{`caption-loading:${captionQuery.isLoading}`}</div>
      <div>{`jobs-loading:${publishJobsQuery.isLoading}`}</div>
      <div>{`readiness:${readinessState ?? 'unknown'}`}</div>
    </div>
  ),
}))

function renderWorkbench(generationIds: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PublishingPilotWorkbench generationIds={generationIds} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()

  vi.mocked(getPublishingReadiness).mockResolvedValue({
    caption_generation_ready: true,
    draft_publish_ready: true,
    degraded_mode: 'full',
    provider: 'openrouter',
    model: 'x-ai/grok-2-vision-1212',
    missing_requirements: [],
    notes: [],
  })

  vi.mocked(getReadyPublishItems).mockResolvedValue([
    {
      generation_id: 'gen-1',
      image_path: 'images/gen-1.png',
      thumbnail_path: 'thumbs/gen-1.jpg',
      checkpoint: 'waiIllustriousSDXL_v160.safetensors',
      prompt: 'prompt gen-1',
      created_at: '2026-03-27T00:00:00+00:00',
      approved_caption_id: 'caption-1',
      caption_count: 2,
      publish_job_count: 1,
      latest_publish_status: 'draft',
      latest_animation_status: 'completed',
      latest_animation_score: 0.81,
    },
    {
      generation_id: 'gen-2',
      image_path: 'images/gen-2.png',
      thumbnail_path: 'thumbs/gen-2.jpg',
      checkpoint: 'waiIllustriousSDXL_v160.safetensors',
      prompt: 'prompt gen-2',
      created_at: '2026-03-27T00:05:00+00:00',
      approved_caption_id: null,
      caption_count: 1,
      publish_job_count: 1,
      latest_publish_status: 'queued',
      latest_animation_status: null,
      latest_animation_score: null,
    },
  ])

  vi.mocked(getCaptionVariants).mockImplementation(async (generationId: string) => {
    if (generationId === 'gen-1') {
      return [
        {
          id: 'caption-1',
          generation_id: 'gen-1',
          channel: 'social_short',
          platform: 'pixiv',
          provider: 'openrouter',
          model: 'grok-4.1-fast',
          prompt_version: 'v1',
          tone: 'teaser',
          story: 'caption one',
          hashtags: '#one',
          approved: true,
          created_at: '2026-03-27T00:00:00+00:00',
          updated_at: '2026-03-27T00:00:00+00:00',
        },
      ]
    }

    return [
      {
        id: 'caption-2',
        generation_id: 'gen-2',
        channel: 'social_short',
        platform: 'twitter',
        provider: 'openrouter',
        model: 'grok-4.1-fast',
        prompt_version: 'v1',
        tone: 'campaign',
        story: 'caption two',
        hashtags: '#two',
        approved: false,
        created_at: '2026-03-27T00:05:00+00:00',
        updated_at: '2026-03-27T00:05:00+00:00',
      },
    ]
  })

  vi.mocked(getPublishJobs).mockImplementation(async (generationId: string) => {
    if (generationId === 'gen-1') {
      return [
        {
          id: 'job-1',
          generation_id: 'gen-1',
          caption_variant_id: 'caption-1',
          platform: 'pixiv',
          status: 'draft',
          scheduled_at: null,
          published_at: null,
          external_post_id: null,
          external_post_url: null,
          notes: null,
          created_at: '2026-03-27T00:00:00+00:00',
          updated_at: '2026-03-27T00:00:00+00:00',
        },
      ]
    }

    return [
      {
        id: 'job-2',
        generation_id: 'gen-2',
        caption_variant_id: null,
        platform: 'twitter',
        status: 'draft',
        scheduled_at: null,
        published_at: null,
        external_post_id: null,
        external_post_url: null,
        notes: null,
        created_at: '2026-03-27T00:05:00+00:00',
        updated_at: '2026-03-27T00:05:00+00:00',
      },
    ]
  })
})

test('renders invalid and missing id notices and propagates shared control changes to cards', async () => {
  renderWorkbench(['gen-1', 'bad id', 'gen-2', 'gen-2', 'missing-3'])

  expect(await screen.findByText(/Publishing pilot intake/i)).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByTestId('publishing-card-gen-1')).toBeInTheDocument()
    expect(screen.getByTestId('publishing-card-gen-2')).toBeInTheDocument()
  })

  expect(getReadyPublishItems).toHaveBeenCalledWith(['gen-1', 'gen-2', 'missing-3'])
  expect(screen.getByText(/Ignored 1 invalid `generation_id` value\(s\)/i)).toBeInTheDocument()
  expect(screen.getByText(/1 selected item\(s\) were not returned/i)).toBeInTheDocument()
  expect(screen.getByText(/^Requested$/i).parentElement).toHaveTextContent('5')
  expect(screen.getByText(/^Valid$/i).parentElement).toHaveTextContent('3')
  expect(screen.getByText(/^Approved Captions$/i).parentElement).toHaveTextContent('1')
  expect(screen.getByText(/^pixiv Drafts$/i).parentElement).toHaveTextContent('1')

  expect(screen.getByTestId('publishing-card-gen-1')).toHaveTextContent('pixiv|teaser|social_short')

  fireEvent.change(screen.getByLabelText(/Platform/i), { target: { value: 'fansly' } })
  fireEvent.change(screen.getByLabelText(/Tone/i), { target: { value: 'campaign' } })
  fireEvent.change(screen.getByLabelText(/Channel/i), { target: { value: 'launch_copy' } })

  expect(screen.getByTestId('publishing-card-gen-1')).toHaveTextContent('fansly|campaign|launch_copy')
  expect(screen.getByTestId('publishing-card-gen-2')).toHaveTextContent('fansly|campaign|launch_copy')
})

test('shows draft-only readiness mode and missing OPENROUTER_API_KEY notice', async () => {
  vi.mocked(getPublishingReadiness).mockResolvedValue({
    caption_generation_ready: false,
    draft_publish_ready: true,
    degraded_mode: 'draft_only',
    provider: 'openrouter',
    model: 'x-ai/grok-2-vision-1212',
    missing_requirements: ['OPENROUTER_API_KEY'],
    notes: ['Caption generation is unavailable'],
  })

  renderWorkbench(['gen-1'])

  expect(await screen.findByText(/draft-only mode/i)).toBeInTheDocument()
  expect(screen.getByText(/Missing requirements:/i)).toHaveTextContent('OPENROUTER_API_KEY')
  expect(screen.getByTestId('publishing-card-gen-1')).toBeInTheDocument()
  expect(getPublishingReadiness).toHaveBeenCalledTimes(1)
})

test('shows the no-valid-ids state and skips the ready-items query', async () => {
  renderWorkbench(['bad id', 'also bad'])

  expect(await screen.findByText(/No valid selected IDs/i)).toBeInTheDocument()
  expect(screen.getByText(/none passed validation/i)).toBeInTheDocument()
  expect(getReadyPublishItems).not.toHaveBeenCalled()
})
