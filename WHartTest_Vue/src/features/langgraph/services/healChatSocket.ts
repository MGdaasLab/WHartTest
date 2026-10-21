/**
 * 自愈对话实时推送：订阅 /ws/heal/chat/ 接收后端转发的 agent-loop 事件（打字机效果）。
 *
 * - 浏览器与自愈任务的 SSE 流分属两端，WS 只推「订阅之后」的事件；
 *   历史加载仍走 history 接口，断线补偿由对话页的低频轮询兜底。
 */

export interface HealStreamEvent {
  type: string;                    // start / stream / tool_result / step_complete / error / complete ...
  data?: string;                   // stream 事件的增量文本
  message?: string;                // error 等事件的消息
  summary?: string;                // tool_result 摘要
  tool_name?: string;
  step?: number;
  session_id?: string;
}

export interface HealChatSubscription {
  close: () => void;
}

/** 构造自愈对话 WS 地址（复用 HTTP 基础路径与 JWT） */
const buildHealWsUrl = (sessionId: string, token: string): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const query = new URLSearchParams({ token, session_id: String(sessionId) });
  return `${protocol}://${window.location.host}/ws/heal/chat/?${query.toString()}`;
};

/**
 * 订阅自愈会话事件流。
 * @param sessionId  自愈会话 ID
 * @param token      JWT access token
 * @param onEvent    收到流事件时的回调
 * @param onClose    连接关闭回调（含异常关闭），调用方可据此启动轮询兜底
 */
export const subscribeHealChat = (
  sessionId: string,
  token: string,
  onEvent: (event: HealStreamEvent) => void,
  onClose?: (event: CloseEvent) => void,
): HealChatSubscription => {
  const ws = new WebSocket(buildHealWsUrl(sessionId, token));

  ws.onmessage = (message) => {
    try {
      const payload = JSON.parse(message.data);
      if (payload?.type === 'heal_event' && payload.event) {
        onEvent(payload.event as HealStreamEvent);
      }
      // subscribed / pong 等控制帧不回调
    } catch {
      // 非 JSON 帧，忽略
    }
  };

  ws.onclose = (event) => {
    onClose?.(event);
  };

  // 客户端保活探测：每 30s 发 ping，服务端回 pong
  const keepaliveTimer = window.setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 30000);

  return {
    close: () => {
      window.clearInterval(keepaliveTimer);
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.onclose = null; // 主动关闭不触发兜底
        ws.close();
      }
    },
  };
};
