import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LoraInput {
  filename: string;
  strength: number;
  category: string | null;
}

export interface GenerationCreate {
  prompt: string;
  negative_prompt?: string | null;
  checkpoint: string;
  loras?: LoraInput[];
  seed?: number | null;
  steps?: number;
  cfg?: number;
  width?: number;
  height?: number;
  sampler?: string;
  scheduler?: string;
  clip_skip?: number | null;
  tags?: string[] | null;
  preset_id?: string | null;
  notes?: string | null;
  source_id?: string | null;
}

export interface GenerationBatchCreate {
  generation: GenerationCreate;
  count: number;
  seed_increment?: number;
}

export interface GenerationResponse {
  id: string;
  prompt: string;
  negative_prompt: string | null;
  checkpoint: string;
  loras: LoraInput[];
  seed: number;
  steps: number;
  cfg: number;
  width: number;
  height: number;
  sampler: string;
  scheduler: string;
  clip_skip: number | null;
  status: string;
  image_path: string | null;
  watermarked_path: string | null;
  upscaled_image_path: string | null;
  adetailed_path: string | null;
  hiresfix_path: string | null;
  dreamactor_path: string | null;
  dreamactor_task_id: string | null;
  dreamactor_status: string | null;
  upscaled_preview_path: string | null;
  upscale_model: string | null;
  thumbnail_path: string | null;
  workflow_path: string | null;
  generation_time_sec: number | null;
  tags: string[] | null;
  preset_id: string | null;
  notes: string | null;
  source_id: string | null;
  comfyui_prompt_id: string | null;
  error_message: string | null;
  postprocess_kind?: string | null;
  postprocess_status?: string | null;
  postprocess_message?: string | null;
  is_favorite: boolean;
  quality_score?: number | null;
  quality_ai_score?: number | null;
  finger_anomaly?: number | null;
  publish_approved?: number;
  created_at: string;
  completed_at: string | null;
}

export interface GenerationBatchResponse {
  count: number;
  base_seed: number;
  seed_increment: number;
  generations: GenerationResponse[];
}

export interface GenerationStatus {
  id: string;
  status: string;
  generation_time_sec: number | null;
  estimated_time_sec: number | null;
  postprocess_kind?: string | null;
  postprocess_status?: string | null;
}

export interface DreamActorStatus {
  status: string;
  progress: number;
  video_url: string | null;
  dreamactor_path: string | null;
}

export type AnimationTargetTool =
  | 'dreamactor'
  | 'seedance'
  | 'wan_i2v'
  | 'hunyuan_avatar'
  | 'custom'

export type AnimationExecutorMode = 'local' | 'remote_worker' | 'managed_api'

export interface AnimationJobResponse {
  id: string
  candidate_id: string | null
  generation_id: string
  publish_job_id: string | null
  target_tool: AnimationTargetTool
  executor_mode: AnimationExecutorMode
  executor_key: string
  status: 'draft' | 'queued' | 'submitted' | 'processing' | 'completed' | 'failed' | 'cancelled'
  request_json: Record<string, unknown> | null
  external_job_id: string | null
  external_job_url: string | null
  output_path: string | null
  error_message: string | null
  submitted_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface AnimationJobDispatchResponse {
  animation_job: AnimationJobResponse
  dispatch_mode: AnimationExecutorMode | string
  remote_request_accepted: boolean
  remote_worker_job_id: string | null
  remote_worker_job_url: string | null
}

export interface AnimationExecutorConfigResponse {
  mode: AnimationExecutorMode | string
  executor_key: string
  remote_base_url: string | null
  managed_provider: string | null
  supports_direct_submit: boolean
  preferred_flow: string
  supported_target_tools: string[]
}

export interface AnimationPresetResponse {
  id: string
  name: string
  description: string | null
  target_tool: AnimationTargetTool
  backend_family: string
  model_profile: string
  request_json: Record<string, unknown>
}

export interface AnimationShotResponse {
  id: string
  source_kind: string
  episode_id: string | null
  scene_panel_id: string
  selected_render_asset_id: string
  generation_id: string | null
  is_current: boolean
  created_at: string
  updated_at: string
}

export interface AnimationShotVariantResponse {
  id: string
  animation_shot_id: string
  animation_job_id: string
  preset_id: string
  launch_reason: string
  status: AnimationJobResponse['status']
  output_path: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface AnimationCurrentShotResponse {
  shot: AnimationShotResponse | null
  variants: AnimationShotVariantResponse[]
}

export interface AnimationPresetLaunchRequest {
  candidate_id?: string | null
  generation_id?: string | null
  episode_id?: string | null
  scene_panel_id?: string | null
  selected_render_asset_id?: string | null
  publish_job_id?: string | null
  executor_mode?: AnimationExecutorMode | null
  executor_key?: string | null
  dispatch_immediately?: boolean
  request_overrides?: Record<string, unknown> | null
}

export interface AnimationPresetLaunchResponse {
  preset: AnimationPresetResponse
  animation_job: AnimationJobResponse
  dispatch: AnimationJobDispatchResponse | null
  dispatch_error: string | null
  animation_shot_id: string | null
  animation_shot_variant_id: string | null
}

export interface AnimationReconciliationResponse {
  checked: number
  updated: number
  failed_restart: number
  completed: number
  cancelled: number
  skipped_unreachable: number
}

export interface SeedanceJobStatus {
  job_id: string;
  status: string;
  progress: number;
  output_path: string | null;
  error_msg: string | null;
  created_at: string | null;
  completed_at: string | null;
  prompt: string | null;
  duration_sec: number | null;
}

export interface SeedanceJobCreateRequest {
  prompt: string;
  duration_sec: number;
  image_ids?: string[];
  image_files?: File[];
  video_files?: File[];
  audio_files?: File[];
}

export interface ActiveGeneration {
  id: string;
  status: string;
  created_at: string;
  checkpoint?: string;
  seed?: number;
  steps?: number;
  width?: number;
  height?: number;
}

export interface PresetCreate {
  name: string;
  description?: string | null;
  checkpoint: string;
  loras?: LoraInput[];
  prompt_template?: string | null;
  negative_prompt?: string | null;
  default_params?: Record<string, unknown>;
  tags?: string[] | null;
}

export interface PresetUpdate {
  name?: string | null;
  description?: string | null;
  checkpoint?: string | null;
  loras?: LoraInput[] | null;
  prompt_template?: string | null;
  negative_prompt?: string | null;
  default_params?: Record<string, unknown> | null;
  tags?: string[] | null;
}

export interface PresetResponse {
  id: string;
  name: string;
  description: string | null;
  checkpoint: string;
  loras: LoraInput[];
  prompt_template: string | null;
  negative_prompt: string | null;
  default_params: Record<string, unknown>;
  tags: string[] | null;
  created_at: string;
  updated_at: string | null;
}

export interface LoraProfile {
  id: string;
  display_name: string;
  filename: string;
  category: string;
  default_strength: number;
  tags: string | null;
  notes: string | null;
  compatible_checkpoints: string[] | null;
  created_at: string;
}

export type LoraProfileResponse = LoraProfile

export interface LoraProfileCreate {
  display_name: string;
  filename: string;
  category: 'style' | 'eyes' | 'material' | 'fetish';
  default_strength?: number;
  tags?: string | null;
  notes?: string | null;
  compatible_checkpoints?: string[] | null;
}

export interface LoraProfileUpdate {
  display_name?: string | null;
  category?: 'style' | 'eyes' | 'material' | 'fetish' | null;
  default_strength?: number | null;
  tags?: string | null;
  notes?: string | null;
  compatible_checkpoints?: string[] | null;
}

export interface MoodMapping {
  id: string;
  mood_keyword: string;
  lora_ids: string[];
  prompt_additions: string;
  created_at: string;
}

export interface MoodMappingCreate {
  mood_keyword: string;
  lora_ids?: string[];
  prompt_additions?: string;
}

export interface MoodMappingUpdate {
  mood_keyword?: string | null;
  lora_ids?: string[] | null;
  prompt_additions?: string | null;
}

export interface LoraGuideCheckpoint {
  name: string;
  architecture: string;
  completed_generations: number;
}

export interface LoraGuideStrength {
  low: number;
  base: number;
  high: number;
  reverse_start: number;
  reverse_limit: number;
}

export interface LoraGuideUsage {
  total_runs: number;
  avg_strength: number | null;
  avg_abs_strength: number | null;
  negative_runs: number;
  min_strength: number | null;
  max_strength: number | null;
}

export interface LoraGuideCheckpointFit {
  checkpoint: string;
  score: number;
  runs: number;
  avg_strength: number | null;
  reasons: string[];
}

export interface LoraGuideEntry {
  id?: string;
  filename: string;
  display_name: string;
  category: string;
  architecture: string;
  compatible_checkpoints: string[];
  strength: LoraGuideStrength;
  usage: LoraGuideUsage;
  raise_effect: string;
  lower_effect: string;
  checkpoint_fits: LoraGuideCheckpointFit[];
}

export interface LoraGuideStrengthExample {
  bucket_id: string;
  label: string;
  min_total: number;
  max_total: number | null;
  guidance: string;
  generation_id: string | null;
  checkpoint: string | null;
  total_abs_strength: number | null;
  thumbnail_path: string | null;
  prompt: string | null;
  loras: LoraInput[];
}

export interface LoraGuideResponse {
  generated_at: string;
  active_checkpoint?: string | null;
  max_total_strength: number;
  checkpoints: LoraGuideCheckpoint[];
  loras: LoraGuideEntry[];
  strength_examples: LoraGuideStrengthExample[];
  cache?: {
    hit: boolean;
    ttl_sec: number;
  };
}

export interface LoraGuideQuery {
  checkpoint?: string;
  refresh?: boolean;
}

export interface MoodSelectRequest {
  moods: string[];
  checkpoint?: string | null;
}

export interface MoodSelectResponse {
  loras: LoraInput[];
  prompt_additions: string;
}

export interface CaptionResponse {
  story: string;
  hashtags: string;
}

export type CaptionPublishingPlatform = 'twitter' | 'fansly' | 'pixiv' | 'generic';
export type PublishJobPlatform = 'twitter' | 'fansly' | 'pixiv' | 'custom';
export type PublishingTone = 'teaser' | 'clinical' | 'campaign';
export type PublishingChannel = 'social_short' | 'post_body' | 'launch_copy';
export type PublishJobStatus = 'draft' | 'queued' | 'scheduled' | 'published' | 'failed';

export interface CaptionGenerateRequest {
  platform: CaptionPublishingPlatform;
  tone: PublishingTone;
  channel: PublishingChannel;
  approved?: boolean;
}

export interface CaptionVariantResponse {
  id: string;
  generation_id: string;
  channel: PublishingChannel;
  platform: CaptionPublishingPlatform;
  provider: string;
  model: string;
  prompt_version: string;
  tone: PublishingTone;
  story: string;
  hashtags: string;
  approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface PublishJobCreate {
  generation_id: string;
  caption_variant_id?: string | null;
  platform?: PublishJobPlatform;
  status?: PublishJobStatus;
  scheduled_at?: string | null;
  external_post_id?: string | null;
  external_post_url?: string | null;
  notes?: string | null;
}

export interface PublishJobResponse {
  id: string;
  generation_id: string;
  caption_variant_id: string | null;
  platform: PublishJobPlatform;
  status: PublishJobStatus;
  scheduled_at: string | null;
  published_at: string | null;
  external_post_id: string | null;
  external_post_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReadyPublishItemResponse {
  generation_id: string;
  image_path: string | null;
  thumbnail_path: string | null;
  checkpoint: string;
  prompt: string;
  created_at: string;
  approved_caption_id: string | null;
  caption_count: number;
  publish_job_count: number;
  latest_publish_status: PublishJobStatus | null;
  latest_animation_status: string | null;
  latest_animation_score: number | null;
}

export interface GalleryQuery {
  page?: number;
  per_page?: number;
  checkpoint?: string | null;
  tags?: string[] | null;
  search?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  favorites?: boolean;
  sort_by?: string;
  sort_order?: string;
  publish_approved?: number | null;
  min_quality?: number | null;
  max_quality?: number | null;
}

export interface TimelineDailyItem {
  date: string;
  count: number;
  completed: number;
  failed: number;
  cancelled: number;
  checkpoints: Record<string, number>;
  avg_generation_time_sec: number | null;
}

export interface TimelineCheckpointItem {
  checkpoint: string;
  count: number;
  pct: number;
}

export interface TimelineHourItem {
  hour: number;
  count: number;
}

export interface TimelineStreak {
  current_days: number;
  longest_days: number;
}

export interface GalleryTimelineResponse {
  days: number;
  total: number;
  daily: TimelineDailyItem[];
  by_checkpoint: TimelineCheckpointItem[];
  by_hour: TimelineHourItem[];
  streak: TimelineStreak;
}

export interface BenchmarkCreate {
  name: string;
  prompt: string;
  negative_prompt?: string | null;
  loras: LoraInput[];
  steps?: number;
  cfg?: number;
  width?: number;
  height?: number;
  sampler?: string;
  scheduler?: string;
  seed?: number | null;
  checkpoints: string[];
}

export interface BenchmarkResponse {
  id: string;
  name: string;
  prompt: string;
  negative_prompt: string | null;
  loras: LoraInput[];
  steps: number;
  cfg: number;
  width: number;
  height: number;
  sampler: string;
  scheduler: string;
  seed: number | null;
  checkpoints: string[];
  generation_ids: string[];
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  completed_at: string | null;
  generations?: GenerationResponse[];
}

export interface CollectionCreate {
  name: string;
  description?: string | null;
}

export interface CollectionUpdate {
  name?: string | null;
  description?: string | null;
  cover_image_id?: string | null;
}

export interface CollectionResponse {
  id: string;
  name: string;
  description: string | null;
  cover_image_id: string | null;
  cover_thumbnail_path: string | null;
  image_count: number;
  contains_generation: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface ScheduledJobCreate {
  name: string;
  preset_id: string;
  count?: number;
  cron_hour?: number;
  cron_minute?: number;
  enabled?: boolean;
}

export interface ScheduledJobUpdate {
  name?: string | null;
  preset_id?: string | null;
  count?: number | null;
  cron_hour?: number | null;
  cron_minute?: number | null;
  enabled?: boolean | null;
}

export interface ScheduledJobResponse {
  id: string;
  name: string;
  preset_id: string;
  count: number;
  cron_hour: number;
  cron_minute: number;
  enabled: boolean;
  last_run_at: string | null;
  last_run_status: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SchedulerRunNowResponse {
  success: boolean;
  queued: number;
  status: string;
}

export interface CollectionDetailResponse {
  collection: CollectionResponse;
  items: GenerationResponse[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface SystemHealth {
  status: string;
  comfyui_connected: boolean;
  db_ok: boolean;
  total_generations: number;
  completed_generations?: number;
  failed_generations?: number;
  cancelled_generations?: number;
}

export interface ComfyUIStatus {
  connected: boolean;
  url: string;
  system_stats?: Record<string, unknown>;
  message?: string;
}

export type WatermarkPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'center'

export interface WatermarkSettings {
  id: number
  enabled: boolean
  text: string
  position: WatermarkPosition
  opacity: number
  font_size: number
  padding: number
  color: string
  updated_at: string
}

export interface WatermarkSettingsUpdate {
  enabled: boolean
  text: string
  position: WatermarkPosition
  opacity: number
  font_size: number
  padding: number
  color: string
}

export interface ModelsResponse {
  checkpoints: string[];
  checkpoints_all?: string[];
  non_image_checkpoints?: string[];
  checkpoint_arches?: Record<string, string>;
  samplers: string[];
  schedulers: string[];
  lora_files: string[];
}

export interface SyncResponse {
  checkpoints: string[];
  checkpoints_all?: string[];
  non_image_checkpoints?: string[];
  samplers: string[];
  schedulers: string[];
  lora_files: string[];
  new_loras: number;
  compatibility_updated: number;
  incompatible_loras: number;
  checkpoint_arches: Record<string, string>;
  synced: boolean;
}

export interface UpscaleModelsResponse {
  upscale_models: string[];
  comfyui_models?: string[];
  local_models?: string[];
  recommended_model?: string | null;
  recommended_profile?: string;
  recommended_checkpoint?: string | null;
  recommended_mode?: UpscaleMode;
  recommended_mode_reason?: string | null;
  safe_upscale_enabled?: boolean;
  quality_upscale_enabled?: boolean;
  quality_required_nodes?: string[];
  quality_missing_nodes?: string[];
  quality_upscale_reason?: string | null;
}

export interface QualityProfileParams {
  steps: number;
  cfg: number;
  width: number;
  height: number;
  sampler: string;
  scheduler: string;
  clip_skip: number | null;
}

export interface CheckpointQualityProfile {
  checkpoint: string;
  architecture: string;
  applicable: boolean;
  profile_name: string;
  description: string;
  params: QualityProfileParams | null;
}

export interface QualityProfilesResponse {
  generated_at: string;
  profiles: Record<string, CheckpointQualityProfile>;
}

export type PromptFactoryCheckpointPreferenceMode =
  | 'default'
  | 'prefer'
  | 'force'
  | 'exclude'

export interface PromptFactoryCheckpointPreferenceEntry {
  checkpoint: string
  available: boolean
  architecture: string | null
  favorite_count: number
  mode: PromptFactoryCheckpointPreferenceMode
  priority_boost: number
  notes: string | null
  updated_at: string | null
}

export interface PromptFactoryCheckpointPreferencesResponse {
  generated_at: string
  entries: PromptFactoryCheckpointPreferenceEntry[]
}

export interface PromptFactoryCheckpointPreferencesReplaceRequest {
  entries: Array<{
    checkpoint: string
    mode: PromptFactoryCheckpointPreferenceMode
    priority_boost: number
    notes?: string | null
  }>
}

export interface PromptTemplate {
  id: string;
  name: string;
  text: string;
  description: string;
}

export interface PromptTemplateVariable {
  token: string;
  description: string;
  example: string;
}

export interface CheckpointPromptTemplates {
  checkpoint: string;
  architecture: string;
  default_positive_template_id: string;
  default_negative_template_id: string;
  positive_templates: PromptTemplate[];
  negative_templates: PromptTemplate[];
  guidance: string[];
}

export interface PromptTemplatesResponse {
  generated_at: string;
  variables: PromptTemplateVariable[];
  templates: Record<string, CheckpointPromptTemplates>;
}

export type StoryPlannerLane = 'unrestricted' | 'all_ages' | 'adult_nsfw'

export interface StoryPlannerCharacterCatalogEntry {
  id: string
  name: string
  canonical_anchor: string
  anti_drift: string
  wardrobe_notes: string
  personality_notes: string
  preferred_checkpoints: string[]
}

export interface StoryPlannerLocationCatalogEntry {
  id: string
  name: string
  setting_anchor: string
  visual_rules: string[]
  restricted_elements: string[]
}

export interface StoryPlannerPolicyPackCatalogEntry {
  id: string
  lane: StoryPlannerLane
  prompt_provider_profile_id: string
  negative_prompt_mode: 'blank' | 'recommended' | 'custom'
  forbidden_defaults: string[]
  planner_rules: string[]
  render_preferences: Record<string, unknown>
}

export interface StoryPlannerCatalog {
  characters: StoryPlannerCharacterCatalogEntry[]
  locations: StoryPlannerLocationCatalogEntry[]
  policy_packs: StoryPlannerPolicyPackCatalogEntry[]
}

export interface StoryPlannerCastInput {
  role: 'lead' | 'support'
  source_type: 'registry' | 'freeform'
  character_id?: string | null
  freeform_description?: string | null
}

export interface StoryPlannerPlanRequest {
  story_prompt: string
  lane: StoryPlannerLane
  cast: StoryPlannerCastInput[]
}

export interface StoryPlannerResolvedCastEntry {
  role: 'lead' | 'support'
  source_type: 'registry' | 'freeform'
  character_id: string | null
  character_name: string | null
  freeform_description: string | null
  canonical_anchor: string | null
  anti_drift: string | null
  wardrobe_notes: string | null
  personality_notes: string | null
  resolution_note: string
}

export interface StoryPlannerResolvedLocationEntry {
  id: string
  name: string
  setting_anchor: string
  visual_rules: string[]
  restricted_elements: string[]
  match_note: string
}

export interface StoryPlannerEpisodeBrief {
  premise: string
  continuity_guidance: string[]
}

export interface StoryPlannerShotCard {
  shot_no: number
  beat: string
  camera: string
  action: string
  emotion: string
  continuity_note: string
}

export interface StoryPlannerAnchorRenderSnapshot {
  policy_pack_id: string
  checkpoint: string
  workflow_lane: Exclude<PromptFactoryWorkflowLane, 'auto'>
  negative_prompt: string | null
  preserve_blank_negative_prompt: boolean
}

export interface StoryPlannerPlanResponse {
  story_prompt: string
  lane: StoryPlannerLane
  policy_pack_id: string
  approval_token: string
  anchor_render: StoryPlannerAnchorRenderSnapshot
  resolved_cast: StoryPlannerResolvedCastEntry[]
  location: StoryPlannerResolvedLocationEntry
  episode_brief: StoryPlannerEpisodeBrief
  shots: StoryPlannerShotCard[]
}

export interface StoryPlannerAnchorQueuedShotResponse {
  shot_no: number
  generation_ids: string[]
}

export interface StoryPlannerAnchorQueueRequest {
  approved_plan: StoryPlannerPlanResponse
  candidate_count?: number
}

export interface StoryPlannerAnchorQueueResponse {
  lane: StoryPlannerLane
  requested_shot_count: number
  queued_generation_count: number
  queued_shots: StoryPlannerAnchorQueuedShotResponse[]
  queued_generations: GenerationResponse[]
}

export type ComicEpisodeStatus = 'draft' | 'planned' | 'in_production' | 'released'
export type ComicTargetOutput = 'oneshot_manga' | 'serial_episode' | 'teaser_animation'
export type ComicPanelType = 'splash' | 'establish' | 'beat' | 'insert' | 'closeup' | 'transition'
export type ComicDialogueType = 'speech' | 'thought' | 'caption' | 'sfx'
export type ComicRenderAssetRole = 'candidate' | 'selected' | 'derived_preview' | 'final_master'
export type ComicRenderExecutionMode = 'local_preview' | 'remote_worker'
export type ComicRenderJobStatus =
  | 'draft'
  | 'queued'
  | 'submitted'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'
export type ComicPageExportState = 'draft' | 'preview_ready' | 'exported'
export type ComicPageLayoutTemplateId = 'jp_2x2_v1' | 'jp_3row_v1'
export type ComicManuscriptProfileId = 'jp_manga_rightbound_v1'

export interface ComicEpisodeResponse {
  id: string
  character_id: string
  character_version_id: string
  title: string
  synopsis: string
  source_story_plan_json: string | null
  status: ComicEpisodeStatus
  continuity_summary: string | null
  canon_delta: string | null
  target_output: ComicTargetOutput
  created_at: string
  updated_at: string
}

export interface ComicEpisodeSceneResponse {
  id: string
  episode_id: string
  scene_no: number
  premise: string
  location_label: string | null
  tension: string | null
  reveal: string | null
  continuity_notes: string | null
  involved_character_ids: string[]
  target_panel_count: number | null
  created_at: string
  updated_at: string
}

export interface ComicScenePanelResponse {
  id: string
  episode_scene_id: string
  panel_no: number
  panel_type: ComicPanelType
  framing: string | null
  camera_intent: string | null
  action_intent: string | null
  expression_intent: string | null
  dialogue_intent: string | null
  continuity_lock: string | null
  page_target_hint: number | null
  reading_order: number
  remote_job_count: number
  pending_remote_job_count: number
  created_at: string
  updated_at: string
}

export interface ComicPanelDialogueResponse {
  id: string
  scene_panel_id: string
  type: ComicDialogueType
  speaker_character_id: string | null
  text: string
  tone: string | null
  priority: number
  balloon_style_hint: string | null
  placement_hint: string | null
  created_at: string
  updated_at: string
}

export interface ComicPanelRenderAssetResponse {
  id: string
  scene_panel_id: string
  generation_id: string | null
  asset_role: ComicRenderAssetRole
  storage_path: string | null
  prompt_snapshot: Record<string, unknown> | null
  quality_score: number | null
  bubble_safe_zones: Array<Record<string, unknown>>
  crop_metadata: Record<string, unknown> | null
  render_notes: string | null
  is_selected: boolean
  created_at: string
  updated_at: string
}

export interface ComicPageAssemblyResponse {
  id: string
  episode_id: string
  page_no: number
  layout_template_id: string | null
  ordered_panel_ids: string[]
  export_state: ComicPageExportState
  preview_path: string | null
  master_path: string | null
  export_manifest: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ComicCharacterResponse {
  id: string
  slug: string
  name: string
  status: string
  tier: string | null
  created_at: string
  updated_at: string
}

export interface ComicCharacterVersionResponse {
  id: string
  character_id: string
  version_name: string
  purpose: string
  checkpoint: string
  workflow_lane: string
  created_at: string
  updated_at: string
}

export interface ComicSceneDetailResponse {
  scene: ComicEpisodeSceneResponse
  panels: ComicScenePanelResponse[]
}

export interface ComicEpisodeDetailResponse {
  episode: ComicEpisodeResponse
  scenes: ComicSceneDetailResponse[]
  pages: ComicPageAssemblyResponse[]
}

export interface ComicEpisodeSummaryResponse {
  episode: ComicEpisodeResponse
  scene_count: number
  page_count: number
}

export interface ComicStoryPlanImportRequest {
  approved_plan: StoryPlannerPlanResponse
  character_version_id: string
  title: string
  panel_multiplier?: number
  work_id?: string | null
  series_id?: string | null
  production_episode_id?: string | null
}

export interface ComicPanelRenderQueueRequest {
  candidate_count?: number
  execution_mode?: ComicRenderExecutionMode
}

export interface ComicRenderJobResponse {
  id: string
  scene_panel_id: string
  render_asset_id: string
  generation_id: string
  request_index: number
  source_id: string
  target_tool: string
  executor_mode: string
  executor_key: string
  status: ComicRenderJobStatus
  request_json: Record<string, unknown> | null
  external_job_id: string | null
  external_job_url: string | null
  output_path: string | null
  error_message: string | null
  submitted_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface ComicPanelRenderQueueResponse {
  panel: ComicScenePanelResponse
  execution_mode: ComicRenderExecutionMode
  requested_count: number
  queued_generation_count: number
  materialized_asset_count: number
  pending_render_job_count: number
  remote_job_count: number
  render_assets: ComicPanelRenderAssetResponse[]
}

export interface ComicDialogueGenerationResponse {
  panel: ComicScenePanelResponse
  dialogues: ComicPanelDialogueResponse[]
  generated_count: number
  overwrite_existing: boolean
  prompt_provider_profile_id: string
}

export interface ComicManuscriptProfileResponse {
  id: ComicManuscriptProfileId
  label: string
  binding_direction: 'right_to_left'
  finishing_tool: 'clip_studio_ex'
  print_intent: 'japanese_manga'
  trim_reference: string
  bleed_reference: string
  safe_area_reference: string
  naming_pattern: string
}

export type ComicHandoffLayerStatus = 'complete' | 'warning' | 'blocked'

export interface ComicHandoffIssueResponse {
  code?: string
  message?: string
  page_id?: string | null
  [key: string]: unknown
}

export interface ComicHandoffPageSummaryResponse {
  page_id: string
  page_no: number
  art_layer_status: ComicHandoffLayerStatus
  frame_layer_status: ComicHandoffLayerStatus
  balloon_layer_status: ComicHandoffLayerStatus
  text_draft_layer_status: ComicHandoffLayerStatus
  hard_block_count: number
  soft_warning_count: number
}

export interface ComicHandoffValidationResponse {
  episode_id: string
  hard_blocks: ComicHandoffIssueResponse[]
  soft_warnings: ComicHandoffIssueResponse[]
  page_summaries: ComicHandoffPageSummaryResponse[]
  generated_at: string
}

export interface ComicHandoffExportSummaryResponse {
  export_zip_path: string
  layered_manifest_path: string
  handoff_validation_path: string
  page_count: number
  hard_block_count: number
  soft_warning_count: number
  exported_at: string
}

export interface ComicPageAssemblyBatchResponse {
  episode_id: string
  layout_template_id: ComicPageLayoutTemplateId
  manuscript_profile: ComicManuscriptProfileResponse
  pages: ComicPageAssemblyResponse[]
  export_manifest_path: string
  dialogue_json_path: string
  panel_asset_manifest_path: string
  page_assembly_manifest_path: string
  manuscript_profile_manifest_path: string
  handoff_readme_path: string
  production_checklist_path: string
  teaser_handoff_manifest_path: string
  layered_manifest_path: string
  handoff_validation_path: string
  handoff_validation: ComicHandoffValidationResponse
  page_summaries: ComicHandoffPageSummaryResponse[]
  latest_export_summary: ComicHandoffExportSummaryResponse | null
}

export interface ComicPageExportResponse extends ComicPageAssemblyBatchResponse {
  export_zip_path: string
}

export type PromptFactoryProvider = 'default' | 'openrouter' | 'xai'
export type PromptFactoryWorkflowLane = 'auto' | 'classic_clip' | 'sdxl_illustrious'
export type PromptFactoryTone = 'clinical' | 'campaign' | 'editorial' | 'teaser'
export type PromptFactoryHeatLevel = 'suggestive' | 'steamy' | 'maximal'
export type PromptFactoryCreativeAutonomy = 'strict' | 'hybrid' | 'director'

export interface PromptFactoryGenerateRequest {
  concept_brief: string
  creative_brief?: string | null
  count: number
  chunk_size?: number
  workflow_lane?: PromptFactoryWorkflowLane
  provider?: PromptFactoryProvider
  model?: string | null
  tone?: PromptFactoryTone
  heat_level?: PromptFactoryHeatLevel
  creative_autonomy?: PromptFactoryCreativeAutonomy
  direction_pass_enabled?: boolean
  target_lora_count?: number
  checkpoint_pool_size?: number
  include_negative_prompt?: boolean
  dedupe?: boolean
  forbidden_elements?: string[]
  direction_pack_override?: PromptFactoryDirectionBlueprint[]
  expansion_axes?: string[]
}

export interface PromptFactoryDirectionBlueprint {
  codename_stub: string
  series: string
  scene_hook: string
  camera_plan: string
  pose_plan: string
  environment: string
  device_focus: string
  lighting_plan: string
  material_focus: string
  intensity_hook: string
}

export interface PromptFactoryRow {
  set_no: number
  codename: string
  series: string
  checkpoint: string
  workflow_lane: Exclude<PromptFactoryWorkflowLane, 'auto'> | null
  loras: LoraInput[]
  sampler: string
  steps: number
  cfg: number
  clip_skip: number | null
  width: number
  height: number
  positive_prompt: string
  negative_prompt: string | null
}

export interface PromptFactoryBenchmark {
  favorites_total: number
  workflow_lane: string
  prompt_dialect: string
  top_checkpoints: string[]
  top_loras: string[]
  avg_lora_strength: number
  cfg_values: number[]
  steps_values: number[]
  sampler: string
  scheduler: string
  clip_skip: number | null
  width: number
  height: number
  theme_keywords: string[]
  material_cues: string[]
  control_cues: string[]
  camera_cues: string[]
  environment_cues: string[]
  exposure_cues: string[]
  negative_prompt: string
}

export interface PromptFactoryGenerateResponse {
  provider: string
  model: string
  requested_count: number
  generated_count: number
  chunk_count: number
  benchmark: PromptFactoryBenchmark
  direction_pack: PromptFactoryDirectionBlueprint[]
  rows: PromptFactoryRow[]
}

export interface PromptFactoryQueueResponse {
  prompt_batch: PromptFactoryGenerateResponse
  queued_generations: GenerationResponse[]
}

export interface PromptFactoryCapabilities {
  default_provider: string
  default_model: string
  openrouter_configured: boolean
  xai_configured: boolean
  ready: boolean
  recommended_lane: string
  supported_lanes: string[]
  batch_import_headers: string[]
  notes: string[]
}

export interface ReproduceRequest {
  mode: 'exact' | 'variation';
  seed?: number | null;
  notes?: string | null;
}

export interface ToggleFavoriteResponse {
  id: string;
  is_favorite: boolean;
}

export interface ToggleReadyResponse {
  id: string;
  publish_approved: number;
  curated_at: string | null;
}

export interface FavoriteUpscaleStatusResponse {
  favorites_total: number
  upscaled_done: number
  queued: number
  running: number
  pending: number
  daily_candidates: number
  completion_pct: number
  daily_enabled: boolean
  daily_hour: number
  daily_minute: number
  daily_batch_limit: number | null
  backlog_window_start_hour: number
  backlog_window_end_hour: number
  backlog_window_open: boolean
  mode: UpscaleMode
}

export type UpscaleMode = 'safe' | 'quality'

export type MetadataExportFormat = 'json' | 'csv'

export interface QueueItem {
  id: string
  status: 'queued' | 'running'
  position: number
  checkpoint: string
  loras: LoraInput[]
  prompt: string
  steps: number
  cfg: number
  width: number
  height: number
  sampler: string
  tags: string[] | null
  notes: string | null
  created_at: string
  estimated_start_sec: number
  estimated_done_sec: number
}

export interface QueueSummary {
  total_queued: number
  total_running: number
  total_active: number
  avg_generation_sec: number
  estimated_remaining_sec: number
  oldest_queued_at: string | null
  queue_items: QueueItem[]
}

export type SequenceContentMode = 'all_ages' | 'adult_nsfw'

export interface SequenceBlueprintCreate {
  work_id?: string | null
  series_id?: string | null
  production_episode_id?: string | null
  content_mode: SequenceContentMode
  policy_profile_id: string
  character_id: string
  location_id: string
  beat_grammar_id: string
  target_duration_sec: number
  shot_count: number
  tone?: string | null
  executor_policy: string
}

export interface SequenceBlueprintResponse extends SequenceBlueprintCreate {
  id: string
  created_at: string
  updated_at: string
}

export interface SequenceShotPlanResponse {
  shot_no: number
  beat_type: string
  camera_intent: string
  emotion_intent: string
  action_intent: string
  target_duration_sec: number
  continuity_rules: string | null
}

export interface SequenceBlueprintDetailResponse {
  blueprint: SequenceBlueprintResponse
  planned_shots: SequenceShotPlanResponse[]
}

export interface SequenceRunCreateRequest {
  sequence_blueprint_id: string
  prompt_provider_profile_id?: string | null
  candidate_count?: number
  target_tool?: string | null
}

export interface SequenceRunResponse {
  id: string
  sequence_blueprint_id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  prompt_provider_profile_id: string
  execution_mode: string
  status: string
  selected_rough_cut_id: string | null
  total_score: number | null
  error_summary: string | null
  created_at: string
  updated_at: string
}

export interface SequenceShotResponse {
  id: string
  sequence_run_id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  shot_no: number
  beat_type: string
  camera_intent: string
  emotion_intent: string
  action_intent: string
  target_duration_sec: number
  continuity_rules: string | null
  created_at: string
  updated_at: string
}

export interface SequenceAnchorCandidateResponse {
  id: string
  sequence_shot_id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  generation_id: string
  identity_score: number | null
  location_lock_score: number | null
  beat_fit_score: number | null
  quality_score: number | null
  rank_score: number | null
  is_selected_primary: boolean
  is_selected_backup: boolean
  created_at: string
  updated_at: string
}

export interface SequenceShotClipResponse {
  id: string
  sequence_shot_id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  selected_animation_job_id: string | null
  clip_path: string | null
  clip_duration_sec: number | null
  clip_score: number | null
  retry_count: number
  is_degraded: boolean
  created_at: string
  updated_at: string
}

export interface SequenceRunShotDetailResponse {
  shot: SequenceShotResponse
  anchor_candidates: SequenceAnchorCandidateResponse[]
  clips: SequenceShotClipResponse[]
}

export interface RoughCutResponse {
  id: string
  sequence_run_id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  output_path: string | null
  timeline_json: unknown
  total_duration_sec: number | null
  continuity_score: number | null
  story_score: number | null
  overall_score: number | null
  created_at: string
  updated_at: string
}

export interface SequenceRoughCutCandidateResponse {
  rough_cut: RoughCutResponse
  is_selected: boolean
}

export interface SequenceRunSummaryResponse {
  run: SequenceRunResponse
  shot_count: number
  rough_cut_candidate_count: number
}

export interface SequenceRunDetailResponse {
  run: SequenceRunResponse
  blueprint: SequenceBlueprintResponse
  shots: SequenceRunShotDetailResponse[]
  rough_cut_candidates: SequenceRoughCutCandidateResponse[]
}

export type ProductionFormatFamily = 'comic' | 'animation' | 'mixed'
export type ProductionDeliveryMode = 'oneshot' | 'serial' | 'anthology'
export type ProductionTargetOutput = 'comic' | 'animation'

export interface ProductionWorkResponse {
  id: string
  title: string
  format_family: ProductionFormatFamily
  default_content_mode: SequenceContentMode
  status: string
  canon_notes: string | null
  created_at: string
  updated_at: string
}

export interface ProductionWorkCreate {
  id?: string | null
  title: string
  format_family: ProductionFormatFamily
  default_content_mode: SequenceContentMode
  status?: string | null
  canon_notes?: string | null
}

export interface ProductionSeriesResponse {
  id: string
  work_id: string
  title: string
  delivery_mode: ProductionDeliveryMode
  audience_mode: SequenceContentMode
  visual_identity_notes: string | null
  created_at: string
  updated_at: string
}

export interface ProductionSeriesCreate {
  id?: string | null
  work_id: string
  title: string
  delivery_mode: ProductionDeliveryMode
  audience_mode: SequenceContentMode
  visual_identity_notes?: string | null
}

export interface ProductionComicTrackLinkResponse {
  id: string
  status: string
  target_output: ComicTargetOutput
  character_id: string
}

export interface ProductionAnimationTrackLinkResponse {
  id: string
  content_mode: SequenceContentMode
  policy_profile_id: string
  shot_count: number
  executor_policy: string
}

export interface ProductionEpisodeDetailResponse {
  id: string
  work_id: string
  series_id: string | null
  title: string
  synopsis: string
  content_mode: SequenceContentMode
  target_outputs: ProductionTargetOutput[]
  continuity_summary: string | null
  status: string
  comic_track: ProductionComicTrackLinkResponse | null
  animation_track: ProductionAnimationTrackLinkResponse | null
  comic_track_count: number
  animation_track_count: number
  created_at: string
  updated_at: string
}

export interface ProductionEpisodeCreate {
  work_id: string
  series_id?: string | null
  title: string
  synopsis: string
  content_mode: SequenceContentMode
  target_outputs: ProductionTargetOutput[]
  continuity_summary?: string | null
  status?: string | null
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

export async function listProductionEpisodes(query: {
  work_id?: string
} = {}): Promise<ProductionEpisodeDetailResponse[]> {
  const res = await api.get<ProductionEpisodeDetailResponse[]>('/production/episodes', {
    params: query,
  })
  return res.data
}

export async function getProductionEpisode(
  productionEpisodeId: string,
): Promise<ProductionEpisodeDetailResponse> {
  const res = await api.get<ProductionEpisodeDetailResponse>(`/production/episodes/${productionEpisodeId}`)
  return res.data
}

export async function listProductionWorks(): Promise<ProductionWorkResponse[]> {
  const res = await api.get<ProductionWorkResponse[]>('/production/works')
  return res.data
}

export async function listProductionSeries(query: {
  work_id?: string
} = {}): Promise<ProductionSeriesResponse[]> {
  const res = await api.get<ProductionSeriesResponse[]>('/production/series', {
    params: query,
  })
  return res.data
}

export async function createProductionWork(
  data: ProductionWorkCreate,
): Promise<ProductionWorkResponse> {
  const res = await api.post<ProductionWorkResponse>('/production/works', data)
  return res.data
}

export async function createProductionSeries(
  data: ProductionSeriesCreate,
): Promise<ProductionSeriesResponse> {
  const res = await api.post<ProductionSeriesResponse>('/production/series', data)
  return res.data
}

export async function createProductionEpisode(
  data: ProductionEpisodeCreate,
): Promise<ProductionEpisodeDetailResponse> {
  const res = await api.post<ProductionEpisodeDetailResponse>('/production/episodes', data)
  return res.data
}

export async function listComicEpisodes(query: {
  production_episode_id?: string
} = {}): Promise<ComicEpisodeSummaryResponse[]> {
  const res = await api.get<ComicEpisodeSummaryResponse[]>('/comic/episodes', {
    params: query,
  })
  return res.data
}

export async function getComicEpisode(
  episodeId: string,
): Promise<ComicEpisodeDetailResponse> {
  const res = await api.get<ComicEpisodeDetailResponse>(`/comic/episodes/${episodeId}`)
  return res.data
}

export async function createSequenceBlueprint(
  data: SequenceBlueprintCreate,
): Promise<SequenceBlueprintDetailResponse> {
  const res = await api.post<SequenceBlueprintDetailResponse>('/sequences/blueprints', data)
  return res.data
}

export async function listSequenceBlueprints(query: {
  content_mode?: SequenceContentMode
  policy_profile_id?: string
  production_episode_id?: string
} = {}): Promise<SequenceBlueprintDetailResponse[]> {
  const res = await api.get<SequenceBlueprintDetailResponse[]>('/sequences/blueprints', {
    params: query,
  })
  return res.data
}

export async function createSequenceRun(
  data: SequenceRunCreateRequest,
): Promise<SequenceRunDetailResponse> {
  const res = await api.post<SequenceRunDetailResponse>('/sequences/runs', data)
  return res.data
}

export async function listSequenceRuns(query: {
  sequence_blueprint_id?: string
  status?: string
} = {}): Promise<SequenceRunSummaryResponse[]> {
  const res = await api.get<SequenceRunSummaryResponse[]>('/sequences/runs', {
    params: query,
  })
  return res.data
}

export async function getSequenceRun(runId: string): Promise<SequenceRunDetailResponse> {
  const res = await api.get<SequenceRunDetailResponse>(`/sequences/runs/${runId}`)
  return res.data
}

export async function startSequenceRun(runId: string): Promise<SequenceRunDetailResponse> {
  const res = await api.post<SequenceRunDetailResponse>(`/sequences/runs/${runId}/start`)
  return res.data
}

export async function createGeneration(data: GenerationCreate): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>('/generations', data);
  return res.data;
}

export async function createGenerationBatch(
  data: GenerationBatchCreate,
): Promise<GenerationBatchResponse> {
  const res = await api.post<GenerationBatchResponse>('/generations/batch', data);
  return res.data;
}

export async function getGeneration(id: string): Promise<GenerationResponse> {
  const res = await api.get<GenerationResponse>(`/generations/${id}`);
  return res.data;
}

export async function getGenerationStatus(id: string): Promise<GenerationStatus> {
  const res = await api.get<GenerationStatus>(`/generations/${id}/status`);
  return res.data;
}

export async function getActiveGenerations(): Promise<ActiveGeneration[]> {
  const res = await api.get<ActiveGeneration[]>('/generations/active');
  return res.data;
}

export async function cancelGeneration(id: string): Promise<void> {
  await api.post(`/generations/${id}/cancel`);
}

export async function upscaleGeneration(
  id: string,
  upscale_model: string,
  mode: UpscaleMode = 'safe',
): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/generations/${id}/upscale`, {
    upscale_model,
    mode,
  });
  return res.data;
}

export async function adetailGeneration(
  id: string,
  opts: { denoise?: number; steps?: number } = {},
): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/generations/${id}/adetail`, {
    denoise: opts.denoise ?? 0.4,
    steps: opts.steps ?? 20,
  });
  return res.data;
}

export async function hiresfixGeneration(
  id: string,
  opts: { upscale_factor?: number; denoise?: number; steps?: number; cfg?: number } = {},
): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/generations/${id}/hiresfix`, {
    upscale_factor: opts.upscale_factor ?? 1.5,
    denoise: opts.denoise ?? 0.5,
    steps: opts.steps ?? 20,
    cfg: opts.cfg ?? 7.0,
  });
  return res.data;
}

export async function applyWatermark(id: string): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/generations/${id}/watermark`);
  return res.data;
}

export async function submitDreamActor(
  id: string,
  templateVideo: File,
): Promise<{ task_id: string; status: string }> {
  const formData = new FormData()
  formData.append('template_video', templateVideo)
  const res = await api.post<{ task_id: string; status: string }>(
    `/generations/${id}/dreamactor`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    },
  )
  return res.data
}

export async function getDreamActorStatus(id: string): Promise<DreamActorStatus> {
  const res = await api.get<DreamActorStatus>(`/generations/${id}/dreamactor/status`)
  return res.data
}

export async function getAnimationExecutorConfig(): Promise<AnimationExecutorConfigResponse> {
  const res = await api.get<AnimationExecutorConfigResponse>('/animation/executor-config')
  return res.data
}

export async function getAnimationPresets(): Promise<AnimationPresetResponse[]> {
  const res = await api.get<AnimationPresetResponse[]>('/animation/presets')
  return res.data
}

export async function listAnimationJobs(query: {
  generation_id?: string
  candidate_id?: string
  status_filter?: string
  limit?: number
} = {}): Promise<AnimationJobResponse[]> {
  const res = await api.get<AnimationJobResponse[]>('/animation/jobs', {
    params: query,
  })
  return res.data
}

export async function getCurrentAnimationShot(query: {
  scene_panel_id: string
  selected_render_asset_id: string
  limit?: number
}): Promise<AnimationCurrentShotResponse | null> {
  const res = await api.get<AnimationCurrentShotResponse | null>('/animation/shots/current', {
    params: query,
  })
  return res.data
}

export async function launchAnimationPreset(
  presetId: string,
  data: AnimationPresetLaunchRequest,
): Promise<AnimationPresetLaunchResponse> {
  const res = await api.post<AnimationPresetLaunchResponse>(
    `/animation/presets/${presetId}/launch`,
    data,
  )
  return res.data
}

export async function reconcileStaleAnimationJobs(): Promise<AnimationReconciliationResponse> {
  const res = await api.post<AnimationReconciliationResponse>('/animation/reconcile-stale')
  return res.data
}

export async function submitSeedanceJob(
  payload: SeedanceJobCreateRequest,
): Promise<{ job_id: string; status: string }> {
  const formData = new FormData()
  formData.append('prompt', payload.prompt)
  formData.append('duration_sec', String(payload.duration_sec))

  if (payload.image_ids && payload.image_ids.length > 0) {
    formData.append('image_ids', payload.image_ids.join(','))
  }
  for (const image of payload.image_files ?? []) {
    formData.append('image_files', image)
  }
  for (const video of payload.video_files ?? []) {
    formData.append('video_files', video)
  }
  for (const audio of payload.audio_files ?? []) {
    formData.append('audio_files', audio)
  }

  const res = await api.post<{ job_id: string; status: string }>(
    '/seedance/jobs',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    },
  )
  return res.data
}

export async function getSeedanceJob(jobId: string): Promise<SeedanceJobStatus> {
  const res = await api.get<SeedanceJobStatus>(`/seedance/jobs/${jobId}`)
  return res.data
}

export async function listSeedanceJobs(): Promise<SeedanceJobStatus[]> {
  const res = await api.get<SeedanceJobStatus[]>('/seedance/jobs')
  return res.data
}

export async function getReadyPublishItems(
  generationIds?: string[],
): Promise<ReadyPublishItemResponse[]> {
  const params = new URLSearchParams()
  for (const generationId of generationIds ?? []) {
    params.append('generation_id', generationId)
  }

  const res = await api.get<ReadyPublishItemResponse[]>('/publishing/ready-items', {
    params,
  })
  return res.data
}

export async function getCaptionVariants(
  generationId: string,
): Promise<CaptionVariantResponse[]> {
  const res = await api.get<CaptionVariantResponse[]>(
    `/publishing/generations/${generationId}/captions`,
  )
  return res.data
}

export async function generateCaptionVariant(
  generationId: string,
  payload: CaptionGenerateRequest,
): Promise<CaptionVariantResponse> {
  const res = await api.post<CaptionVariantResponse>(
    `/publishing/generations/${generationId}/captions/generate`,
    payload,
  )
  return res.data
}

export async function approveCaptionVariant(captionId: string): Promise<CaptionVariantResponse> {
  const res = await api.post<CaptionVariantResponse>(`/publishing/captions/${captionId}/approve`)
  return res.data
}

export async function getPublishJobs(generationId: string): Promise<PublishJobResponse[]> {
  const res = await api.get<PublishJobResponse[]>(
    `/publishing/generations/${generationId}/publish-jobs`,
  )
  return res.data
}

export async function createPublishJob(payload: PublishJobCreate): Promise<PublishJobResponse> {
  const res = await api.post<PublishJobResponse>('/publishing/posts', payload)
  return res.data
}

export async function generateCaptionById(generationId: string): Promise<CaptionResponse> {
  const res = await api.post<CaptionResponse>('/tools/generate-caption-by-id', {
    generation_id: generationId,
  })
  return res.data
}

export async function getStoryPlannerCatalog(): Promise<StoryPlannerCatalog> {
  const res = await api.get<StoryPlannerCatalog>('/tools/story-planner/catalog')
  return res.data
}

export async function planStoryEpisode(
  data: StoryPlannerPlanRequest,
): Promise<StoryPlannerPlanResponse> {
  const res = await api.post<StoryPlannerPlanResponse>('/tools/story-planner/plan', data)
  return res.data
}

export async function generateStoryPlannerAnchors(
  data: StoryPlannerAnchorQueueRequest,
): Promise<StoryPlannerAnchorQueueResponse> {
  const res = await api.post<StoryPlannerAnchorQueueResponse>(
    '/tools/story-planner/generate-anchors',
    data,
  )
  return res.data
}

export async function getComicCharacters(): Promise<ComicCharacterResponse[]> {
  const res = await api.get<ComicCharacterResponse[]>('/comic/characters')
  return res.data
}

export async function getComicCharacterVersions(
  characterId?: string | null,
): Promise<ComicCharacterVersionResponse[]> {
  const res = await api.get<ComicCharacterVersionResponse[]>('/comic/character-versions', {
    params: characterId ? { character_id: characterId } : undefined,
  })
  return res.data
}

export async function importComicStoryPlan(
  data: ComicStoryPlanImportRequest,
): Promise<ComicEpisodeDetailResponse> {
  const res = await api.post<ComicEpisodeDetailResponse>('/comic/episodes/import-story-plan', data)
  return res.data
}

export async function queueComicPanelRenders(
  panelId: string,
  data: ComicPanelRenderQueueRequest,
): Promise<ComicPanelRenderQueueResponse> {
  const res = await api.post<ComicPanelRenderQueueResponse>(
    `/comic/panels/${panelId}/queue-renders`,
    null,
    {
      params: {
        candidate_count: data.candidate_count ?? 3,
        execution_mode: data.execution_mode ?? 'local_preview',
      },
    },
  )
  return res.data
}

export async function getComicPanelRenderJobs(
  panelId: string,
): Promise<ComicRenderJobResponse[]> {
  const res = await api.get<ComicRenderJobResponse[]>(`/comic/panels/${panelId}/render-jobs`)
  return res.data
}

export async function selectComicPanelRenderAsset(
  panelId: string,
  assetId: string,
): Promise<ComicPanelRenderAssetResponse> {
  const res = await api.post<ComicPanelRenderAssetResponse>(
    `/comic/panels/${panelId}/assets/${assetId}/select`,
  )
  return res.data
}

export async function generateComicPanelDialogues(
  panelId: string,
): Promise<ComicDialogueGenerationResponse> {
  const res = await api.post<ComicDialogueGenerationResponse>(
    `/comic/panels/${panelId}/dialogues/generate`,
  )
  return res.data
}

export async function assembleComicEpisodePages(
  episodeId: string,
  layoutTemplateId: ComicPageLayoutTemplateId = 'jp_2x2_v1',
  manuscriptProfileId: ComicManuscriptProfileId = 'jp_manga_rightbound_v1',
): Promise<ComicPageAssemblyBatchResponse> {
  const res = await api.post<ComicPageAssemblyBatchResponse>(
    `/comic/episodes/${episodeId}/pages/assemble`,
    null,
    {
      params: {
        layout_template_id: layoutTemplateId,
        manuscript_profile_id: manuscriptProfileId,
      },
    },
  )
  return res.data
}

export async function exportComicEpisodePages(
  episodeId: string,
  layoutTemplateId: ComicPageLayoutTemplateId = 'jp_2x2_v1',
  manuscriptProfileId: ComicManuscriptProfileId = 'jp_manga_rightbound_v1',
): Promise<ComicPageExportResponse> {
  const res = await api.post<ComicPageExportResponse>(
    `/comic/episodes/${episodeId}/pages/export`,
    null,
    {
      params: {
        layout_template_id: layoutTemplateId,
        manuscript_profile_id: manuscriptProfileId,
      },
    },
  )
  return res.data
}

export async function getPromptFactoryCapabilities(): Promise<PromptFactoryCapabilities> {
  const res = await api.get<PromptFactoryCapabilities>('/tools/prompt-factory/capabilities')
  return res.data
}

export async function generatePromptBatch(
  data: PromptFactoryGenerateRequest,
): Promise<PromptFactoryGenerateResponse> {
  const res = await api.post<PromptFactoryGenerateResponse>('/tools/prompt-factory/generate', data)
  return res.data
}

export async function generatePromptBatchAndQueue(
  data: PromptFactoryGenerateRequest,
): Promise<PromptFactoryQueueResponse> {
  const res = await api.post<PromptFactoryQueueResponse>('/tools/prompt-factory/generate-and-queue', data)
  return res.data
}

export async function queuePromptBatch(
  data: PromptFactoryGenerateResponse,
): Promise<PromptFactoryQueueResponse> {
  const res = await api.post<PromptFactoryQueueResponse>('/tools/prompt-factory/queue', data)
  return res.data
}

export async function deleteSeedanceJob(jobId: string): Promise<void> {
  await api.delete(`/seedance/jobs/${jobId}`)
}

export async function getGallery(query: GalleryQuery): Promise<PaginatedResponse<GenerationResponse>> {
  const params = {
    page: query.page,
    per_page: query.per_page,
    checkpoint: query.checkpoint,
    tags: query.tags,
    search: query.search,
    date_from: query.date_from,
    date_to: query.date_to,
    favorites: query.favorites,
    sort_by: query.sort_by,
    sort_order: query.sort_order,
    publish_approved: query.publish_approved,
    min_quality: query.min_quality,
    max_quality: query.max_quality,
  };
  const res = await api.get<PaginatedResponse<GenerationResponse>>('/gallery', { params });
  return res.data;
}

export async function getGalleryTimeline(days = 30): Promise<GalleryTimelineResponse> {
  const res = await api.get<GalleryTimelineResponse>('/gallery/timeline', {
    params: { days },
  });
  return res.data;
}

export async function createBenchmark(
  data: BenchmarkCreate,
): Promise<BenchmarkResponse> {
  const res = await api.post<BenchmarkResponse>('/benchmark/run', data);
  return res.data;
}

export async function listBenchmarks(): Promise<BenchmarkResponse[]> {
  const res = await api.get<BenchmarkResponse[]>('/benchmark/jobs');
  return res.data;
}

export async function getBenchmark(jobId: string): Promise<BenchmarkResponse> {
  const res = await api.get<BenchmarkResponse>(`/benchmark/jobs/${jobId}`);
  return res.data;
}

export async function deleteBenchmark(jobId: string): Promise<void> {
  await api.delete(`/benchmark/jobs/${jobId}`);
}

export async function toggleFavorite(id: string): Promise<ToggleFavoriteResponse> {
  const res = await api.post<ToggleFavoriteResponse>(`/generations/${id}/favorite`);
  return res.data;
}

export async function toggleReadyToGo(id: string): Promise<ToggleReadyResponse> {
  const res = await api.post<ToggleReadyResponse>(`/generations/${id}/ready`);
  return res.data;
}

export async function getFavoriteUpscaleStatus(): Promise<FavoriteUpscaleStatusResponse> {
  const res = await api.get<FavoriteUpscaleStatusResponse>('/generations/favorites/upscale-status')
  return res.data
}

export async function deleteGalleryItem(id: string): Promise<void> {
  await api.delete(`/gallery/${id}`);
}

export async function getCollections(generationId?: string): Promise<CollectionResponse[]> {
  const res = await api.get<CollectionResponse[]>('/collections', {
    params: generationId ? { generation_id: generationId } : undefined,
  });
  return res.data;
}

export async function getCollection(
  id: string,
  page = 1,
  perPage = 48,
): Promise<CollectionDetailResponse> {
  const res = await api.get<CollectionDetailResponse>(`/collections/${id}`, {
    params: { page, per_page: perPage },
  });
  return res.data;
}

export async function createCollection(data: CollectionCreate): Promise<CollectionResponse> {
  const res = await api.post<CollectionResponse>('/collections', data);
  return res.data;
}

export async function updateCollection(
  id: string,
  data: CollectionUpdate,
): Promise<CollectionResponse> {
  const res = await api.put<CollectionResponse>(`/collections/${id}`, data);
  return res.data;
}

export async function addToCollection(collectionId: string, generationId: string): Promise<void> {
  await api.post(`/collections/${collectionId}/items`, { generation_id: generationId });
}

export async function removeFromCollection(collectionId: string, generationId: string): Promise<void> {
  await api.delete(`/collections/${collectionId}/items/${generationId}`);
}

export async function deleteCollection(id: string): Promise<void> {
  await api.delete(`/collections/${id}`);
}

export async function getPresets(): Promise<PresetResponse[]> {
  const res = await api.get<PresetResponse[]>('/presets');
  return res.data;
}

export async function createPreset(data: PresetCreate): Promise<PresetResponse> {
  const res = await api.post<PresetResponse>('/presets', data);
  return res.data;
}

export async function updatePreset(id: string, data: PresetUpdate): Promise<PresetResponse> {
  const res = await api.put<PresetResponse>(`/presets/${id}`, data);
  return res.data;
}

export async function deletePreset(id: string): Promise<void> {
  await api.delete(`/presets/${id}`);
}

export async function getSchedulerJobs(): Promise<ScheduledJobResponse[]> {
  const res = await api.get<ScheduledJobResponse[]>('/scheduler/jobs');
  return res.data;
}

export async function createSchedulerJob(
  data: ScheduledJobCreate,
): Promise<ScheduledJobResponse> {
  const res = await api.post<ScheduledJobResponse>('/scheduler/jobs', data);
  return res.data;
}

export async function updateSchedulerJob(
  id: string,
  data: ScheduledJobUpdate,
): Promise<ScheduledJobResponse> {
  const res = await api.put<ScheduledJobResponse>(`/scheduler/jobs/${id}`, data);
  return res.data;
}

export async function deleteSchedulerJob(id: string): Promise<void> {
  await api.delete(`/scheduler/jobs/${id}`);
}

export async function runSchedulerJobNow(
  id: string,
): Promise<SchedulerRunNowResponse> {
  const res = await api.post<SchedulerRunNowResponse>(`/scheduler/jobs/${id}/run`);
  return res.data;
}

export async function getLoras(checkpoint?: string | null): Promise<LoraProfileResponse[]> {
  const res = await api.get<LoraProfileResponse[]>('/loras', {
    params: checkpoint ? { checkpoint } : undefined,
  });
  return res.data;
}

export async function createLora(data: LoraProfileCreate): Promise<LoraProfile> {
  const res = await api.post<LoraProfile>('/loras', data);
  return res.data;
}

export async function updateLora(id: string, data: LoraProfileUpdate): Promise<LoraProfile> {
  const res = await api.put<LoraProfile>(`/loras/${id}`, data);
  return res.data;
}

export async function deleteLora(id: string): Promise<void> {
  await api.delete(`/loras/${id}`);
}

export async function listMoods(): Promise<MoodMapping[]> {
  const res = await api.get<MoodMapping[]>('/moods');
  return res.data;
}

export async function createMood(data: MoodMappingCreate): Promise<MoodMapping> {
  const res = await api.post<MoodMapping>('/moods', data);
  return res.data;
}

export async function updateMood(id: string, data: MoodMappingUpdate): Promise<MoodMapping> {
  const res = await api.put<MoodMapping>(`/moods/${id}`, data);
  return res.data;
}

export async function deleteMood(id: string): Promise<void> {
  await api.delete(`/moods/${id}`);
}

export async function selectLoras(data: MoodSelectRequest): Promise<MoodSelectResponse> {
  const res = await api.post<MoodSelectResponse>('/loras/select', data);
  return res.data;
}

export async function getLoraGuide(query: LoraGuideQuery = {}): Promise<LoraGuideResponse> {
  const params: Record<string, string | boolean> = {};
  if (query.checkpoint) params.checkpoint = query.checkpoint;
  if (query.refresh) params.refresh = true;
  const res = await api.get<LoraGuideResponse>('/loras/guide', {
    params: Object.keys(params).length > 0 ? params : undefined,
  });
  return res.data;
}

export async function reproduceGeneration(id: string, data: ReproduceRequest): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/reproduce/${id}`, data);
  return res.data;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const res = await api.get<SystemHealth>('/system/health');
  return res.data;
}

export async function getComfyUIStatus(): Promise<ComfyUIStatus> {
  const res = await api.get<ComfyUIStatus>('/system/comfyui');
  return res.data;
}

export async function updateComfyUIUrl(url: string): Promise<ComfyUIStatus> {
  const res = await api.post<ComfyUIStatus>('/system/comfyui', { url });
  return res.data;
}

export async function getWatermarkSettings(): Promise<WatermarkSettings> {
  const res = await api.get<WatermarkSettings>('/system/watermark');
  return res.data;
}

export async function updateWatermarkSettings(
  data: WatermarkSettingsUpdate,
): Promise<WatermarkSettings> {
  const res = await api.post<WatermarkSettings>('/system/watermark', data);
  return res.data;
}

export async function getModels(): Promise<ModelsResponse> {
  const res = await api.get<ModelsResponse>('/system/models');
  return res.data;
}

export async function syncModels(): Promise<SyncResponse> {
  const res = await api.post<SyncResponse>('/system/sync');
  return res.data;
}

export async function getUpscaleModels(checkpoint?: string | null): Promise<UpscaleModelsResponse> {
  const res = await api.get<UpscaleModelsResponse>('/system/upscale-models', {
    params: checkpoint ? { checkpoint } : undefined,
  });
  return res.data;
}

export async function getQualityProfiles(): Promise<QualityProfilesResponse> {
  const res = await api.get<QualityProfilesResponse>('/system/quality-profiles');
  return res.data;
}

export async function getPromptFactoryCheckpointPreferences(): Promise<PromptFactoryCheckpointPreferencesResponse> {
  const res = await api.get<PromptFactoryCheckpointPreferencesResponse>(
    '/system/prompt-factory-checkpoint-preferences',
  )
  return res.data
}

export async function updatePromptFactoryCheckpointPreferences(
  data: PromptFactoryCheckpointPreferencesReplaceRequest,
): Promise<PromptFactoryCheckpointPreferencesResponse> {
  const res = await api.put<PromptFactoryCheckpointPreferencesResponse>(
    '/system/prompt-factory-checkpoint-preferences',
    data,
  )
  return res.data
}

export async function getPromptTemplates(): Promise<PromptTemplatesResponse> {
  const res = await api.get<PromptTemplatesResponse>('/system/prompt-templates');
  return res.data;
}

export async function exportMetadata(format: MetadataExportFormat): Promise<Blob> {
  const res = await api.get<Blob>('/export/metadata', {
    params: { format },
    responseType: 'blob',
  })
  return res.data
}

export async function getQueueSummary(): Promise<QueueSummary> {
  const res = await api.get<QueueSummary>('/generations/queue/summary')
  return res.data
}

export async function cancelAllQueued(): Promise<{ cancelled: number }> {
  const res = await api.post<{ cancelled: number }>('/generations/cancel-all-queued')
  return res.data
}

// ---------------------------------------------------------------------------
// Curation
// ---------------------------------------------------------------------------

export interface CurationItem {
  id: string
  image_path: string | null
  thumbnail_path: string | null
  upscaled_preview_path: string | null
  checkpoint: string
  steps: number
  cfg: number
  quality_score: number | null
  publish_approved: number  // 0=pending, 1=approved, 2=rejected
  tags: string | null
  prompt: string
  is_favorite?: boolean
}

export interface CurationQueueResponse {
  items: CurationItem[]
  total: number
  approved_today: number
}

export async function getCurationQueue(): Promise<CurationQueueResponse> {
  const res = await api.get<CurationQueueResponse>('/curation/queue')
  return res.data
}

export async function approveCurationItem(id: string): Promise<void> {
  await api.post(`/curation/${id}/approve`)
}

export async function rejectCurationItem(id: string): Promise<void> {
  await api.post(`/curation/${id}/reject`)
}

export async function recalculateCurationScores(): Promise<void> {
  await api.post('/curation/recalculate')
}

export async function autoApproveCuration(threshold = 70): Promise<{ approved: number }> {
  const res = await api.post<{ approved: number }>('/curation/auto-approve', null, {
    params: { threshold },
  })
  return res.data
}

// ---------------------------------------------------------------------------
// Direction Board
// ---------------------------------------------------------------------------

export interface DirectionReference {
  id: string
  external_url: string | null
  generation_id: string | null
  title: string
  notes: string | null
  tags: string | null  // JSON array string
  source: 'external' | 'internal'
  created_at: string
}

export interface DirectionReferenceCreate {
  external_url?: string | null
  generation_id?: string | null
  title: string
  notes?: string | null
  tags?: string[] | null
}

export async function getDirectionReferences(): Promise<DirectionReference[]> {
  const res = await api.get<DirectionReference[]>('/direction/references')
  return res.data
}

export async function createDirectionReference(
  data: DirectionReferenceCreate,
): Promise<DirectionReference> {
  const res = await api.post<DirectionReference>('/direction/references', data)
  return res.data
}

export async function deleteDirectionReference(id: string): Promise<void> {
  await api.delete(`/direction/references/${id}`)
}

export async function pinGenerationToDirection(generationId: string): Promise<DirectionReference> {
  const res = await api.post<DirectionReference>(`/direction/pin/${generationId}`)
  return res.data
}

// ---------------------------------------------------------------------------
// Quality AI
// ---------------------------------------------------------------------------

export interface AnalyzeResult {
  generation_id: string;
  quality_ai_score: number | null;
  quality_score: number | null;
  hand_count: number;
  finger_anomaly: number;
  quality_tags: string[];
  wd14_bad_tags: string[];
  wd14_good_tags: string[];
  hands_finger_counts: number[];
}

export interface BatchAnalyzeResult {
  processed: number;
  skipped: number;
  errors: number;
}

export interface QualityReport {
  total_analyzed: number;
  anomaly_count: number;
  anomaly_rate: number;
  bad_tag_distribution: Record<string, number>;
  score_histogram: Record<string, number>;
}

export async function analyzeGenerationQuality(generationId: string): Promise<AnalyzeResult> {
  const res = await api.post<AnalyzeResult>(`/quality/analyze/${generationId}`);
  return res.data;
}

export async function batchAnalyzeQuality(limit = 50, skipAnalyzed = true): Promise<BatchAnalyzeResult> {
  const res = await api.post<BatchAnalyzeResult>('/quality/analyze-batch', {
    limit,
    skip_analyzed: skipAnalyzed,
  });
  return res.data;
}

export async function getQualityReport(): Promise<QualityReport> {
  const res = await api.get<QualityReport>('/quality/report');
  return res.data;
}
