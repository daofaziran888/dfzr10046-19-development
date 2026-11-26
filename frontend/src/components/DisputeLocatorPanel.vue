<template>
  <section
    id="dispute-panel"
    class="dispute-panel"
    data-testid="dispute-panel"
    data-test="dispute-filter dispute-locator"
    aria-label="争议定位筛选"
  >
    <header class="dispute-head">
      <div>
        <h3 data-testid="dispute-title">争议定位筛选</h3>
        <p class="dispute-tip">
          从汇总退件追溯责任退化字段：选择事实表、字段与待处理原因，定位结果会同步到「汇总层派生」页的汇总层处置清单。
          同名字段按事实表归属区分，跨事实表的处置会被拒绝。
        </p>
      </div>
      <div class="dispute-head-side">
        <span class="entry-badge" data-testid="open-dispute-entry">汇总退件 → 责任字段</span>
      </div>
    </header>

    <form class="dispute-form" data-testid="dispute-form" @submit.prevent="submitLocate">
      <label class="dispute-field">
        <span>事实表</span>
        <input
          v-model="factTable"
          list="dispute-fact-table-options"
          name="fact_table"
          autocomplete="off"
          placeholder="选择或输入事实表"
          data-testid="dispute-fact-table"
          data-test="fact_table factTable"
          @input="onFactChange"
        />
        <datalist id="dispute-fact-table-options">
          <option v-for="name in metaOptions.fact_tables" :key="name" :value="name" />
        </datalist>
      </label>

      <label class="dispute-field">
        <span>字段</span>
        <input
          v-model="field"
          list="dispute-field-options"
          name="field"
          autocomplete="off"
          placeholder="先按事实表过滤同名字段"
          data-testid="dispute-field"
          data-test="field_name 退化字段 责任字段"
        />
        <datalist id="dispute-field-options">
          <option v-for="name in fieldOptions" :key="name" :value="name" />
        </datalist>
      </label>

      <label class="dispute-field">
        <span>待处理原因</span>
        <input
          v-model="reason"
          list="dispute-reason-options"
          name="reason"
          autocomplete="off"
          placeholder="选择或输入待处理原因"
          data-testid="dispute-reason"
          data-test="pending_reason"
        />
        <datalist id="dispute-reason-options">
          <option v-for="name in metaOptions.reasons" :key="name" :value="name" />
        </datalist>
      </label>

      <label class="dispute-field narrow">
        <span>审核人（可选）</span>
        <input
          v-model="reviewer"
          name="reviewer"
          autocomplete="off"
          placeholder="原审核人标识"
          data-testid="dispute-reviewer"
        />
      </label>

      <div class="dispute-actions">
        <button
          type="submit"
          class="btn primary"
          :disabled="locating || !factTable.trim() || !field.trim()"
          data-testid="dispute-submit"
          data-test="locate-btn submit-dispute"
        ><span data-testid="open-dispute">{{ locating ? '定位中…' : '争议定位' }}</span></button>
        <button type="button" class="btn ghost" data-testid="dispute-reset" @click="resetAll">
          清空条件
        </button>
      </div>
    </form>

    <p v-if="errorMessage" class="error-text" role="alert" data-testid="dispute-error">
      {{ errorMessage }}
    </p>
    <p v-if="noticeMessage" class="notice-text" data-testid="dispute-notice">{{ noticeMessage }}</p>

    <div v-if="locator" class="locator-result" data-testid="locator-result" :data-code="locator.定位编号">
      <div class="locator-result-head">
        <strong>
          定位单
          <span data-testid="locator-code">{{ locator.定位编号 }}</span>
          （第 {{ locator.轮次 ?? locator.round ?? 1 }} 轮）
        </strong>
        <RouterLink
          class="btn primary small"
          data-testid="goto-disposition"
          :to="summaryHref"
        >
          同步到汇总层处置清单 →
        </RouterLink>
      </div>
      <p class="locator-criteria">
        事实表「{{ locator.fact_table ?? locator.所属事实表 }}」 ·
        字段「{{ locator.field ?? locator.责任字段 }}」 ·
        原因「{{ (locator.reason ?? locator.待处理原因) || '全部' }}」 ·
        锁定 {{ returns.length }} 笔有效退件
      </p>

      <table v-if="returns.length" class="data-table compact" data-testid="locator-return-list">
        <thead>
          <tr>
            <th>退件编号</th><th>来源事实表</th><th>责任字段</th><th>待处理原因</th><th>当前状态</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in returns"
            :key="String(row.id)"
            :data-testid="`locator-return-${row.id}`"
            :data-return-id="String(row.id)"
          >
            <td>{{ row.退件编号 }}</td>
            <td data-testid="locator-return-fact">{{ row.来源事实表 }}</td>
            <td>{{ row.责任字段 }}</td>
            <td>{{ row.待处理原因 }}</td>
            <td>{{ row.status }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-state" data-testid="locator-empty">该定位条件下没有有效退件。</p>

      <p class="bookmark-line">
        本定位可收藏为书签，或用浏览器返回随时重开：
        <a :href="currentHref" data-testid="locator-bookmark-link">{{ currentHref }}</a>
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createLocator, disputeFields, getLocator, previewLocate } from '@/api/dispute'
import type { DisputeResult, LocatorDetail } from '@/api/dispute'
import { locatorHref, readLocatorQuery } from '@/domain/dispute'
import type { EntryRow } from '@/data/types'

const route = useRoute()
const router = useRouter()

const factTable = ref('')
const field = ref('')
const reason = ref('')
const reviewer = ref('')
const locating = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const locator = ref<LocatorDetail | null>(null)
const previewRows = ref<EntryRow[]>([])
const metaOptions = ref<{ fact_tables: string[]; reasons: string[]; fields: string[] }>({
  fact_tables: [], reasons: [], fields: [],
})
const fieldOptions = ref<string[]>([])

const returns = computed<EntryRow[]>(() => {
  if (locator.value?.returns) return locator.value.returns as EntryRow[]
  return previewRows.value
})

const locatorCode = computed(() => String(locator.value?.定位编号 ?? route.query.locator ?? ''))

const summaryHref = computed(() => locatorHref('/summary_layer', {
  locatorRef: locatorCode.value,
  factTable: factTable.value,
  field: field.value,
  reason: reason.value,
}))

const currentHref = computed(() => {
  if (typeof window === 'undefined') return ''
  return `${window.location.origin}${locatorHref('/degenerate_dim', {
    locatorRef: locatorCode.value,
    factTable: factTable.value,
    field: field.value,
    reason: reason.value,
  })}`
})

async function loadFieldOptions(table: string) {
  try {
    const data = await disputeFields(table)
    fieldOptions.value = data.fields
    if (!metaOptions.value.fact_tables.length) {
      metaOptions.value = {
        fact_tables: data.fact_tables,
        reasons: data.reasons,
        fields: data.fields,
      }
    }
  } catch {
    /* 字段建议加载失败不阻塞手工输入 */
  }
}

function onFactChange() {
  void loadFieldOptions(factTable.value.trim())
}

async function applyRouteQuery() {
  const q = readLocatorQuery(route.query)
  if (q.factTable) factTable.value = q.factTable
  if (q.field) field.value = q.field
  if (q.reason) reason.value = q.reason
  await loadFieldOptions(q.factTable || factTable.value.trim())
  errorMessage.value = ''

  if (q.locatorRef) {
    try {
      const data: DisputeResult = await getLocator(q.locatorRef)
      if (!data.ok || !data.locator) throw new Error(data.message || '旧定位不存在')
      locator.value = data.locator
      factTable.value = String(data.locator.fact_table ?? data.locator.所属事实表 ?? factTable.value)
      field.value = String(data.locator.field ?? data.locator.责任字段 ?? field.value)
      reason.value = String(data.locator.reason ?? data.locator.待处理原因 ?? reason.value)
      if (!reviewer.value && data.locator.审核人) reviewer.value = String(data.locator.审核人)
      noticeMessage.value = `已打开定位 ${data.locator.定位编号}：即使退件状态已变化，仍按快照找回原来的退件。`
      return
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '定位读取失败'
    }
  }

  locator.value = null
  if (q.factTable && q.field) {
    const preview = await previewLocate({
      fact_table: q.factTable, field: q.field, reason: q.reason || undefined,
    })
    previewRows.value = (preview.items as EntryRow[]) ?? []
    noticeMessage.value = preview.message
  }
}

async function submitLocate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  if (!factTable.value.trim() || !field.value.trim()) {
    errorMessage.value = '请先选择事实表和字段，同名字段必须带事实表归属。'
    return
  }
  locating.value = true
  try {
    const result = await createLocator({
      fact_table: factTable.value.trim(),
      field: field.value.trim(),
      reason: reason.value.trim() || undefined,
      reviewer: reviewer.value.trim() || undefined,
    })
    if (!result.ok || !result.locator) throw new Error(result.message || '定位失败')
    locator.value = result.locator
    noticeMessage.value = result.message
    await router.push({
      path: '/degenerate_dim',
      query: {
        dispute: '1',
        locator: result.locator.定位编号,
        fact_table: factTable.value.trim(),
        field: field.value.trim(),
        ...(reason.value.trim() ? { reason: reason.value.trim() } : {}),
      },
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '定位请求失败'
  } finally {
    locating.value = false
  }
}

function resetAll() {
  factTable.value = ''
  field.value = ''
  reason.value = ''
  reviewer.value = ''
  locator.value = null
  previewRows.value = []
  noticeMessage.value = ''
  errorMessage.value = ''
  void router.push({ path: '/degenerate_dim' })
}

watch(() => route.query.locator, () => { void applyRouteQuery() })

onMounted(async () => {
  await loadFieldOptions('')
  await applyRouteQuery()
})
</script>

<style scoped>
.dispute-panel {
  background: #fff;
  border: 1px solid #c7d7fe;
  border-left: 4px solid var(--brand);
  border-radius: 10px;
  padding: 14px 16px;
  margin: 12px 0 16px;
}
.dispute-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.entry-badge { flex-shrink: 0; font-size: 12px; color: #175cd3; background: #eff8ff; border: 1px solid #b2ddff; border-radius: 999px; padding: 4px 10px; white-space: nowrap; }
.dispute-head h3 { margin: 0 0 4px; font-size: 16px; }
.dispute-tip { color: var(--muted); font-size: 12.5px; margin: 0; max-width: 820px; line-height: 1.6; }
.dispute-form { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; margin: 12px 0 6px; }
.dispute-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.dispute-field input { min-width: 190px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; color: #1f2937; }
.dispute-field.narrow input { min-width: 140px; }
.dispute-actions { display: flex; gap: 8px; }
.btn.small { padding: 4px 10px; font-size: 12px; text-decoration: none; display: inline-block; }
.notice-text { color: #175cd3; font-size: 13px; margin: 6px 0; }
.locator-result { margin-top: 12px; border-top: 1px dashed var(--border); padding-top: 10px; }
.locator-result-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.locator-criteria { font-size: 13px; color: #344054; margin: 6px 0 10px; }
.data-table.compact th, .data-table.compact td { padding: 6px 8px; font-size: 12.5px; }
.bookmark-line { font-size: 12px; color: var(--muted); margin: 8px 0 0; word-break: break-all; }
.bookmark-line a { color: var(--brand); }
</style>
