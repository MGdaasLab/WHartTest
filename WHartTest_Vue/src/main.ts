import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ArcoVue from '@arco-design/web-vue'; // 导入 Arco Design Vue 组件库
import './style.css'
import '@arco-design/web-vue/dist/arco.css';
import './arco-theme-override.css' // 引入 Arco Design 主题覆盖样式
import './assets/wired-elements-custom.css'
import App from './App.vue'
import router from './router' // 新增导入
import 'wired-elements'

const app = createApp(App)

app.use(createPinia())
app.use(router) // 新增使用 router
app.use(ArcoVue); // 新增：全局注册 Arco Design 组件
app.mount('#app')
