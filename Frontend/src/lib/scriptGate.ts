/**
 * 用途：判断配置页是否应阻断「开始生成」，并给出跳转文案页/进度页的引导。
 */
import { isGenerationInProgress, resolveTaskStepPath } from './taskFlow'
import type { RiskCheck, TaskStatus } from '../types/domain'

export type ScriptGateTarget = 'script' | 'progress'

export interface ScriptGateAction {
  target: ScriptGateTarget
  label: string
}

export interface ScriptGateState {
  blocked: boolean
  message: string
  primaryAction: ScriptGateAction | null
  secondaryAction: ScriptGateAction | null
}

interface ScriptGateInput {
  status?: TaskStatus
  errorCode?: string | null
  latestRiskCheck?: RiskCheck | null
}

function progressAction(label = '查看生成进度'): ScriptGateAction {
  return { target: 'progress', label }
}

function scriptAction(label = '去文案与合规'): ScriptGateAction {
  return { target: 'script', label }
}

/** 解析配置页文案门禁状态与引导按钮。 */
export function resolveScriptGate(input: ScriptGateInput): ScriptGateState {
  const { status, errorCode, latestRiskCheck } = input

  if (!status) {
    return { blocked: true, message: '任务加载中…', primaryAction: null, secondaryAction: null }
  }

  if (isGenerationInProgress(status)) {
    return {
      blocked: true,
      message: '视频正在生成中，请前往生成进度页查看状态。',
      primaryAction: progressAction(),
      secondaryAction: null,
    }
  }

  if (status === 'content_rejected') {
    return {
      blocked: true,
      message: '文案存在高风险，请返回修改并重新检查后再生成。',
      primaryAction: scriptAction(),
      secondaryAction: null,
    }
  }

  if (status === 'content_review_required' && latestRiskCheck?.reviewed_by !== 'user') {
    return {
      blocked: true,
      message: '文案合规尚未人工确认，请返回「文案与合规」页填写确认说明后再继续。',
      primaryAction: scriptAction(),
      secondaryAction: null,
    }
  }

  if (status === 'failed') {
    const step = resolveTaskStepPath(status, errorCode)
    if (errorCode === 'TRANSCRIBE_FAILED') {
      return {
        blocked: true,
        message: '视频文案识别失败，请返回文案页重新识别或粘贴文案。',
        primaryAction: scriptAction(),
        secondaryAction: null,
      }
    }
    if (errorCode === 'GENERATION_FAILED' || errorCode === 'PIPELINE_FAILED') {
      return {
        blocked: false,
        message: '',
        primaryAction: null,
        secondaryAction: null,
      }
    }
    return {
      blocked: true,
      message: '任务处理失败，请根据失败类型返回对应步骤继续。',
      primaryAction: step === 'progress' ? progressAction() : scriptAction(),
      secondaryAction: step === 'progress' ? scriptAction() : progressAction(),
    }
  }

  if (
    status !== 'script_confirmed' &&
    status !== 'content_review_required' &&
    !(status === 'transcribed' && latestRiskCheck?.risk_status === 'passed')
  ) {
    return {
      blocked: true,
      message: '请先完成文案确认与合规检查，再配置并启动生成。',
      primaryAction: scriptAction(),
      secondaryAction: null,
    }
  }

  return { blocked: false, message: '', primaryAction: null, secondaryAction: null }
}

/** 文案页是否处于「识别失败」态（勿与生成失败混淆）。 */
export function isTranscribeFailure(status?: TaskStatus, errorCode?: string | null, hasScriptText = false): boolean {
  if (status !== 'failed') return false
  if (errorCode === 'TRANSCRIBE_FAILED') return true
  if (errorCode === 'GENERATION_FAILED' || errorCode === 'PIPELINE_FAILED') return false
  return !hasScriptText
}
