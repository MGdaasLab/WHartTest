import { createApp } from 'vue' // 从 Vue 导入 createApp 工厂函数，用于创建应用实例。
import { createPinia } from 'pinia' // 从 Pinia 导入状态管理创建函数，用于全局状态容器初始化。
import ArcoVue from '@arco-design/web-vue'; // 导入 Arco Design Vue 组件库主插件，后续注册到应用实例。
import ArcoVueIcon from '@arco-design/web-vue/es/icon'; // 导入 Arco Design 图标插件，提供全局图标组件。
import './style.css' // 导入项目全局基础样式文件。
import '@arco-design/web-vue/dist/arco.css'; // 导入 Arco 官方样式，保证组件样式可用。
import './arco-theme-override.css' // 导入 Arco 主题覆盖样式，用于项目定制视觉主题。
import './assets/wired-elements-custom.css' // 导入 wired-elements 的自定义样式覆盖文件。
import App from './App.vue' // 导入根组件 App，作为整个前端应用挂载入口。
import router from './router' // 导入路由实例，用于页面导航与守卫控制。
import 'wired-elements' // 导入 wired-elements Web Components，完成其全局注册。
import { useThemeStore } from './store/themeStore';
import { useLocaleStore } from './store/localeStore';
import { installLocaleAdapters } from './utils/installLocaleAdapters';

// Monaco Editor 配置 - 使用本地资源，无需外网
import * as monaco from 'monaco-editor' // 导入 monaco-editor 命名空间对象，供加载器注入编辑器实现。
import { loader } from '@guolao/vue-monaco-editor' // 导入 vue-monaco-editor 的 loader 配置器。
loader.config({ monaco }) // 将本地 monaco 实例注入 loader，避免运行时走外网 CDN 拉取资源。

const app = createApp(App) // 创建 Vue 应用实例，并指定根组件为 App。
const pinia = createPinia()

app.use(pinia) // 安装 Pinia 插件，让全局 store 在所有组件中可用。
app.use(router) // 安装路由插件，启用声明式路由和路由守卫。
app.use(ArcoVue); // 安装 Arco UI 组件插件，实现组件按需/全局能力。
app.use(ArcoVueIcon); // 安装 Arco 图标插件，支持在模板中直接使用图标组件。
useThemeStore(pinia).initializeTheme();
useLocaleStore(pinia).initializeLocale();
installLocaleAdapters(pinia);
app.mount('#app') // 将应用挂载到 index.html 中 id 为 app 的容器节点。
