## 目标

为 UI 自动化模块的删除操作加引用限制，实现删除顺序引导：**测试用例 → 步骤 → 页面（元素）**：

1. **元素**：被页面步骤（`UiPageStepsDetailed.element`）引用时不允许删除 —— 已有实现，保留
2. **步骤（`UiPageSteps`）**：被测试用例（`UiCaseStepsDetailed.page_step`）引用时不允许删除 —— 目前靠 PROTECT 兜底、错误信息笼统，改为显式检查并给出明确提示
3. **页面（`UiPage`）**：页面下存在步骤集合、或页面下元素被步骤引用时不允许删除 —— 目前无显式检查（元素被引用会随页面删除被 SET_NULL），需新增检查

## 后端修改：`WHartTest_Django/ui_automation/views.py`

### 1. `UiPageStepsViewSet.destroy`（L399-408）
在 `perform_destroy` 前增加显式检查：
```python
usage_count = instance.case_usages.count()
if usage_count:
    return Response(
        {'error': f'步骤已被 {usage_count} 个测试用例引用，无法删除。请先删除引用该步骤的测试用例'},
        status=status.HTTP_400_BAD_REQUEST
    )
```
保留原有 `ProtectedError` 捕获作为兜底。

### 2. `UiPageViewSet.destroy`（L283-292）
在 `perform_destroy` 前增加两个显式检查（按删除顺序从后向前拦截）：
- 页面下存在步骤集合（`instance.page_steps.count()`）→ 400 `'页面下存在 N 个页面步骤，无法删除页面。请先删除页面下的步骤'`
- 页面下元素被步骤引用（`UiPageStepsDetailed.objects.filter(element__page=instance).count()`）→ 400 `'页面下的元素已被 N 个页面步骤引用，无法删除页面。请先删除引用这些元素的步骤'`

保留原有 `ProtectedError` 捕获作为兜底。`UiPageStepsDetailed` 已在 imports 中（views.py L13-17），无需新增 import。

### 3. `UiElementViewSet.destroy`（L359-367）
已有引用检查（"元素已被 N 个页面步骤引用，无法删除"），不改动。

## 前端修改：`WHartTest_Vue/src/features/ui-automation/`

### 4. `views/PageList.vue` L72
删除确认文案由 `"确定删除该页面？关联的元素也会被删除。"` 改为提示删除条件：
`"确定删除该页面？若页面下存在步骤或元素被步骤引用，将无法删除。"`

### 5. `views/PageStepList.vue` L169 / L208（deleteStepConfirm 中英文文案）
由 `"确定删除该步骤？"` 改为：`"确定删除该步骤？若被测试用例引用则无法删除，请先删除相关用例。"`（中英文同步更新）

### 6. `views/ElementList.vue` L44
删除确认文案由 `"确定删除该元素？"` 改为：`"确定删除该元素？若被页面步骤引用则无法删除，请先删除相关步骤。"`

## 国际化：`WHartTest_Vue/src/i18n/index.ts`

在 `LEGACY_REGEX_EN_MAP` 中新增 3 条英文翻译正则（PageStepList.vue 的 `tl()` 会翻译后端错误信息；含数字故用正则而非精确匹配）：
- `/^步骤已被\s*(\d+)\s*个测试用例引用.*$/` → `Step is referenced by N test case(s). Delete the referencing test case(s) first.`
- `/^页面下存在\s*(\d+)\s*个页面步骤.*$/` → `Page contains N page step(s). Delete the steps under this page first.`
- `/^页面下的元素已被\s*(\d+)\s*个页面步骤引用.*$/` → `Elements on this page are referenced by N step(s). Delete the referencing steps first.`

## 验证

- 后端：运行 `python manage.py check` 及 `ui_automation` 现有测试确认无回归
- 前端：运行 TypeScript 检查（vue-tsc 或项目 lint 脚本）确认无类型/语法错误

## 说明

- 用例删除（`UiTestCaseViewSet`）不加限制，与"用例最先删除"的顺序一致
- 不涉及数据库迁移；错误信息通过现有 `err?.error` 透出机制展示（PageList/PageStepList/ElementList 均已支持）