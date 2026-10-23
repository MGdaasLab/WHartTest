"""
skill-runner：Skill 命令的独立执行面（第 2 层）

设计目标是把「执行面」与「凭证面」分开：

- backend 只负责鉴权、取用户可见的 skill 目录，并把作业提交给 runner；
- runner 进程中**不存在**任何平台机密（无 DJANGO_SECRET_KEY、无 DB 口令、无 LLM Key），
  容器也不挂在业务网段（到不了 postgres/redis/qdrant），文件系统只读 + tmpfs 工作区；
- 即使模型在 skill 里跑出任意代码，能拿到的也只是一个无秘密、无持久化、无内网可达的沙箱。

本模块只依赖标准库，便于在最小镜像里运行；命令策略直接复用
``orchestrator_integration/builtin_tools/skill_exec_guard.py``（同一份实现，避免两侧漂移）。
"""

__all__ = ["server", "executor"]
