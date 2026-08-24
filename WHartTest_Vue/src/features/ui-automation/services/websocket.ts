/**
 * UI 自动化 WebSocket 服务
 * 用于与后端建立实时通信，发送执行任务和接收结果
 */

import { ref, shallowRef } from 'vue'
import { useAuthStore } from '@/store/authStore'
import { getCurrentServerLanguage } from '@/utils/installLocaleAdapters'

/** 消息类型枚举 */
export const UiSocketEnum = {
  PAGE_STEPS: 'u_page_steps',             // 执行页面步骤
  PAGE_STEP_RESULT: 'u_page_step_result', // 页面步骤执行结果
  TEST_CASE: 'u_test_case',               // 执行测试用例
  TEST_CASE_BATCH: 'u_test_case_batch',   // 批量执行用例
  STOP_EXECUTION: 'u_stop_execution',     // 停止执行
  STEP_RESULT: 'u_step_result',           // 步骤执行结果
  CASE_RESULT: 'u_case_result',           // 用例执行结果
  // 录制器
  RECORDER_START: 'u_recorder_start',     // 绑定录制会话，启动帧中继
  RECORDER_INPUT: 'u_recorder_input',     // 浏览器输入事件
  RECORDER_ASSERT: 'u_recorder_assert',   // 记录断言动作
  RECORDER_STOP: 'u_recorder_stop',       // 停止帧中继
  RECORDER_FRAME: 'u_recorder_frame',     // 浏览器画面帧
  RECORDER_ACTION: 'u_recorder_action',   // 录制动作增量
  RECORDER_STATUS: 'u_recorder_status',   // 录制状态/错误
} as const

/** Socket 消息模型 */
export interface QueueModel {
  func_name: string
  func_args: Record<string, any>
}

export interface SocketDataModel {
  code: number
  msg: string
  user?: string
  is_notice: number
  data?: QueueModel
}

/** 步骤执行结果 */
export interface StepResultModel {
  step_id: number
  status: 'success' | 'failed' | 'skipped'
  message: string
  screenshot?: string
  duration: number
  element_found: boolean
}

/** 用例执行结果 */
export interface CaseResultModel {
  case_id: number
  status: 'success' | 'failed' | 'skipped'
  message: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  duration: number
  steps: StepResultModel[]
}

type MessageHandler = (data: SocketDataModel) => void

class UiWebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private handlers: Map<string, MessageHandler[]> = new Map()
  
  public connected = ref(false)
  public error = shallowRef<Error | null>(null)
  
  /** 获取 WebSocket URL */
  private getWsUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_HOST || window.location.host
    const url = new URL(`${protocol}//${host}/ws/ui/web/`)
    url.searchParams.set('lang', getCurrentServerLanguage())
    return url.toString()
  }
  
  /** 连接 WebSocket */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }
      
      const url = this.getWsUrl()
      console.log('[WebSocket] Connecting to:', url)
      
      this.ws = new WebSocket(url)
      
      this.ws.onopen = () => {
        console.log('[WebSocket] Connected')
        this.connected.value = true
        this.error.value = null
        this.reconnectAttempts = 0
        resolve()
      }
      
      this.ws.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason)
        this.connected.value = false
        this.attemptReconnect()
      }
      
      this.ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        this.error.value = new Error('WebSocket connection error')
        reject(this.error.value)
      }
      
      this.ws.onmessage = (event) => {
        this.handleMessage(event.data)
      }
    })
  }
  
  /** 处理收到的消息 */
  private handleMessage(rawData: string) {
    try {
      const data: SocketDataModel = JSON.parse(rawData)
      console.log('[WebSocket] Received:', data)
      
      // 根据 func_name 触发对应的处理函数
      const funcName = data.data?.func_name
      if (funcName) {
        const handlers = this.handlers.get(funcName) || []
        handlers.forEach(handler => handler(data))
      }
      
      // 触发通用消息处理
      const allHandlers = this.handlers.get('*') || []
      allHandlers.forEach(handler => handler(data))
    } catch (e) {
      console.error('[WebSocket] Failed to parse message:', e)
    }
  }
  
  /** 重连逻辑 */
  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnect attempts reached')
      return
    }
    
    this.reconnectAttempts++
    console.log(`[WebSocket] Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    setTimeout(() => {
      this.connect().catch(console.error)
    }, this.reconnectDelay)
  }
  
  /** 发送消息 */
  send(funcName: string, funcArgs: Record<string, any>) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Not connected')
      return false
    }
    
    const message: SocketDataModel = {
      code: 200,
      msg: 'request',
      is_notice: 2, // 发送给执行器
      data: {
        func_name: funcName,
        func_args: funcArgs,
      }
    }
    
    console.log('[WebSocket] Sending:', message)
    this.ws.send(JSON.stringify(message))
    return true
  }
  
  /** 注册消息处理函数 */
  on(funcName: string, handler: MessageHandler) {
    if (!this.handlers.has(funcName)) {
      this.handlers.set(funcName, [])
    }
    this.handlers.get(funcName)!.push(handler)
    return () => this.off(funcName, handler)
  }
  
  /** 移除消息处理函数 */
  off(funcName: string, handler: MessageHandler) {
    const handlers = this.handlers.get(funcName)
    if (handlers) {
      const idx = handlers.indexOf(handler)
      if (idx > -1) handlers.splice(idx, 1)
    }
  }
  
  /** 断开连接 */
  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.connected.value = false
  }
  
  /** 执行测试用例 */
  runTestCase(caseId: number, envConfigId?: number, actuatorId?: string): boolean {
    // 从auth store获取当前用户信息
    const authStore = useAuthStore()
    const currentUser = authStore.currentUser
    
    return this.send(UiSocketEnum.TEST_CASE, {
      case_id: caseId,
      env_config_id: envConfigId,
      actuator_id: actuatorId,
      executor_id: currentUser?.id,
      executor_name: currentUser?.username,
    })
  }
  
  /** 批量执行测试用例 */
  runTestCases(caseIds: number[], envConfigId?: number, actuatorId?: string): boolean {
    // 从auth store获取当前用户信息
    const authStore = useAuthStore()
    const currentUser = authStore.currentUser
    
    return this.send(UiSocketEnum.TEST_CASE_BATCH, {
      case_ids: caseIds,
      env_config_id: envConfigId,
      actuator_id: actuatorId,
      executor_id: currentUser?.id,
      executor_name: currentUser?.username,
    })
  }
  
  /** 执行页面步骤 */
  runPageSteps(pageStepId: number, envConfigId?: number, actuatorId?: string): boolean {
    // 从auth store获取当前用户信息
    const authStore = useAuthStore()
    const currentUser = authStore.currentUser
    
    return this.send(UiSocketEnum.PAGE_STEPS, {
      page_step_id: pageStepId,
      env_config_id: envConfigId,
      actuator_id: actuatorId,
      executor_id: currentUser?.id,
      executor_name: currentUser?.username,
    })
  }
  
  /** 停止执行 */
  stopExecution(taskId?: string): boolean {
    return this.send(UiSocketEnum.STOP_EXECUTION, {
      task_id: taskId,
    })
  }

  // ---------------- 录制器 ----------------

  /** 绑定录制会话（开始帧中继） */
  recorderStart(sessionId: string): boolean {
    return this.send(UiSocketEnum.RECORDER_START, { session_id: sessionId })
  }

  /** 转发浏览器输入事件 */
  recorderInput(args: Record<string, any>): boolean {
    return this.send(UiSocketEnum.RECORDER_INPUT, args)
  }

  /** 记录断言动作 */
  recorderAssert(mode: string): boolean {
    return this.send(UiSocketEnum.RECORDER_ASSERT, { mode })
  }

  /** 停止帧中继 */
  recorderStop(): boolean {
    return this.send(UiSocketEnum.RECORDER_STOP, {})
  }
}

/** 单例实例 */
export const uiWebSocket = new UiWebSocketService()
