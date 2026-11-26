/** 争议定位前端领域助手：URL 别名解析与按“定位单+退件”隔离的断线草稿。
 *  注意：草稿键必须包含定位单与退件 id，绝不允许只按字段名共享，
 *  否则两个事实表的同名字段会互相串用处置决定。
 */
import type { LocationQuery } from 'vue-router'

export type LocatorQuery = {
  locatorRef: string
  factTable: string
  field: string
  reason: string
}

function first(query: LocationQuery, keys: string[]): string {
  for (const key of keys) {
    const value = query[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) {
      return value[0].trim()
    }
  }
  return ''
}

export function readLocatorQuery(query: LocationQuery): LocatorQuery {
  return {
    locatorRef: first(query, [
      'locator', 'locatorId', 'locator_id', 'dispute', 'disputeId', 'code', '定位编号', '定位单',
    ]),
    factTable: first(query, [
      'fact_table', 'factTable', 'fact', 'table', '所属事实表', '来源事实表', '事实表',
    ]),
    field: first(query, [
      'field', 'field_name', 'fieldName', '责任字段', '退化字段', '字段',
    ]),
    reason: first(query, [
      'reason', 'reasonName', 'pendingReason', 'pending_reason', 'reason_name', '待处理原因', '原因',
    ]),
  }
}

export function locatorHref(
  path: string,
  scope: { locatorRef?: string; factTable?: string; field?: string; reason?: string },
): string {
  const params = new URLSearchParams()
  params.set('dispute', '1')
  if (scope.locatorRef) params.set('locator', scope.locatorRef)
  if (scope.factTable) params.set('fact_table', scope.factTable)
  if (scope.field) params.set('field', scope.field)
  if (scope.reason) params.set('reason', scope.reason)
  return `${path}?${params.toString()}`
}

const DRAFT_PREFIX = 'dfzr:disposition-draft:'

/** 草稿作用域精确到 定位单(或裸条件) + 退件 id，保证同名字段跨事实表不串单。 */
export function draftStorageKey(scopeKey: string, returnId: number | string): string {
  return `${DRAFT_PREFIX}${scopeKey}:${returnId}`
}

export function loadDraft(scopeKey: string, returnId: number | string): string {
  try {
    return window.localStorage.getItem(draftStorageKey(scopeKey, returnId)) ?? ''
  } catch {
    return ''
  }
}

export function saveDraftLocal(scopeKey: string, returnId: number | string, text: string): void {
  try {
    if (text) window.localStorage.setItem(draftStorageKey(scopeKey, returnId), text)
    else window.localStorage.removeItem(draftStorageKey(scopeKey, returnId))
  } catch {
    /* 隐私模式等场景下忽略本地暂存失败 */
  }
}

export function clearDraftLocal(scopeKey: string, returnId: number | string): void {
  try {
    window.localStorage.removeItem(draftStorageKey(scopeKey, returnId))
  } catch {
    /* ignore */
  }
}
