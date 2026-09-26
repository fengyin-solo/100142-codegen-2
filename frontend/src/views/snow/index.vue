<template>
  <section class="page" data-module="snow">
    <header class="page-head">
      <div>
        <h2>冬季除雪防滑</h2>
        <p class="page-desc">按责任路段登记除雪作业，围绕作业单号、责任路段、作业班组、融雪剂用量做登记、拦截与异常清单。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">登记除雪作业</button>
        <button class="btn" type="button" @click="exportRows">导出除雪作业清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="create-panel" @submit.prevent="submitCreate">
      <div class="create-grid">
        <label v-for="field in createFields" :key="field.key" class="filter-item">
          <span>{{ field.label }}<em v-if="field.required" class="required-mark">*</em></span>
          <select v-if="field.key === '路面状况'" v-model="createForm[field.key]">
            <option v-for="option in roadConditions" :key="option" :value="option">{{ option }}</option>
          </select>
          <input v-else v-model="createForm[field.key]" :placeholder="field.placeholder" />
        </label>
      </div>
      <div class="create-actions">
        <button class="btn primary" type="submit">提交登记</button>
        <button class="btn ghost" type="button" @click="showCreate = false">收起</button>
        <span class="page-desc">每公里融雪剂用量口径：{{ perKmMin }}-{{ perKmMax }} 吨/公里，超出即提示用量异常</span>
      </div>
    </form>

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
          <th>状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            {{ row.status }}
            <span v-if="row.abnormal" class="abnormal-mark" :title="String(row.拦截原因 ?? '用量或关联异常')">异常</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无除雪作业数据，可先登记除雪作业</td>
        </tr>
      </tbody>
    </table>

    <div class="exception-panel">
      <article class="exception-card">
        <h3>{{ exceptions.crew_usage.label }}（{{ exceptions.crew_usage.items.length }}）</h3>
        <p class="page-desc">班组单次用量合理范围 {{ exceptions.crew_usage.min }}-{{ exceptions.crew_usage.max }} 吨，超出即在此单独列出</p>
        <ul class="exception-list">
          <li v-for="row in exceptions.crew_usage.items" :key="`crew-${row.id}`">
            {{ row.作业单号 }} · {{ row.责任路段 }} · {{ row.作业班组 }} · 用量 {{ row.融雪剂用量 }} 吨
          </li>
          <li v-if="!exceptions.crew_usage.items.length" class="empty-state">暂无班组用量异常</li>
        </ul>
      </article>
      <article class="exception-card">
        <h3>{{ exceptions.patrol_mismatch.label }}（{{ exceptions.patrol_mismatch.items.length }}）</h3>
        <p class="page-desc">关联巡查单在巡查任务中查不到的除雪作业</p>
        <ul class="exception-list">
          <li v-for="row in exceptions.patrol_mismatch.items" :key="`patrol-${row.id}`">
            {{ row.作业单号 }} · {{ row.责任路段 }} · 关联巡查单 {{ row.关联巡查单 }}
          </li>
          <li v-if="!exceptions.patrol_mismatch.items.length" class="empty-state">暂无关联异常</li>
        </ul>
      </article>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条除雪作业记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null> & { id: number | string }

type ExceptionGroup = { label: string; min?: number; max?: number; items: Row[] }

const ENDPOINT = '/api/snow'
const columns = ["作业单号", "责任路段", "作业班组", "关联巡查单", "作业里程", "融雪剂用量", "路面状况", "作业日期"]
const actions = ["派工作业", "完成作业", "作废作业"]
const roadConditions = ["结冰", "积雪", "未结冰"]
const perKmMin = 0.1
const perKmMax = 0.5
const createFields = [
  { key: "作业单号", label: "作业单号", required: true, placeholder: "如 SNOW-0008" },
  { key: "责任路段", label: "责任路段", required: true, placeholder: "如 北环高架 K0+000-K3+500" },
  { key: "作业班组", label: "作业班组", required: true, placeholder: "如 除雪一班" },
  { key: "关联巡查单", label: "关联巡查单", required: false, placeholder: "如 PATR-0001，可空" },
  { key: "作业里程", label: "作业里程（公里）", required: true, placeholder: "如 3.5" },
  { key: "融雪剂用量", label: "融雪剂用量（吨）", required: true, placeholder: "如 1.2" },
  { key: "路面状况", label: "路面状况", required: true, placeholder: "" },
  { key: "作业日期", label: "作业日期", required: false, placeholder: "如 2026-01-15" },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreate = ref(false)
const createForm = reactive<Record<string, string>>({ 路面状况: roadConditions[0] })
const stats = ref([
  { label: '待派工作业', value: 0 },
  { label: '作业中路段', value: 0 },
  { label: '异常提示', value: 0 },
  { label: '已拦截', value: 0 },
])
const exceptions = ref<{ crew_usage: ExceptionGroup; patrol_mismatch: ExceptionGroup }>({
  crew_usage: { label: '班组用量超出合理范围', items: [] },
  patrol_mismatch: { label: '关联作业对不上', items: [] },
})

function refreshStats() {
  const list = rows.value
  stats.value = [
    { label: '待派工作业', value: list.filter((row) => row.status === '待派工').length },
    { label: '作业中路段', value: list.filter((row) => row.status === '作业中').length },
    { label: '异常提示', value: list.filter((row) => row.abnormal).length },
    { label: '已拦截', value: list.filter((row) => row.status === '已拦截').length },
  ]
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function readMessage(response: Response, fallback: string): Promise<{ ok: boolean; message: string }> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    return { ok: false, message: payload?.detail ?? fallback }
  }
  return { ok: Boolean(payload?.ok ?? true), message: payload?.message ?? fallback }
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const result = await readMessage(response, '除雪作业登记未生效，请稍后重试')
    if (result.ok) {
      noticeMessage.value = result.message
    } else {
      errorMessage.value = result.message
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '除雪作业登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = await readMessage(response, '除雪作业动作未生效，请稍后重试')
    if (result.ok) {
      noticeMessage.value = result.message
    } else {
      errorMessage.value = result.message
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '除雪作业操作失败'
  }
}

async function reload() {
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [listResponse, exceptionResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/exceptions`),
    ])
    if (!listResponse.ok) {
      throw new Error('除雪作业列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    refreshStats()
    if (exceptionResponse.ok) {
      exceptions.value = await exceptionResponse.json()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '除雪作业列表读取失败'
  }
}

onMounted(reload)
</script>
