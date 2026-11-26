<template>
  <section
    id="disposition-panel"
    class="disposition-panel"
    data-testid="disposition-panel"
    data-test="summary-disposition disposition-list-panel"
    aria-label="汇总层处置清单"
  >
    <header class="disp-head">
      <div>
        <h3 data-testid="disposition-heading">汇总层处置清单</h3>
        <p class="disp-sub" data-testid="disposition-scope">
          <template v-if="scope.factTable || locator">
            当前定位：事实表「{{ scope.factTable || locator?.fact_table || locator?.所属事实表 }}」
            · 字段「{{ scope.field || locator?.field || locator?.责任字段 }}」
            <template v-if="scope.reason || locator?.reason || locator?.待处理原因">
              · 原因「{{ scope.reason || locator?.reason || locator?.待处理原因 }}」
            </template>
            <template v-if="locatorCode"> · 定位单 <span data-testid="disposition-locator-code">{{ locatorCode }}</span>（第 {{ locator?.轮次 ?? locator?.round ?? 1 }} 轮）</template>
          </template>
          <template v-else>未携带定位条件，展示全部待处理汇总退件；从「退化维度 → 争议定位」可按事实表与字段精确锁定。</template>
        </p>
      </div>
      <div class="disp-head-actions">
        <label class="reviewer-field">
          <span>审核人</span>
          <input
            v-model="reviewer"
            class="reviewer-input-head"
            data-testid="disposition-reviewer"
            name="reviewer"
            placeholder="审核人标识"
          />
        </label>
        <RouterLink
          v-if="locatorCode || scope.factTable"
          class="btn small"
          data-testid="roundtrip-locator"
          data-test="back-to-locator"
          :to="degensHref"
        >
          ← 返回责任字段定位
        </RouterLink>
        <button type="button" class="btn ghost small" data-testid="disposition-reload" @click="reload">
          刷新清单
        </button>
      </div>
    </header>

    <!-- 断线恢复提示 -->
    <div
      v-if="!online"
      class="banner offline"
      data-testid="offline-banner"
      role="alert"
    >
      网络连接已断开：已填写的处置意见按“定位单 + 退件”暂存在本机，不会串到同名字段的其他事实表退件；恢复网络后将自动重连。
    </div>
    <div
      v-else-if="recoveredMessage"
      class="banner recovered"
      data-testid="recovered-banner"
      role="status"
    >
      {{ recoveredMessage }}
    </div>

    <!-- 新旧轮次冲突报告 -->
    <div
      v-if="conflict && conflict.has_new_round"
      class="banner"
      :class="conflict.conflict ? 'conflict' : 'compatible'"
      data-testid="conflict-banner"
      :data-conflict="conflict.conflict ? 'true' : 'false'"
      role="alert"
    >
      <strong v-if="conflict.conflict">新旧两轮处置范围冲突：</strong>
      <strong v-else>存在新一轮定位（范围未冲突）：</strong>
      <span data-testid="conflict-guidance">{{ conflict.guidance }}</span>
      <ul class="conflict-items">
        <li
          v-for="item in conflict.items"
          :key="item.return_id"
          :data-testid="`conflict-item-${item.return_id}`"
          :data-can-accept="String(item.can_accept)"
        >
          退件 {{ item.return_code || item.return_id }}：
          <span v-if="item.can_accept === true" class="ok-text">
            原审核人的待提交处置仍可被新一轮接受。
          </span>
          <span v-else-if="item.can_accept === false" class="bad-text">
            该待提交处置不能被新一轮接受，应回原退件单独结案。
          </span>
          <span v-else>该退件可通过下方“单独结案”在原退件办结。</span>
          <span class="conflict-suggestion">{{ item.suggestion }}</span>
        </li>
      </ul>
    </div>

    <p v-if="errorMessage" class="error-text" role="alert" data-testid="disposition-error">
      {{ errorMessage }}
    </p>
    <p v-if="actionMessage" class="notice-text" role="status" data-testid="disposition-message">
      {{ actionMessage }}
    </p>

    <table v-if="rows.length" class="data-table disposition-table" data-testid="disposition-list">
      <thead>
        <tr>
          <th>退件编号</th>
          <th>来源事实表</th>
          <th>责任字段</th>
          <th>待处理原因</th>
          <th>当前状态</th>
          <th>处置决定 / 待提交意见</th>
          <th>审核人</th>
          <th>处置操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          :data-testid="`disposition-row-${row.id}`"
          :data-return-id="String(row.id)"
          :data-fact-table="String(row.来源事实表 ?? '')"
          :data-field="String(row.责任字段 ?? '')"
        >
          <td>{{ row.退件编号 }}</td>
          <td data-testid="disposition-row-fact">{{ row.来源事实表 }}</td>
          <td>{{ row.责任字段 }}</td>
          <td>{{ row.待处理原因 }}</td>
          <td :data-testid="`disposition-status-${row.id}`">{{ row.status }}</td>
          <td>
            <div
              v-if="row.处置决定"
              class="decision-text"
              :data-testid="`decision-text-${row.id}`"
            >
              {{ row.处置决定 }}
            </div>
            <input
              v-model="decisions[Number(row.id)]"
              class="decision-input"
              :data-testid="`disposition-decision-${row.id}`"
              data-test="decision-input"
              name="decision"
              placeholder="填写本退件的处置决定（不与同名字段其他退件共享）"
              @input="persistDraft(Number(row.id))"
            />
            <div
              v-for="item in conflictItemsFor(Number(row.id))"
              :key="`ci-${item.return_id}`"
              class="row-conflict bad-text"
              :data-testid="`row-conflict-${row.id}`"
            >
              {{ item.suggestion }}
            </div>
            <div v-if="rowError[Number(row.id)]" class="error-text" :data-testid="`row-error-${row.id}`">
              {{ rowError[Number(row.id)] }}
            </div>
          </td>
          <td data-testid="disposition-reviewer-cell">{{ row.审核人 || reviewer || '—' }}</td>
          <td class="row-actions disposition-actions">
            <button
              type="button"
              class="link"
              :data-testid="`action-${row.id}-提交处置`"
              data-test="disposition-submit"
              :disabled="submittingId === Number(row.id)"
              @click="submitRow(Number(row.id), false)"
            ><span :data-testid="`disposition-submit-${row.id}`">提交处置</span></button>
            <button
              type="button"
              class="link muted"
              :data-testid="`action-${row.id}-保存待提交`"
              @click="saveDraftRow(Number(row.id))"
            >
              保存待提交
            </button>
            <button
              type="button"
              class="link warn"
              :data-testid="`action-${row.id}-单独结案`"
              data-test="close-separate"
              @click="submitRow(Number(row.id), true)"
            >
              单独结案
            </button>
            <RouterLink
              class="link"
              :data-testid="`goto-field-${row.id}`"
              :to="fieldHref(row)"
            >
              定位责任字段
            </RouterLink>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-else-if="!loading" class="empty-state" data-testid="disposition-empty">
      当前定位下没有需要处置的有效退件。可回到「退化维度」页调整事实表、字段或待处理原因后重新定位。
    </p>
    <p v-else class="empty-state">处置清单加载中…</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  getLocator,
  previewLocate,
  saveDispositionDraft,
  submitDisposition,
} from '@/api/dispute'
import type { ConflictReport, LocatorDetail } from '@/api/dispute'
import { clearDraftLocal, loadDraft, locatorHref, readLocatorQuery, saveDraftLocal } from '@/domain/dispute'
import type { EntryRow } from '@/data/types'

const route = useRoute()

const locator = ref<LocatorDetail | null>(null)
const rows = ref<EntryRow[]>([])
const loading = ref(false)
const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const recoveredMessage = ref('')
const errorMessage = ref('')
const actionMessage = ref('')
const submittingId = ref<number | null>(null)
const reviewer = ref('值班审核人')
const decisions = reactive<Record<number, string>>({})
const rowError = reactive<Record<number, string>>({})

const scope = computed(() => readLocatorQuery(route.query))
const locatorCode = computed(() => scope.value.locatorRef || String(locator.value?.定位编号 ?? ''))
const scopeKey = computed(() =>
  locatorCode.value
    ? `loc:${locatorCode.value}`
    : `raw:${scope.value.factTable}|${scope.value.field}|${scope.value.reason}`,
)
const conflict = computed<ConflictReport | null>(() => locator.value?.conflict ?? null)

const degensHref = computed(() => locatorHref('/degenerate_dim', {
  locatorRef: locatorCode.value,
  factTable: scope.value.factTable,
  field: scope.value.field,
  reason: scope.value.reason,
}))

function fieldHref(row: EntryRow) {
  return locatorHref('/degenerate_dim', {
    locatorRef: locatorCode.value,
    factTable: String(row.来源事实表 ?? scope.value.factTable ?? ''),
    field: String(row.责任字段 ?? scope.value.field ?? ''),
    reason: String(row.待处理原因 ?? scope.value.reason ?? ''),
  })
}

function conflictItemsFor(returnId: number) {
  return conflict.value?.items?.filter((item) => item.return_id === returnId && item.level === 'conflict') ?? []
}

function hydrateDecisions(list: EntryRow[]) {
  for (const row of list) {
    const id = Number(row.id)
    const serverDecision = String(row.处置决定 ?? '')
    const localDraft = loadDraft(scopeKey.value, id)
    decisions[id] = serverDecision || localDraft || ''
  }
}

const CACHE_PREFIX = 'dfzr:locator-cache:'

function cacheKeyFor(q: ReturnType<typeof readLocatorQuery>): string {
  return q.locatorRef
    ? `${CACHE_PREFIX}${q.locatorRef}`
    : `${CACHE_PREFIX}raw:${q.factTable}|${q.field}|${q.reason}`
}

function writeCache(key: string, value: { locator: LocatorDetail | null; rows: EntryRow[] }) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify({ ...value, at: Date.now() }))
  } catch {
    /* 缓存不可用时忽略 */
  }
}

function readCache(key: string): { locator: LocatorDetail | null; rows: EntryRow[] } | null {
  try {
    const raw = window.sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as { locator: LocatorDetail | null; rows: EntryRow[] }) : null
  } catch {
    return null
  }
}

async function loadAllReturns() {
  const response = await fetch('/api/summary_return?page=1&size=200')
  const data = await response.json() as { items?: EntryRow[] }
  const all = data.items ?? []
  rows.value = all.filter((row) => ['待处理', '处置中', '待提交'].includes(String(row.status)))
  hydrateDecisions(rows.value)
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  const q = scope.value
  const cacheKey = cacheKeyFor(q)
  try {
    if (q.locatorRef) {
      const result = await getLocator(q.locatorRef)
      if (!result.ok || !result.locator) throw new Error(result.message || '定位不存在')
      locator.value = result.locator
      rows.value = (result.locator.returns as EntryRow[]) ?? []
      hydrateDecisions(rows.value)
      writeCache(cacheKey, { locator: locator.value, rows: rows.value })
    } else if (q.factTable && q.field) {
      locator.value = null
      const result = await previewLocate({
        fact_table: q.factTable, field: q.field, reason: q.reason || undefined,
      })
      rows.value = (result.items as EntryRow[]) ?? []
      hydrateDecisions(rows.value)
      writeCache(cacheKey, { locator: null, rows: rows.value })
    } else {
      locator.value = null
      await loadAllReturns()
      writeCache(cacheKey, { locator: null, rows: rows.value })
    }
  } catch (error) {
    // 断线刷新/重开时退回到最近一次定位快照缓存，保证行与未提交意见仍可见。
    const cached = readCache(cacheKey)
    if (cached && cached.rows.length) {
      locator.value = cached.locator
      rows.value = cached.rows
      hydrateDecisions(rows.value)
      errorMessage.value = '当前网络不可用，正在展示本机缓存的定位快照；恢复网络后会自动同步。'
    } else {
      errorMessage.value = error instanceof Error ? error.message : '处置清单读取失败'
    }
  } finally {
    loading.value = false
  }
}

function persistDraft(id: number) {
  saveDraftLocal(scopeKey.value, id, decisions[id] ?? '')
}

async function saveDraftRow(id: number) {
  rowError[id] = ''
  const text = decisions[id] ?? ''
  persistDraft(id)
  try {
    const result = await saveDispositionDraft({
      return_id: id,
      locator_id: locatorCode.value || undefined,
      fact_table: scope.value.factTable || undefined,
      field: scope.value.field || undefined,
      decision: text,
      reviewer: reviewer.value,
    })
    if (!result.ok) {
      rowError[id] = result.message
      return
    }
    actionMessage.value = `退件 ${id} 的待提交处置已保存，断线或重开书签后仍可继续。`
    await reload()
  } catch (error) {
    // 离线时本地草稿已暂存，恢复网络后可再次保存。
    rowError[id] = error instanceof Error ? `${error.message}（意见已暂存本机）` : '保存失败'
  }
}

async function submitRow(id: number, separate: boolean) {
  rowError[id] = ''
  actionMessage.value = ''
  submittingId.value = id
  const text = (decisions[id] ?? '').trim()
  if (!text) {
    rowError[id] = '请先填写处置决定再提交。'
    submittingId.value = null
    return
  }
  try {
    const result = await submitDisposition({
      return_id: id,
      // 单独结案是“回原退件”的路径：不再借用旧定位轮次，但仍带事实表归属做校验。
      locator_id: separate ? undefined : (locatorCode.value || undefined),
      fact_table: scope.value.factTable || rows.value.find((r) => Number(r.id) === id)?.来源事实表,
      field: scope.value.field || rows.value.find((r) => Number(r.id) === id)?.责任字段,
      decision: text,
      reviewer: reviewer.value,
      separate,
    })
    if (!result.ok) {
      rowError[id] = result.message
      if (result.conflict) {
        errorMessage.value = result.message
      }
      return
    }
    clearDraftLocal(scopeKey.value, id)
    actionMessage.value = result.message
    await reload()
  } catch (error) {
    rowError[id] = error instanceof Error ? error.message : '提交失败'
  } finally {
    submittingId.value = null
  }
}

function handleOnline() {
  online.value = true
  recoveredMessage.value = '网络已恢复，正在重新连接并同步处置清单…'
  void reload().then(() => {
    recoveredMessage.value = '断线恢复完成：清单已与服务端同步，本机暂存意见仍保留在输入框。'
    window.setTimeout(() => { recoveredMessage.value = '' }, 6000)
  })
}
function handleOffline() {
  online.value = false
}

onMounted(() => {
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
  void reload()
})
onBeforeUnmount(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
})
watch(() => route.fullPath, () => { void reload() })
</script>

<style scoped>
.disposition-panel { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; margin: 12px 0 16px; }
.disp-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.disp-head h3 { margin: 0 0 4px; font-size: 16px; }
.disp-sub { color: var(--muted); font-size: 12.5px; margin: 0; line-height: 1.6; }
.disp-head-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn.small { padding: 4px 10px; font-size: 12px; text-decoration: none; display: inline-block; }
.btn.muted { color: var(--muted); }
.btn.warn { color: #b54708; }
.banner { border-radius: 8px; padding: 10px 12px; font-size: 13px; margin: 10px 0; line-height: 1.6; }
.banner.conflict { background: #fffaeb; border: 1px solid #fedf89; color: #93370d; }
.banner.compatible { background: #ecfdf3; border: 1px solid #abefc6; color: #067647; }
.banner.offline { background: #fef3f2; border: 1px solid #fecdca; color: #b42318; }
.banner.recovered { background: #eff8ff; border: 1px solid #b2ddff; color: #175cd3; }
.conflict-items { margin: 6px 0 0; padding-left: 18px; }
.conflict-suggestion { color: #7a2e0e; }
.ok-text { color: #067647; }
.bad-text { color: #b42318; }
.notice-text { color: #175cd3; font-size: 13px; }
.disposition-table { margin-top: 8px; }
.decision-text { font-size: 12.5px; background: #f2f4f7; border-radius: 6px; padding: 4px 8px; margin-bottom: 6px; }
.decision-input, .reviewer-input { width: 100%; min-width: 180px; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
.reviewer-field { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--muted); }
.reviewer-input-head { padding: 5px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; min-width: 130px; }
.disposition-actions { flex-wrap: wrap; gap: 8px; min-width: 170px; }
.row-conflict { font-size: 12px; margin-top: 4px; }
</style>
