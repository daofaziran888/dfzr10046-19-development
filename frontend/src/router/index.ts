import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'
import DisputeCenterView from '@/views/DisputeCenterView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/dispute', name: 'dispute-center', component: DisputeCenterView },
    { path: '/dispute/:locatorRef', name: 'dispute-center-ref', component: DisputeCenterView },
    // 常见命名的争议定位路径别名，书签/浏览器返回均可落到同一工作台。
    { path: '/dispute-locator', component: DisputeCenterView },
    { path: '/dispute-locator/:locatorRef', component: DisputeCenterView },
    { path: '/dispute-locators', component: DisputeCenterView },
    { path: '/dispute-location', component: DisputeCenterView },
    { path: '/dispute-location/:locatorRef', component: DisputeCenterView },
    { path: '/dispute-center', component: DisputeCenterView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
