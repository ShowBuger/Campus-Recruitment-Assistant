<script setup>
defineProps({ avatarKey: { type: String, default: 'indigo' }, avatarUrl: { type: String, default: '' }, label: { type: String, default: '' } })
</script>

<template>
  <span class="user-avatar" :class="`avatar-${avatarKey}`" role="img" :aria-label="label ? `${label}的头像` : '用户头像'">
    <img v-if="avatarUrl" :src="`${avatarUrl}?v=${encodeURIComponent(avatarUrl)}`" alt="">
    <svg v-else-if="avatarKey === 'indigo'" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="25" r="13"/><path d="M13 59c2-13 10-20 19-20s17 7 19 20"/><path class="accent" d="m20 24 5-15 8 7 10-5 2 14-8-5-8 5Z"/></svg>
    <svg v-else-if="avatarKey === 'sunset'" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="24" r="13"/><path d="M11 59c3-13 11-19 21-19s18 6 21 19"/><path class="accent" d="M17 24c0-15 9-19 15-19 12 0 17 10 15 25-4-3-7-9-8-14-5 7-12 11-22 8Z"/></svg>
    <svg v-else-if="avatarKey === 'forest'" viewBox="0 0 64 64" aria-hidden="true"><path class="accent" d="M32 4 6 44h15l-8 14h38l-8-14h15Z"/><circle cx="32" cy="27" r="10"/><path d="M17 60c2-14 8-21 15-21s13 7 15 21"/></svg>
    <svg v-else-if="avatarKey === 'ocean'" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="26" r="12"/><path d="M13 59c3-14 10-20 19-20s16 6 19 20"/><path class="accent" d="M3 15c8 7 16 7 24 0s16-7 24 0 10 5 13 2V4H0v13c1 0 2-1 3-2Z"/></svg>
    <svg v-else-if="avatarKey === 'cherry'" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="27" r="12"/><path d="M13 59c3-13 10-19 19-19s16 6 19 19"/><path class="accent" d="M18 8c7 0 12 4 14 9 2-5 7-9 14-9-1 8-6 12-14 12S19 16 18 8Z"/></svg>
    <svg v-else-if="avatarKey === 'mono'" viewBox="0 0 64 64" aria-hidden="true"><rect class="accent" x="10" y="11" width="44" height="40" rx="9"/><circle cx="25" cy="29" r="4"/><circle cx="39" cy="29" r="4"/><path d="M23 40h18M32 11V4M27 4h10"/></svg>
    <svg v-else-if="avatarKey === 'cosmos'" viewBox="0 0 64 64" aria-hidden="true"><circle class="accent" cx="32" cy="32" r="20"/><circle cx="25" cy="28" r="4"/><circle cx="39" cy="28" r="4"/><path d="M24 41c5 4 11 4 16 0"/><path d="M7 26c8-5 16-7 25-7s18 2 25 7M17 12l-4-5M47 12l4-5"/></svg>
    <svg v-else viewBox="0 0 64 64" aria-hidden="true"><path class="accent" d="m32 4 7 19 20 1-16 12 6 20-17-11-17 11 6-20L5 24l20-1Z"/><circle cx="25" cy="29" r="3"/><circle cx="39" cy="29" r="3"/><path d="M24 38c5 4 11 4 16 0"/></svg>
  </span>
</template>

<style scoped>
.user-avatar{display:inline-grid;width:100%;height:100%;place-items:center;overflow:hidden;border-radius:50%;background:var(--avatar-bg);color:var(--avatar-line)}.user-avatar img{width:100%;height:100%;object-fit:cover}.user-avatar svg{width:88%;height:88%;fill:var(--avatar-face);stroke:var(--avatar-line);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}.user-avatar .accent{fill:var(--avatar-accent)}
.avatar-indigo{--avatar-bg:#dce5ff;--avatar-face:#f8c9ad;--avatar-line:#24345f;--avatar-accent:#536fd1}.avatar-sunset{--avatar-bg:#ffe0c3;--avatar-face:#f3b997;--avatar-line:#65352e;--avatar-accent:#d75c48}.avatar-forest{--avatar-bg:#d9eedb;--avatar-face:#f0bd93;--avatar-line:#244c39;--avatar-accent:#4b9a62}.avatar-ocean{--avatar-bg:#d6f1f4;--avatar-face:#e7b18e;--avatar-line:#184a62;--avatar-accent:#3c9dc1}.avatar-cherry{--avatar-bg:#ffe0e8;--avatar-face:#efb594;--avatar-line:#613044;--avatar-accent:#d85c83}.avatar-mono{--avatar-bg:#e7e8eb;--avatar-face:#fff;--avatar-line:#252a31;--avatar-accent:#aeb4bf}.avatar-cosmos{--avatar-bg:#dfdaf7;--avatar-face:#f4d9b2;--avatar-line:#352861;--avatar-accent:#7762b8}.avatar-spark{--avatar-bg:#fff0bd;--avatar-face:#fff7dc;--avatar-line:#604b19;--avatar-accent:#e4ad2f}
</style>
