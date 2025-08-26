# 为 WHartTest  做贡献

感谢您有兴趣为 WHartTest  做贡献！本文档提供了我们开发工作流程的指南和信息。

## 分支策略

我们使用三分支工作流程来确保代码质量和稳定发布：

### 分支描述

- **`master`** 🚀
  - 仅包含生产就绪代码
  - 受保护分支，有严格规则
  - 仅接受从 `release` 分支合并
  - 自动标记发布版本

- **`release`** 🧪
  - 发布候选分支
  - 用于最终测试和错误修复
  - 从 `dev` 分支合并
  - 测试完成后合并到 `master`

- **`dev`** 🔧
  - 主开发分支
  - 所有功能分支都合并到这里
  - 在这里进行集成测试
  - 应始终保持工作状态

### 工作流程过程

```
1. 从 dev 创建功能分支
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name

2. 开发您的功能
   - 编写代码
   - 如适用，添加测试
   - 更新文档

3. 提交 Pull Request 到 dev
   - 确保 CI 通过
   - 请求代码审查
   - 处理反馈

4. 发布流程（仅维护者）
   dev → release → master
```

## 开发指南

### 代码风格

- 遵循 TypeScript 最佳实践
- 使用 ESLint 和 Prettier 配置
- 编写有意义的提交信息
- 为复杂函数添加 JSDoc 注释

### 提交信息格式

```
type(scope): description

示例：
feat(auth): 添加用户登录功能
fix(ui): 解决按钮对齐问题
docs(readme): 更新安装说明
```

### Pull Request 指南

1. **标题**：清晰且具有描述性
2. **描述**：解释做什么以及为什么做
3. **测试**：描述您如何测试
4. **截图**：对于 UI 更改
5. **破坏性更改**：明确标记

### 分支命名

- `feature/description` - 新功能
- `fix/description` - 错误修复
- `docs/description` - 文档更新
- `refactor/description` - 代码重构
- `test/description` - 添加测试

## 设置开发环境

1. **克隆仓库**
   ```bash
   git clone https://github.com/MGdaasLab/WHartTest.git
   cd WHartTest_Vue
   ```

2. **安装依赖**
   ```bash
   npm install
   ```

3. **启动开发服务器**
   ```bash
   npm run dev
   ```

4. **运行测试**
   ```bash
   npm test
   ```

## 分支保护规则（维护者）

### Master 分支
- 需要 Pull Request 审查
- 需要状态检查通过
- 要求分支保持最新
- 仅限管理员推送

### Release 分支
- 需要 Pull Request 审查
- 需要状态检查通过
- 允许合并提交

### Dev 分支
- 需要状态检查通过
- 允许压缩合并

## 发布流程

1. **准备发布**
   ```bash
   git checkout release
   git merge dev
   git push origin release
   ```

2. **测试发布候选版本**
   - 部署到预发布环境
   - 运行集成测试
   - 执行手动测试

3. **部署到生产环境**
   ```bash
   git checkout master
   git merge release
   git tag v1.x.x
   git push origin master --tags
   ```

4. **同步 Dev 分支**
   ```bash
   git checkout dev
   git merge master
   git push origin dev
   ```

## 获取帮助

- 📖 查看现有文档
- 🐛 搜索现有问题
- 💬 加入我们的讨论
- 📧 联系维护者

## 行为准则

请在所有互动中保持尊重和专业。我们在这里一起构建伟大的东西！

---

感谢您为 WHartTest 做贡献！🎉
