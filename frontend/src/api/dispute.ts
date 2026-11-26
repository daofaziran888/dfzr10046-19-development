/** 争议定位与汇总退件处置 API。
 *  业务失败在本仓约定里仍是 HTTP 200 + ok:false，这里统一解析 JSON 并保留 ok/message。
 */
import { request } from './client'
import type { EntryRow } from '@/data/types'

export type LocateParams = {
  fact_table: string
  field: string
  reason?: string
  reviewer?: string
}

export type ConflictItem = {
  return_id: number
  return_code?: string
  in_new_round_scope?: boolean
  can_accept: boolean | null
  level?: 'info' | 'ok' | 'conflict' | string
  reason_code?: string
  suggestion?: string
  new_round_decision?: string
  draft_decision?: string
}

export type ConflictReport = {
  has_new_round: boolean
  conflict: boolean
  new_locator?: string | null
  new_round?: number
  items: ConflictItem[]
  acceptable_count?: number
  blocked_count?: number
  guidance?: string
}

export type LocatorDetail = {
  id: number
  定位编号: string
  code?: string
  fact_table?: string
  field?: string
  reason?: string
  round?: number
  轮次?: number
  conflict?: ConflictReport
  returns?: EntryRow[]
  items?: EntryRow[]
  total?: number
  [key: string]: unknown
}

export type DisputeResult = {
  ok: boolean
  message: string
  locator?: LocatorDetail
  entry?: EntryRow & Record<string, unknown>
  conflict?: boolean
  cross_fact_table?: boolean
  [key: string]: unknown
}

async function parse<T>(response: Response): Promise<T> {
  let data: unknown = null
  try {
    data = await response.json()
  } catch {
    if (!response.ok) throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  if (!response.ok && (data === null || typeof data !== 'object')) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return data as T
}

export async function disputeFields(factTable = ''): Promise<{
  fields: string[]
  fact_tables: string[]
  reasons: string[]
  decisions: string[]
  items: { fact_table: string; field: string; status?: string }[]
}> {
  const query = new URLSearchParams()
  if (factTable) query.set('fact_table', factTable)
  const response = await request(`/api/dispute/fields?${query.toString()}`)
  return parse(response)
}

export async function previewLocate(params: LocateParams): Promise<DisputeResult> {
  const query = new URLSearchParams({ fact_table: params.fact_table, field: params.field })
  if (params.reason) query.set('reason', params.reason)
  const response = await request(`/api/dispute/locate?${query.toString()}`)
  return parse(response)
}

export async function createLocator(params: LocateParams): Promise<DisputeResult> {
  const response = await request('/api/dispute/locators', {
    method: 'POST',
    body: JSON.stringify(params),
  })
  return parse<DisputeResult>(response)
}

export async function getLocator(ref: string): Promise<DisputeResult> {
  const response = await request(`/api/dispute/locators/${encodeURIComponent(ref)}`)
  return parse<DisputeResult>(response)
}

export async function saveDispositionDraft(body: Record<string, unknown>): Promise<DisputeResult> {
  const response = await request('/api/dispute/draft', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return parse<DisputeResult>(response)
}

export async function submitDisposition(body: Record<string, unknown>): Promise<DisputeResult> {
  const response = await request('/api/dispute/dispositions', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return parse<DisputeResult>(response)
}
