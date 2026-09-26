<template>
  <section class="page" data-module="snow">
    <header class="page-head">
      <div>
        <h2>冬季除雪防滑</h2>
        <p class="page-desc">
          按责任路段登记除雪作业、班组与融雪剂用量；每公里用量低于 {{ caliber.lower }} 或高于
          {{ caliber.upper }} 吨提示用量异常，路面未结冰派工按重复派工拦截。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showForm = !showForm">
          {{ showForm ? '收起登记表单' : '登记除雪作业' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出除雪作业清单</button>
      </div>
    </header>

    <form v-if="showForm" class="create-panel" @submit.prevent="submitCreate">
      <label v-for="field in formFields" :key="field.key" class="filter-item">
        <span>{{ field.key }}<em v-if="field.required" class="required-mark">*</em></span>
        <input v-model="form[field.key]" :placeholder="field.placeholder" />
      </label>
      <label class="filter-item">
        <span>路面状态<em class="required-mark">*</em></span>
        <select v-model="form['路面状态']">
          <option value="已结冰">已结冰</option>
          <option value="未结冰">未结冰</option>
        </select>
      </label>
      <label class="filter-item">
        <span>作业日期</span>
        <input v-model="form['作业日期']" type="date" />
      </label>
      <div class="create-actions">
        <button class="btn primary" type="submit">提交登记</button>
        <button class="btn ghost" type="button" @click="resetForm">清空表单</button>
      </div>
    </form>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>作业单号</span>
        <input v-model="filters.keyword" placeholder="按作业单号检索" />
      </label>
      <label class="filter-item">
        <span>作业状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
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
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无除雪作业数据，可先登记除雪作业</td>
        </tr>
      </tbody>
    </table>

    <section class="anomaly-panels">
      <article class="anomaly-panel">
        <h3>班组用量异常（每公里 {{ caliber.lower }}–{{ caliber.upper }} 吨之外）</h3>
        <table class="data-table">
          <thead>
            <tr><th>作业单号</th><th>责任路段</th><th>作业班组</th><th>每公里用量</th><th>异常说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in usageAbnormal" :key="`u-${String(row.id)}`">
              <td>{{ row['作业单号'] }}</td>
              <td>{{ row['责任路段'] }}</td>
              <td>{{ row['作业班组'] }}</td>
              <td>{{ row['每公里用量'] }}</td>
              <td>{{ row['异常说明'] }}</td>
            </tr>
            <tr v-if="!usageAbnormal.length">
              <td colspan="5" class="empty-state">暂无班组用量异常</td>
            </tr>
          </tbody>
        </table>
      </article>
      <article class="anomaly-panel">
        <h3>关联作业对不上（关联巡查单不存在）</h3>
        <table class="data-table">
          <thead>
            <tr><th>作业单号</th><th>责任路段</th><th>作业班组</th><th>关联巡查单</th><th>异常说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in linkMismatch" :key="`l-${String(row.id)}`">
              <td>{{ row['作业单号'] }}</td>
              <td>{{ row['责任路段'] }}</td>
              <td>{{ row['作业班组'] }}</td>
              <td>{{ row['关联巡查单'] }}</td>
              <td>{{ row['异常说明'] }}</td>
            </tr>
            <tr v-if="!linkMismatch.length">
              <td colspan="5" class="empty-state">暂无关联作业对不上</td>
            </tr>
          </tbody>
        </table>
      </article>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条除雪作业记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/snow'
const columns = ["作业单号", "责任路段", "作业班组", "作业里程", "融雪剂用量", "每公里用量", "路面状态", "作业状态", "异常说明"]
const actions = ["完成作业", "中断作业", "恢复作业"]
const statuses = ["作业中", "已完成", "已中断", "已拦截"]
const formFields = [
  { key: '作业单号', required: true, placeholder: '如 SNOW-0005' },
  { key: '责任路段', required: true, placeholder: '如 滨江大道 K0+000—K2+000' },
  { key: '作业班组', required: true, placeholder: '如 除雪一班' },
  { key: '作业里程', required: true, placeholder: '公里，如 2' },
  { key: '融雪剂用量', required: true, placeholder: '吨，如 0.6' },
  { key: '关联巡查单', required: false, placeholder: '选填，如 PATR-0002' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref({ keyword: '', status: '' })
const showForm = ref(false)
const form = ref<Record<string, string>>({ '路面状态': '已结冰' })
const usageAbnormal = ref<Row[]>([])
const linkMismatch = ref<Row[]>([])
const caliber = ref({ lower: 0.1, upper: 0.8 })

const stats = computed(() => [
  { label: '进行中作业', value: rows.value.filter((row) => row['作业状态'] === '作业中').length },
  { label: '用量异常', value: usageAbnormal.value.length },
  { label: '重复派工已拦截', value: rows.value.filter((row) => row['作业状态'] === '已拦截').length },
  { label: '关联作业对不上', value: linkMismatch.value.length },
])

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function resetForm() {
  form.value = { '路面状态': '已结冰' }
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function readMessage(response: Response): Promise<{ ok: boolean; message: string }> {
  const payload = (await response.json()) as { ok?: boolean; message?: string }
  return { ok: Boolean(payload.ok), message: payload.message ?? '操作已完成' }
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form.value } }),
    })
    const result = await readMessage(response)
    if (result.ok) {
      noticeMessage.value = result.message
      resetForm()
      showForm.value = false
    } else {
      errorMessage.value = result.message
    }
    // 被拦截的重复派工也会记入列表，无论放行与否都刷新。
    await Promise.all([reload(), reloadAnomalies()])
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
    const result = await readMessage(response)
    if (result.ok) {
      noticeMessage.value = result.message
    } else {
      errorMessage.value = result.message
    }
    await Promise.all([reload(), reloadAnomalies()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '除雪作业操作失败'
  }
}

async function reload() {
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.status) query.set('status', filters.value.status)
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('除雪作业列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '除雪作业列表读取失败'
  }
}

async function reloadAnomalies() {
  try {
    const response = await request(`${ENDPOINT}/anomalies`)
    if (!response.ok) {
      throw new Error('异常清单读取失败')
    }
    const payload = await response.json()
    usageAbnormal.value = payload.usage_abnormal ?? []
    linkMismatch.value = payload.link_mismatch ?? []
    if (payload.caliber) {
      caliber.value = { lower: payload.caliber.lower, upper: payload.caliber.upper }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '异常清单读取失败'
  }
}

onMounted(() => {
  void reload()
  void reloadAnomalies()
})
</script>

<style scoped>
.create-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.create-panel input,
.filter-bar select {
  min-width: 180px;
}
.create-actions {
  display: flex;
  gap: 8px;
}
.required-mark {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.anomaly-panels {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}
.anomaly-panel {
  flex: 1;
  min-width: 0;
}
.anomaly-panel h3 {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 6px;
}
.notice-text {
  color: #067647;
}
</style>
