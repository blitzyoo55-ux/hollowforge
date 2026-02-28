import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createGeneration } from '../api/client'
import type { GenerationCreate } from '../api/client'

const PLACEHOLDER = `Set_No|Checkpoint|LoRA_1|LoRA_1_Strength|LoRA_2|LoRA_2_Strength|Sampler|Steps|CFG|Clip_Skip|Resolution|Positive_Prompt|Negative_Prompt
1|waiIllustriousSDXL_v160.safetensors|incase_new_style_red_ill.safetensors|0.7|plumpill.safetensors|0.75|euler_a|28|6.0|2|832x1216|score_9, 1girl, solo, squat...|score_5, 3d, realistic...`

interface ParsedRow {
  setNo: string
  checkpoint: string
  lora1: string
  lora1Strength: number
  lora2: string
  lora2Strength: number
  sampler: string
  steps: number
  cfg: number
  clipSkip: number | null
  width: number
  height: number
  positivePrompt: string
  negativePrompt: string
  error?: string
}

function parseCSV(raw: string): ParsedRow[] {
  // Strip BOM and normalize line endings
  const cleaned = raw.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = cleaned
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  // Detect header line (case-insensitive prefix match)
  const isHeaderLine = (l: string) => /^set_no\|/i.test(l)

  const rows: ParsedRow[] = []
  for (const line of lines) {
    // Skip header row
    if (isHeaderLine(line)) continue

    const cols = line.split('|')

    if (cols.length < 11) {
      rows.push({
        setNo: cols[0] ?? '?',
        checkpoint: '',
        lora1: '',
        lora1Strength: 0,
        lora2: '',
        lora2Strength: 0,
        sampler: '',
        steps: 0,
        cfg: 0,
        clipSkip: null,
        width: 0,
        height: 0,
        positivePrompt: '',
        negativePrompt: '',
        error: `컬럼 수 부족 (${cols.length}, 최소 11 필요)`,
      })
      continue
    }

    // Auto-detect clip_skip by inspecting col[9]:
    //   resolution format (e.g. "832x1216") → no clip_skip (col[9] = resolution)
    //   otherwise (e.g. "2")               → has clip_skip (col[9] = clip_skip, col[10] = resolution)
    const isResolutionFmt = (s: string) => /^\d{3,5}x\d{3,5}$/i.test(s.trim())
    const hasClipSkip = !isResolutionFmt(cols[9] ?? '')

    if (cols.length < (hasClipSkip ? 12 : 11)) {
      rows.push({
        setNo: cols[0] ?? '?',
        checkpoint: '',
        lora1: '',
        lora1Strength: 0,
        lora2: '',
        lora2Strength: 0,
        sampler: '',
        steps: 0,
        cfg: 0,
        clipSkip: null,
        width: 0,
        height: 0,
        positivePrompt: '',
        negativePrompt: '',
        error: `컬럼 수 부족 (${cols.length}/${hasClipSkip ? 12 : 11})`,
      })
      continue
    }

    let setNo: string, checkpoint: string, lora1: string, lora1StrRaw: string
    let lora2: string, lora2StrRaw: string, sampler: string, stepsRaw: string, cfgRaw: string
    let clipSkipRaw: string | undefined
    let resolution: string
    let positivePrompt: string
    let negParts: string[]

    if (hasClipSkip) {
      ;[setNo, checkpoint, lora1, lora1StrRaw, lora2, lora2StrRaw, sampler, stepsRaw, cfgRaw, clipSkipRaw, resolution, positivePrompt, ...negParts] = cols as [string, string, string, string, string, string, string, string, string, string, string, string, ...string[]]
    } else {
      ;[setNo, checkpoint, lora1, lora1StrRaw, lora2, lora2StrRaw, sampler, stepsRaw, cfgRaw, resolution, positivePrompt, ...negParts] = cols as [string, string, string, string, string, string, string, string, string, string, string, ...string[]]
    }

    const negativePrompt = negParts.join('|')
    const [wStr, hStr] = resolution.split('x')
    const width = parseInt(wStr ?? '832', 10)
    const height = parseInt(hStr ?? '1216', 10)

    let clipSkip: number | null = null
    if (clipSkipRaw !== undefined && clipSkipRaw.trim() !== '') {
      const parsed = parseInt(clipSkipRaw.trim(), 10)
      clipSkip = Number.isNaN(parsed) ? null : parsed
    }

    rows.push({
      setNo: setNo.trim(),
      checkpoint: checkpoint.trim(),
      lora1: lora1.trim(),
      lora1Strength: parseFloat(lora1StrRaw) || 0,
      lora2: lora2.trim(),
      lora2Strength: parseFloat(lora2StrRaw) || 0,
      sampler: sampler.trim(),
      steps: parseInt(stepsRaw, 10),
      cfg: parseFloat(cfgRaw) || 6,
      clipSkip,
      width: Number.isNaN(width) ? 832 : width,
      height: Number.isNaN(height) ? 1216 : height,
      positivePrompt: positivePrompt.trim(),
      negativePrompt: negativePrompt.trim(),
    })
  }
  return rows
}

function rowToPayload(row: ParsedRow): GenerationCreate {
  const loras = []
  if (row.lora1 && row.lora1.toLowerCase() !== 'none') {
    loras.push({ filename: row.lora1, strength: row.lora1Strength, category: null })
  }
  if (row.lora2 && row.lora2.toLowerCase() !== 'none') {
    loras.push({ filename: row.lora2, strength: row.lora2Strength, category: null })
  }
  return {
    prompt: row.positivePrompt,
    negative_prompt: row.negativePrompt || null,
    checkpoint: row.checkpoint,
    loras,
    steps: row.steps,
    cfg: row.cfg,
    clip_skip: row.clipSkip ?? null,
    width: row.width,
    height: row.height,
    sampler: row.sampler,
    tags: [`import_set_${row.setNo.padStart(2, '0')}`],
    notes: `Imported Set #${row.setNo}`,
  }
}

export default function BatchImportPage() {
  const [csv, setCsv] = useState('')
  const [parsed, setParsed] = useState<ParsedRow[] | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<{ setNo: string; ok: boolean; msg: string }[]>([])

  const createMutation = useMutation({ mutationFn: createGeneration })

  function handleParse() {
    if (!csv.trim()) {
      toast.error('CSV 내용을 입력해주세요')
      return
    }
    const rows = parseCSV(csv)
    if (rows.length === 0) {
      toast.error('파싱 가능한 행이 없습니다')
      return
    }
    setParsed(rows)
    setResults([])
    toast.success(`${rows.length}건 파싱 완료`)
  }

  async function handleSubmitAll() {
    if (!parsed) return
    const valid = parsed.filter((r) => !r.error)
    if (valid.length === 0) {
      toast.error('제출 가능한 유효한 행이 없습니다')
      return
    }

    setSubmitting(true)
    setResults([])
    const newResults: typeof results = []

    for (const row of valid) {
      try {
        await createMutation.mutateAsync(rowToPayload(row))
        newResults.push({ setNo: row.setNo, ok: true, msg: '성공' })
      } catch (err: unknown) {
        // Extract backend error detail from axios response if available
        let msg = '오류'
        if (err && typeof err === 'object' && 'response' in err) {
          const axiosErr = err as { response?: { data?: { detail?: unknown }; status?: number } }
          const detail = axiosErr.response?.data?.detail
          const status = axiosErr.response?.status
          if (detail) {
            msg = typeof detail === 'string' ? detail : JSON.stringify(detail)
          } else if (status) {
            msg = `HTTP ${status} 오류`
          }
        } else if (err instanceof Error) {
          msg = err.message
        }
        newResults.push({ setNo: row.setNo, ok: false, msg })
      }
      setResults([...newResults])
    }

    setSubmitting(false)
    const succeeded = newResults.filter((r) => r.ok).length
    const failed = newResults.length - succeeded
    if (failed === 0) {
      toast.success(`${succeeded}건 전량 큐 등록 완료`)
    } else {
      toast.warning(`${succeeded}건 성공 / ${failed}건 실패`)
    }
  }

  const validRows = parsed?.filter((r) => !r.error) ?? []
  const errorRows = parsed?.filter((r) => r.error) ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Batch Import</h1>
          <p className="text-sm text-gray-500 mt-0.5">파이프(|) 구분 CSV를 붙여넣고 한번에 큐에 등록합니다</p>
        </div>
      </div>

      {/* CSV input */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4 space-y-3">
        <label className="text-sm font-medium text-gray-300">CSV 입력</label>
        <textarea
          className="w-full h-52 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-xs font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-violet-500 resize-y"
          placeholder={PLACEHOLDER}
          value={csv}
          onChange={(e) => {
            setCsv(e.target.value)
            setParsed(null)
            setResults([])
          }}
        />
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={handleParse}
              className="w-full rounded-lg border border-violet-500/40 bg-violet-600/10 px-4 py-2 text-sm font-medium text-violet-300 hover:bg-violet-600/20 transition-colors duration-200 sm:w-auto"
            >
              파싱 미리보기
            </button>
          {parsed && (
            <span className="text-xs text-gray-500">
              {validRows.length}건 유효
              {errorRows.length > 0 && (
                <span className="ml-2 text-red-400">{errorRows.length}건 오류</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Preview table */}
      {parsed && parsed.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4 space-y-4">
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-sm font-semibold text-gray-200">
              미리보기 ({parsed.length}건)
            </h2>
            <button
              type="button"
              disabled={submitting || validRows.length === 0}
              onClick={handleSubmitAll}
              className="w-full rounded-lg border border-emerald-500/40 bg-emerald-600/10 px-4 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 sm:w-auto"
            >
              {submitting ? '제출 중...' : `전체 큐 등록 (${validRows.length}건)`}
            </button>
          </div>

          <div className="space-y-3 md:hidden">
            {parsed.map((row) => {
              const result = results.find((r) => r.setNo === row.setNo)
              return (
                <div key={row.setNo} className={`rounded-lg border border-gray-800 bg-gray-950/50 p-3 space-y-2 ${row.error ? 'opacity-50' : ''}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-gray-400">#{row.setNo}</span>
                    <span className="text-xs">
                      {row.error ? (
                        <span className="text-red-400" title={row.error}>오류</span>
                      ) : result ? (
                        result.ok ? (
                          <span className="text-emerald-400">등록됨</span>
                        ) : (
                          <span className="text-red-400" title={result.msg}>실패</span>
                        )
                      ) : (
                        <span className="text-gray-600">대기</span>
                      )}
                    </span>
                  </div>
                  <p className="text-xs text-gray-300 break-all">
                    {row.checkpoint.replace(/\.safetensors$/i, '')}
                  </p>
                  <div className="space-y-1 text-xs text-violet-300">
                    {row.lora1 && row.lora1.toLowerCase() !== 'none' && (
                      <p className="break-all">
                        {row.lora1.replace(/\.safetensors$/i, '')}
                        <span className="text-violet-400/60 ml-1">{row.lora1Strength}</span>
                      </p>
                    )}
                    {row.lora2 && row.lora2.toLowerCase() !== 'none' && (
                      <p className="break-all text-violet-200/70">
                        {row.lora2.replace(/\.safetensors$/i, '')}
                        <span className="text-violet-400/60 ml-1">{row.lora2Strength}</span>
                      </p>
                    )}
                  </div>
                  <p className="text-xs font-mono text-gray-400">
                    {row.width}×{row.height} · {row.steps}s · cfg{row.cfg} · {row.sampler}{row.clipSkip != null ? ` · clip${row.clipSkip}` : ''}
                  </p>
                  <p className="text-xs text-gray-400 line-clamp-2" title={row.positivePrompt}>
                    {row.positivePrompt}
                  </p>
                </div>
              )
            })}
          </div>

          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 uppercase tracking-wider">
                  <th className="pr-3 py-2">#</th>
                  <th className="pr-3 py-2">체크포인트</th>
                  <th className="pr-3 py-2">LoRA</th>
                  <th className="pr-3 py-2">설정</th>
                  <th className="pr-3 py-2">프롬프트</th>
                  <th className="py-2">상태</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {parsed.map((row) => {
                  const result = results.find((r) => r.setNo === row.setNo)
                  return (
                    <tr key={row.setNo} className={row.error ? 'opacity-50' : ''}>
                      <td className="pr-3 py-2 font-mono text-gray-400">{row.setNo}</td>
                      <td className="pr-3 py-2 text-gray-300 max-w-[140px] truncate" title={row.checkpoint}>
                        {row.checkpoint.replace(/\.safetensors$/i, '')}
                      </td>
                      <td className="pr-3 py-2 text-violet-300 max-w-[120px]">
                        {row.lora1 && row.lora1.toLowerCase() !== 'none' ? (
                          <div className="truncate" title={row.lora1}>
                            {row.lora1.replace(/\.safetensors$/i, '')}
                            <span className="text-violet-400/60 ml-1">{row.lora1Strength}</span>
                          </div>
                        ) : null}
                        {row.lora2 && row.lora2.toLowerCase() !== 'none' ? (
                          <div className="truncate text-violet-200/70" title={row.lora2}>
                            {row.lora2.replace(/\.safetensors$/i, '')}
                            <span className="text-violet-400/60 ml-1">{row.lora2Strength}</span>
                          </div>
                        ) : null}
                      </td>
                      <td className="pr-3 py-2 font-mono text-gray-400 whitespace-nowrap">
                        {row.width}×{row.height} · {row.steps}s · cfg{row.cfg} · {row.sampler}{row.clipSkip != null ? ` · clip${row.clipSkip}` : ''}
                      </td>
                      <td className="pr-3 py-2 text-gray-400 max-w-[200px] truncate" title={row.positivePrompt}>
                        {row.positivePrompt}
                      </td>
                      <td className="py-2 max-w-[220px]">
                        {row.error ? (
                          <span className="text-red-400 text-[11px] break-words" title={row.error}>오류: {row.error}</span>
                        ) : result ? (
                          result.ok ? (
                            <span className="text-emerald-400">등록됨</span>
                          ) : (
                            <span className="text-red-400 text-[11px] break-words" title={result.msg}>실패: {result.msg}</span>
                          )
                        ) : (
                          <span className="text-gray-600">대기</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
