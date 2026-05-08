<template>
  <router-view></router-view> <!-- 渲染当前路由匹配到的页面组件，是整站页面切换的承载位。 -->
</template>

<script setup lang="ts">
import { onMounted } from 'vue'; // 导入 onMounted 生命周期钩子，用于组件初次挂载后执行初始化逻辑。
import { useAuthStore } from '@/store/authStore'; // 导入认证状态 store 的组合式函数，用于访问登录态能力。

const authStore = useAuthStore(); // 获取 authStore 实例，后续可调用认证状态检查方法。

// 在应用启动时检查认证状态
onMounted(() => { // 在根组件挂载完成后执行一次初始化回调。
  authStore.checkAuthStatus(); // 触发认证状态校验（如读取本地 token 并同步登录状态）。
  console.log('App mounted, checking auth status'); // 输出调试日志，标记应用启动时已执行认证检查。
});
</script>

<style>
/* 全局样式可写在这里，也可拆分到独立样式文件（如 src/style.css） */
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif; /* 设置应用默认字体栈，优先使用 Avenir 并提供系统回退字体。 */
  -webkit-font-smoothing: antialiased; /* 在 WebKit 内核浏览器启用抗锯齿字体渲染。 */
  -moz-osx-font-smoothing: grayscale; /* 在 macOS Firefox 上优化字体平滑显示效果。 */
  /* text-align: center; */ /* 移除全局居中，避免影响布局 */
  color: var(--theme-page-text); /* 设置应用默认文字颜色为当前主题页面文本色。 */
  min-height: 100vh; /* 保证根容器最小高度覆盖整个可视区域高度。 */
}

/* 重置部分浏览器默认样式 */
body, html {
  margin: 0; /* 清除浏览器默认外边距，避免页面出现白边。 */
  padding: 0; /* 清除浏览器默认内边距，保证布局起点一致。 */
  height: 100%; /* 让 html/body 高度撑满视口，配合 #app 高度布局。 */
}
</style>
