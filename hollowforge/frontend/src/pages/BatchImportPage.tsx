import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { createGeneration } from '../api/client'
import type { GenerationCreate } from '../api/client'

const PLACEHOLDER = `Set_No|Checkpoint|LoRA_1|Strength_1|LoRA_2|Strength_2|LoRA_3|Strength_3|LoRA_4|Strength_4|Sampler|Steps|CFG|Clip_Skip|Resolution|Positive_Prompt|Negative_Prompt
1|prefectIllustriousXL_v70.safetensors|FullCoverLatexMask.safetensors|0.7|incase_new_style_red_ill.safetensors|0.6|None|0.0|None|0.0|euler_a|30|5.5|2|832x1216|masterpiece, best quality, 1girl, solo, lab-451, glossy materials, controlled composition...|lowres, blurry, bad anatomy...
2|animayhemPaleRider_v2TrueGrit.safetensors|latex_hood_illustrious.safetensors|0.65|GEN(illust) 0.2v.safetensors|0.55|None|0.0|None|0.0|euler_a|35|5.5|2|832x1216|masterpiece, best quality, 1girl, solo, containment design, reflective surfaces, editorial framing...|lowres, blurry, bad anatomy...`

interface ParsedRow {
  setNo: string
  checkpoint: string
  lora1: string
  lora1Strength: number
  lora2: string
  lora2Strength: number
  lora3: string
  lora3Strength: number
  lora4: string
  lora4Strength: number
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

const isResolutionFmt = (s: string) => /^\d{3,5}x\d{3,5}$/i.test(s.trim())

/** Detect LoRA slot count (2, 3, or 4) from the header line. */
function detectLoraCount(lines: string[]): number {
  const headerLine = lines.find((l) => /^set_no\|/i.test(l))
  if (!headerLine) return 2
  const cols = headerLine.toLowerCase().split('|')
  if (cols.some((c) => c.includes('lora_4') || c === 'strength_4')) return 4
  if (cols.some((c) => c.includes('lora_3') || c === 'strength_3')) return 3
  return 2
}

function parseCSV(raw: string): ParsedRow[] {
  // Strip BOM and normalize line endings
  const cleaned = raw.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = cleaned
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  const isHeaderLine = (l: string) => /^set_no\|/i.test(l)
  const loraCount = detectLoraCount(lines)

  // Column layout:
  //   [0]=Set_No  [1]=Checkpoint
  //   [2..2+loraCount*2-1] = LoRA pairs (name, strength)
  //   [samplerIdx] = Sampler
  //   [samplerIdx+1] = Steps
  //   [samplerIdx+2] = CFG
  //   [samplerIdx+3] = Clip_Skip (if not resolution fmt) OR Resolution
  //   [+4 or +3] = Resolution   [next] = Positive_Prompt   [rest] = Negative_Prompt
  const samplerIdx = 2 + loraCount * 2
  const minCols = samplerIdx + 4 // sampler + steps + cfg + resolution + prompt (minimum)

  const rows: ParsedRow[] = []
  for (const line of lines) {
    if (isHeaderLine(line)) continue

    const cols = line.split('|')

    const makeError = (err: string): ParsedRow => ({
      setNo: cols[0]?.trim() ?? '?',
      checkpoint: '',
      lora1: '', lora1Strength: 0,
      lora2: '', lora2Strength: 0,
      lora3: '', lora3Strength: 0,
      lora4: '', lora4Strength: 0,
      sampler: '', steps: 0, cfg: 0, clipSkip: null,
      width: 0, height: 0, positivePrompt: '', negativePrompt: '',
      error: err,
    })

    if (cols.length < minCols) {
      rows.push(makeError(`컬럼 수 부족 (${cols.length}, 최소 ${minCols} 필요, LoRA ${loraCount}개 감지)`))
      continue
    }

    const setNo = cols[0].trim()
    const checkpoint = cols[1].trim()

    // Extract LoRA pairs (index-based, up to loraCount)
    const getLoRA = (slot: number) => ({
      name: slot < loraCount ? (cols[2 + slot * 2]?.trim() ?? '') : '',
      strength: slot < loraCount ? (parseFloat(cols[2 + slot * 2 + 1] ?? '0') || 0) : 0,
    })
    const l1 = getLoRA(0)
    const l2 = getLoRA(1)
    const l3 = getLoRA(2)
    const l4 = getLoRA(3)

    const sampler = cols[samplerIdx]?.trim() ?? ''
    const stepsRaw = cols[samplerIdx + 1]?.trim() ?? '0'
    const cfgRaw = cols[samplerIdx + 2]?.trim() ?? '7'

    // Auto-detect clip_skip: col after CFG is Clip_Skip if NOT a resolution string
    const afterCfg = cols[samplerIdx + 3]?.trim() ?? ''
    const hasClipSkip = !isResolutionFmt(afterCfg)

    let clipSkip: number | null = null
    let resolutionIdx: number

    if (hasClipSkip) {
      const parsed = parseInt(afterCfg, 10)
      clipSkip = !isNaN(parsed) && afterCfg !== '' ? parsed : null
      resolutionIdx = samplerIdx + 4
    } else {
      resolutionIdx = samplerIdx + 3
    }

    if (cols.length < resolutionIdx + 2) {
      rows.push(makeError(`컬럼 수 부족 (resolution/prompt 없음, col=${cols.length})`))
      continue
    }

    const resolution = cols[resolutionIdx]?.trim() ?? ''
    const positivePrompt = cols[resolutionIdx + 1]?.trim() ?? ''
    const negativePrompt = cols.slice(resolutionIdx + 2).join('|').trim()

    const [wStr, hStr] = resolution.split('x')
    const width = parseInt(wStr ?? '832', 10)
    const height = parseInt(hStr ?? '1216', 10)
    const steps = parseInt(stepsRaw, 10)

    if (isNaN(steps) || steps < 1) {
      rows.push(makeError(`Steps 파싱 실패: "${stepsRaw}" (컬럼 오프셋 = ${samplerIdx + 1})`))
      continue
    }

    rows.push({
      setNo,
      checkpoint,
      lora1: l1.name, lora1Strength: l1.strength,
      lora2: l2.name, lora2Strength: l2.strength,
      lora3: l3.name, lora3Strength: l3.strength,
      lora4: l4.name, lora4Strength: l4.strength,
      sampler,
      steps,
      cfg: parseFloat(cfgRaw) || 6,
      clipSkip,
      width: isNaN(width) ? 832 : width,
      height: isNaN(height) ? 1216 : height,
      positivePrompt,
      negativePrompt,
    })
  }
  return rows
}

function rowToPayload(row: ParsedRow): GenerationCreate {
  const loras: { filename: string; strength: number; category: null }[] = []
  const addLora = (name: string, strength: number) => {
    if (name && name.toLowerCase() !== 'none') {
      loras.push({ filename: name, strength, category: null })
    }
  }
  addLora(row.lora1, row.lora1Strength)
  addLora(row.lora2, row.lora2Strength)
  addLora(row.lora3, row.lora3Strength)
  addLora(row.lora4, row.lora4Strength)
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

/** Render a compact LoRA list for preview (skip None/empty) */
function LoRAList({ row }: { row: ParsedRow }) {
  const loras = [
    { name: row.lora1, strength: row.lora1Strength },
    { name: row.lora2, strength: row.lora2Strength },
    { name: row.lora3, strength: row.lora3Strength },
    { name: row.lora4, strength: row.lora4Strength },
  ].filter((l) => l.name && l.name.toLowerCase() !== 'none')

  if (loras.length === 0) return <span className="text-gray-600">없음</span>

  return (
    <div className="space-y-0.5">
      {loras.map((l, i) => (
        <div key={i} className={`truncate ${i === 0 ? 'text-violet-300' : 'text-violet-200/70'}`} title={l.name}>
          {l.name.replace(/\.safetensors$/i, '')}
          <span className="text-violet-400/60 ml-1">{l.strength}</span>
        </div>
      ))}
    </div>
  )
}

export default function BatchImportPage() {
  const [csv, setCsv] = useState('')
  const [parsed, setParsed] = useState<ParsedRow[] | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<{ setNo: string; ok: boolean; msg: string }[]>([])
  const [loadedFileName, setLoadedFileName] = useState<string | null>(null)

  const createMutation = useMutation({ mutationFn: createGeneration })

  async function handleFileSelect(file: File | null) {
    if (!file) return
    try {
      const text = await file.text()
      setCsv(text)
      setLoadedFileName(file.name)
      setParsed(null)
      setResults([])
      toast.success(`${file.name} 불러오기 완료`)
    } catch (err) {
      const message = err instanceof Error ? err.message : '파일 읽기 실패'
      toast.error(message)
    }
  }

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
          <p className="text-sm text-gray-500 mt-0.5">
            파이프(|) 구분 CSV 붙여넣기 → 한번에 큐 등록. LoRA 2~4개 자동 감지 (헤더 필수)
          </p>
        </div>
      </div>

      {/* CSV input */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4 space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <label className="text-sm font-medium text-gray-300">CSV 입력</label>
            <p className="mt-1 text-xs text-gray-500">
              파일 업로드와 텍스트 붙여넣기를 모두 지원합니다.
            </p>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-xs font-medium text-gray-300 hover:border-violet-500/50 hover:text-violet-300">
            <input
              type="file"
              accept=".csv,.txt,text/csv,text/plain"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null
                void handleFileSelect(file)
                e.currentTarget.value = ''
              }}
            />
            CSV 파일 불러오기
          </label>
        </div>
        {loadedFileName && (
          <div className="rounded-lg border border-gray-800 bg-gray-950/80 px-3 py-2 text-xs text-gray-400">
            불러온 파일: <span className="font-mono text-gray-300">{loadedFileName}</span>
          </div>
        )}
        <div className="text-xs font-medium text-gray-400">또는 CSV 텍스트 붙여넣기</div>
        <textarea
          className="w-full h-52 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-xs font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-violet-500 resize-y"
          placeholder={PLACEHOLDER}
          value={csv}
          onChange={(e) => {
            setCsv(e.target.value)
            setLoadedFileName(null)
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

          {/* Mobile card view */}
          <div className="space-y-3 md:hidden">
            {parsed.map((row) => {
              const result = results.find((r) => r.setNo === row.setNo)
              return (
                <div
                  key={row.setNo}
                  className={`rounded-lg border border-gray-800 bg-gray-950/50 p-3 space-y-2 ${row.error ? 'opacity-50' : ''}`}
                >
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
                  <div className="text-xs">
                    <LoRAList row={row} />
                  </div>
                  <p className="text-xs font-mono text-gray-400">
                    {row.width}×{row.height} · {row.steps}s · cfg{row.cfg} · {row.sampler}
                    {row.clipSkip != null ? ` · clip${row.clipSkip}` : ''}
                  </p>
                  <p className="text-xs text-gray-400 line-clamp-2" title={row.positivePrompt}>
                    {row.positivePrompt}
                  </p>
                  {row.error && (
                    <p className="text-xs text-red-400 break-words">{row.error}</p>
                  )}
                </div>
              )
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 uppercase tracking-wider">
                  <th className="pr-3 py-2">#</th>
                  <th className="pr-3 py-2">체크포인트</th>
                  <th className="pr-3 py-2">LoRA (최대 4개)</th>
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
                      <td className="pr-3 py-2 max-w-[150px]">
                        <LoRAList row={row} />
                      </td>
                      <td className="pr-3 py-2 font-mono text-gray-400 whitespace-nowrap">
                        {row.width}×{row.height} · {row.steps}s · cfg{row.cfg} · {row.sampler}
                        {row.clipSkip != null ? ` · clip${row.clipSkip}` : ''}
                      </td>
                      <td className="pr-3 py-2 text-gray-400 max-w-[200px] truncate" title={row.positivePrompt}>
                        {row.positivePrompt}
                      </td>
                      <td className="py-2 max-w-[220px]">
                        {row.error ? (
                          <span className="text-red-400 text-[11px] break-words" title={row.error}>
                            오류: {row.error}
                          </span>
                        ) : result ? (
                          result.ok ? (
                            <span className="text-emerald-400">등록됨</span>
                          ) : (
                            <span className="text-red-400 text-[11px] break-words" title={result.msg}>
                              실패: {result.msg}
                            </span>
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
