<template>
  <section class="page" data-module="dispute_center" data-testid="dispute-center">
    <header class="page-head">
      <div>
        <h2>争议定位工作台</h2>
        <p class="page-desc">
          值班员按事实表、字段与待处理原因定位汇总退件的责任退化字段；定位单可收藏、可往返，
          处置决定按“事实表 + 字段 + 退件 + 轮次”隔离，不同事实表的同名字段互不串单。
        </p>
      </div>
    </header>
    <DisputeLocatorPanel />
    <DispositionListPanel />
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DisputeLocatorPanel from '@/components/DisputeLocatorPanel.vue'
import DispositionListPanel from '@/components/DispositionListPanel.vue'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  // 支持 /dispute/DL-0001 这类路径式书签，归一到 query 形式，保证两个面板状态一致。
  const ref = route.params.locatorRef
  if (typeof ref === 'string' && ref && !route.query.locator) {
    void router.replace({ path: '/dispute', query: { ...route.query, locator: ref } })
  }
})
</script>
