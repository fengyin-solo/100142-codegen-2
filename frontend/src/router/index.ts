import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Road = () => import('@/views/road/index.vue')
const Bridge = () => import('@/views/bridge/index.vue')
const Tunnel = () => import('@/views/tunnel/index.vue')
const Patrol = () => import('@/views/patrol/index.vue')
const Disease = () => import('@/views/disease/index.vue')
const Assess = () => import('@/views/assess/index.vue')
const Plan = () => import('@/views/plan/index.vue')
const Work = () => import('@/views/work/index.vue')
const Accept = () => import('@/views/accept/index.vue')
const Pothole = () => import('@/views/pothole/index.vue')
const Crack = () => import('@/views/crack/index.vue')
const Drain = () => import('@/views/drain/index.vue')
const Light = () => import('@/views/light/index.vue')
const Material = () => import('@/views/material/index.vue')
const Equip = () => import('@/views/equip/index.vue')
const Fund = () => import('@/views/fund/index.vue')
const Complaint = () => import('@/views/complaint/index.vue')
const Archive = () => import('@/views/archive/index.vue')
const Snow = () => import('@/views/snow/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/road', name: 'road', component: Road },
    { path: '/bridge', name: 'bridge', component: Bridge },
    { path: '/tunnel', name: 'tunnel', component: Tunnel },
    { path: '/patrol', name: 'patrol', component: Patrol },
    { path: '/disease', name: 'disease', component: Disease },
    { path: '/assess', name: 'assess', component: Assess },
    { path: '/plan', name: 'plan', component: Plan },
    { path: '/work', name: 'work', component: Work },
    { path: '/accept', name: 'accept', component: Accept },
    { path: '/pothole', name: 'pothole', component: Pothole },
    { path: '/crack', name: 'crack', component: Crack },
    { path: '/drain', name: 'drain', component: Drain },
    { path: '/light', name: 'light', component: Light },
    { path: '/material', name: 'material', component: Material },
    { path: '/equip', name: 'equip', component: Equip },
    { path: '/fund', name: 'fund', component: Fund },
    { path: '/complaint', name: 'complaint', component: Complaint },
    { path: '/archive', name: 'archive', component: Archive },
    { path: '/snow', name: 'snow', component: Snow },
  ],
})

export default router
