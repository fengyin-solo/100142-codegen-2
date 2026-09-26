<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">市政道路桥梁养护平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向市政道路桥梁的巡查、病害登记、养护施工、检测评定与设施档案的一体化养护管理后台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "道路设施", path: "/road" }, { label: "桥梁档案", path: "/bridge" }, { label: "隧道设施", path: "/tunnel" }, { label: "巡查任务", path: "/patrol" }, { label: "病害登记", path: "/disease" }, { label: "技术评定", path: "/assess" }, { label: "养护计划", path: "/plan" }, { label: "养护施工", path: "/work" }, { label: "竣工验收", path: "/accept" }, { label: "坑槽修补", path: "/pothole" }, { label: "裂缝处置", path: "/crack" }, { label: "除雪防滑", path: "/snow" }, { label: "排水设施", path: "/drain" }, { label: "照明设施", path: "/light" }, { label: "养护材料", path: "/material" }, { label: "养护机械", path: "/equip" }, { label: "养护资金", path: "/fund" }, { label: "公众诉求", path: "/complaint" }, { label: "设施档案", path: "/archive" }]
</script>
