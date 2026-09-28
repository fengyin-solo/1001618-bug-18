<template>
  <section class="page" data-module="flight">
    <header class="page-head">
      <div>
        <h2>航班计划管理</h2>
        <p class="page-desc">维护航班计划，围绕航班号、执行日期、机型、起降性质做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记航班计划</button>
        <button class="btn" type="button" @click="exportRows">导出航班计划清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="busyKey === actionKey(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无航班计划数据，可先登记航班计划</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条航班计划记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/flight'
const columns = ["航班号", "执行日期", "机型", "起降性质", "计划时刻", "预计时刻", "保障等级", "航班状态"]
const actions = ["确认计划", "开始保障", "结束保障"]
const statuses = ["待确认", "已确认", "保障中", "已结束"]

const stats = reactive([
  { label: "今日航班", value: 0 },
  { label: "待处理航班", value: 0 },
  { label: "保障中航班", value: 0 },
  { label: "已结束航班", value: 0 },
])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const busyKey = ref('')

function actionKey(action: string, row: Row) {
  return `${String(row.id)}:${action}`
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '航班计划登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (busyKey.value) {
    return
  }
  errorMessage.value = ''
  successMessage.value = ''
  busyKey.value = actionKey(action, row)
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = (await response.json().catch(() => null)) as
      | { ok?: boolean; message?: string }
      | null
    if (!response.ok || !payload || payload.ok === false) {
      throw new Error(payload?.message || '航班计划动作未生效，请稍后重试')
    }
    successMessage.value = payload.message || `航班计划已${action}`
    await Promise.all([reload(), refreshStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '航班计划操作失败'
  } finally {
    busyKey.value = ''
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('航班计划列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '航班计划列表读取失败'
  }
}

async function refreshStats() {
  // 统计口径不受列表筛选影响，取全量后按内部状态汇总待处理/保障中/已结束数量
  try {
    const response = await request(`${ENDPOINT}?page=1&size=200`)
    if (!response.ok) {
      return
    }
    const payload = await response.json()
    const allRows = (payload.items ?? []) as Row[]
    stats[0].value = Number(payload.total ?? allRows.length)
    stats[1].value = allRows.filter((row) => row.status !== '已结束').length
    stats[2].value = allRows.filter((row) => row.status === '保障中').length
    stats[3].value = allRows.filter((row) => row.status === '已结束').length
  } catch {
    // 统计刷新失败不阻断列表操作，保留上一次的数字
  }
}

onMounted(async () => {
  await Promise.all([reload(), refreshStats()])
})
</script>
