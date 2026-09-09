"""
UI自动化执行器 - 执行画面帧采集（直播到前端画布，headless 下同样可用）

实现与录制器同构：
- 优先 CDP Page.startScreencast（浏览器原生编码 jpeg 帧，每帧须 Ack 否则暂停推流）；
- CDP 不可用时回退定时 page.screenshot(jpeg) 内存帧。

只保留最新一帧、由固定间隔泵推送（丢帧合并，不积压上行通道）。
默认 5fps、最大宽度 1280、jpeg quality 50（约 150KB/s）；可用环境变量调节：
- WHARTTEST_STREAM_FRAMES=false 完全关闭帧采集
- WHARTTEST_FRAME_RATE=5 帧率
"""

import asyncio
import base64
import logging
import os
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger('actuator.frame_stream')

_MAX_WIDTH = 1280
_QUALITY = 50


def stream_enabled() -> bool:
    """是否开启执行画面帧推流（默认开启，WHARTTEST_STREAM_FRAMES=false 关闭）"""
    return os.environ.get('WHARTTEST_STREAM_FRAMES', 'true').lower() != 'false'


def frame_rate() -> float:
    """目标帧率（默认 5fps）"""
    try:
        rate = float(os.environ.get('WHARTTEST_FRAME_RATE', '60'))
        return rate if rate > 0 else 5.0
    except ValueError:
        return 5.0


class FrameStreamer:
    """从执行浏览器采集画面帧并经 on_frame 回调推送（只发最新帧）。"""

    def __init__(self, page: Page, on_frame):
        """
        Args:
            page: 执行中的浏览器页面
            on_frame: async (w, h, base64_jpeg) -> None 回调
        """
        self._page = page
        self._on_frame = on_frame
        self._interval = 1.0 / max(1.0, frame_rate())
        self._cdp = None
        self._latest = None          # (w, h, base64_jpeg)：只保留最新一帧
        self._tasks: list[asyncio.Task] = []
        self._stopped = False

    async def start(self) -> None:
        """启动帧采集：优先 CDP screencast，失败回退定时截图。"""
        if self._stopped:
            return
        self._tasks.append(asyncio.ensure_future(self._pump_loop()))
        try:
            session = await self._page.context.new_cdp_session(self._page)
            await session.send('Page.enable')
            session.on('Page.screencastFrame', self._on_screencast)
            await session.send('Page.startScreencast', {
                'format': 'jpeg',
                'quality': _QUALITY,
                'maxWidth': _MAX_WIDTH,
                'everyNthFrame': 1,
            })
            self._cdp = session  # 启动成功后才对帧负有 Ack 责任
            logger.info('[frame_stream] CDP screencast 已启动（%.1f fps）', 1.0 / self._interval)
            return
        except Exception as e:
            self._cdp = None
            logger.warning('[frame_stream] CDP screencast 不可用，回退定时截图: %s', e)
        self._tasks.append(asyncio.ensure_future(self._screenshot_loop()))

    def _on_screencast(self, params: dict) -> None:
        """CDP 帧事件（同步回调）：逐帧 Ack，数据只保留最新一帧。"""
        session_id = params.get('sessionId')
        if session_id and self._cdp:
            asyncio.create_task(self._ack(session_id))
        data = params.get('data', '')
        if not data:
            return
        if data.startswith('data:image/jpeg;base64,'):
            data = data[len('data:image/jpeg;base64,'):]
        meta = params.get('metadata') or {}
        w = int(meta.get('deviceWidth') or 0)
        h = int(meta.get('deviceHeight') or 0)
        if w and h:
            self._latest = (w, h, data)

    async def _ack(self, session_id: str) -> None:
        try:
            await self._cdp.send('Page.screencastFrameAck', {'sessionId': session_id})
        except Exception:
            pass

    async def _pump_loop(self) -> None:
        """固定间隔把最新一帧推给回调（丢帧合并，不积压）。"""
        while not self._stopped:
            await asyncio.sleep(self._interval)
            latest, self._latest = self._latest, None
            if latest is None:
                continue
            try:
                await self._on_frame(*latest)
            except Exception as e:
                logger.debug('[frame_stream] 推送帧失败: %s', e)

    async def _screenshot_loop(self) -> None:
        """CDP 不可用的兜底：定时截图内存帧。"""
        while not self._stopped:
            try:
                buf = await self._page.screenshot(type='jpeg', quality=_QUALITY)
                w = await self._page.evaluate('() => window.innerWidth')
                h = await self._page.evaluate('() => window.innerHeight')
                if buf:
                    self._latest = (int(w or 0), int(h or 0), base64.b64encode(buf).decode('ascii'))
            except Exception as e:
                logger.debug('[frame_stream] 截图兜底失败: %s', e)
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        """停止采集（幂等）。"""
        self._stopped = True
        if self._cdp:
            try:
                await self._cdp.send('Page.stopScreencast')
            except Exception:
                pass
            self._cdp = None
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []