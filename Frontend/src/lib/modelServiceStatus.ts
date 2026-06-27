/**
 * 用途：通过 Vite 代理直接探测 8002/8003/8004 模型包装服务健康状态。
 * 避免旧版后端 runtime-info 缺少 cosyvoice_ok 等字段时误报「未就绪」。
 */

export interface ModelServiceHealth {
  ok: boolean
  mode: string | null
}

export interface ModelServicesHealth {
  cosyvoice: ModelServiceHealth
  heygem: ModelServiceHealth
  tuilionnx: ModelServiceHealth
}

async function probeOne(path: string): Promise<ModelServiceHealth> {
  try {
    const response = await fetch(path)
    if (!response.ok) return { ok: false, mode: null }
    const payload = (await response.json()) as { mode?: string }
    return { ok: true, mode: payload.mode ?? null }
  } catch {
    return { ok: false, mode: null }
  }
}

/** 并行探测 CosyVoice / HeyGem / TuiliONNX 包装服务。 */
export async function probeModelServices(): Promise<ModelServicesHealth> {
  const [cosyvoice, heygem, tuilionnx] = await Promise.all([
    probeOne('/model-health/cosyvoice'),
    probeOne('/model-health/heygem'),
    probeOne('/model-health/tuilionnx'),
  ])
  return { cosyvoice, heygem, tuilionnx }
}

export function formatModelServiceLabel(service: ModelServiceHealth): string {
  if (!service.ok) return '· 未就绪'
  return `· ${service.mode ?? 'ok'}`
}

export function hasStubModelMode(health: ModelServicesHealth): boolean {
  return [health.cosyvoice.mode, health.heygem.mode, health.tuilionnx.mode].includes('stub')
}
