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
  upscaled_image_path: string | null;
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

export interface LoraProfileResponse {
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

export interface GalleryQuery {
  page?: number;
  per_page?: number;
  checkpoint?: string | null;
  tags?: string[] | null;
  search?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  sort_by?: string;
  sort_order?: string;
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
}

export interface ComfyUIStatus {
  connected: boolean;
  url: string;
  system_stats?: Record<string, unknown>;
  message?: string;
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

export interface ReproduceRequest {
  mode: 'exact' | 'variation';
  seed?: number | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

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
): Promise<GenerationResponse> {
  const res = await api.post<GenerationResponse>(`/generations/${id}/upscale`, {
    upscale_model,
  });
  return res.data;
}

export async function getGallery(query: GalleryQuery): Promise<PaginatedResponse<GenerationResponse>> {
  const res = await api.get<PaginatedResponse<GenerationResponse>>('/gallery', { params: query });
  return res.data;
}

export async function deleteGalleryItem(id: string): Promise<void> {
  await api.delete(`/gallery/${id}`);
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

export async function getLoras(checkpoint?: string | null): Promise<LoraProfileResponse[]> {
  const res = await api.get<LoraProfileResponse[]>('/loras', {
    params: checkpoint ? { checkpoint } : undefined,
  });
  return res.data;
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

export async function getModels(): Promise<ModelsResponse> {
  const res = await api.get<ModelsResponse>('/system/models');
  return res.data;
}

export async function syncModels(): Promise<SyncResponse> {
  const res = await api.post<SyncResponse>('/system/sync');
  return res.data;
}

export async function getUpscaleModels(): Promise<UpscaleModelsResponse> {
  const res = await api.get<UpscaleModelsResponse>('/system/upscale-models');
  return res.data;
}

export async function getQualityProfiles(): Promise<QualityProfilesResponse> {
  const res = await api.get<QualityProfilesResponse>('/system/quality-profiles');
  return res.data;
}

export async function getPromptTemplates(): Promise<PromptTemplatesResponse> {
  const res = await api.get<PromptTemplatesResponse>('/system/prompt-templates');
  return res.data;
}
