<template>
  <router-view></router-view>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useAuthStore } from '@/store/authStore';

const authStore = useAuthStore();

// 在应用启动时检查认证状态
onMounted(() => {
  authStore.checkAuthStatus();
  console.log('App mounted, checking auth status');
});
</script>

<style>
/* Global styles can be placed here or in a separate CSS file like src/style.css */
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  min-height: 100vh; /* Ensure app takes full viewport height */
}

/* Reset some default browser styles */
body, html {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>
