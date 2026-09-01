# -*- coding: utf-8 -*-
"""
whart_test_tools.py - 兼容别名脚本，直接代理执行 whart_tools.py
解决大模型根据技能名 whart-test 推断调用 whart_test_tools.py 时的找不到文件问题。
"""
import sys
from pathlib import Path

# 将当前脚本所在目录加入 sys.path
_current_dir = str(Path(__file__).parent.resolve())
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import whart_tools

if __name__ == '__main__':
    whart_tools.main()
