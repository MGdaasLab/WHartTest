# -*- coding: utf-8 -*-
"""
UI Automation Skill 测试脚本

测试所有 API 函数的完整流程：
创建模块 → 创建页面 → 创建元素 → 创建页面步骤 → 创建测试用例 → 清理
"""
import json
import sys
from pathlib import Path

# 添加当前目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from ui_automation_tools import (
    # 模块
    get_ui_modules, create_ui_module, update_ui_module, delete_ui_module,
    # 页面
    get_ui_pages, get_ui_page, create_ui_page, update_ui_page, delete_ui_page,
    # 元素
    get_elements, create_element, update_element, delete_element, batch_create_elements,
    # 页面步骤
    get_page_steps, get_page_step, create_page_step, update_page_step, delete_page_step, set_step_details,
    # 测试用例
    get_testcases, get_testcase, create_testcase, update_testcase, delete_testcase, set_case_steps,
    # 公共数据
    get_public_data, create_public_data, update_public_data, delete_public_data,
)


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def log_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def log_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def log_info(msg):
    print(f"{Colors.BLUE}→ {msg}{Colors.END}")


def log_section(msg):
    print(f"\n{Colors.YELLOW}{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}{Colors.END}")


def test_module_crud(project_id: int):
    """测试模块 CRUD"""
    log_section("测试模块管理")
    
    # 创建模块
    log_info("创建模块...")
    result = create_ui_module(project_id, "测试模块_自动化测试")
    if result.get("status") == "success":
        module_id = result["data"]["id"]
        log_success(f"创建模块成功: ID={module_id}")
    else:
        log_error(f"创建模块失败: {result}")
        return None
    
    # 获取模块列表
    log_info("获取模块列表...")
    result = get_ui_modules(project_id)
    if isinstance(result, list):
        log_success(f"获取模块列表成功: {len(result)} 个模块")
    else:
        log_error(f"获取模块列表失败: {result}")
    
    # 更新模块
    log_info("更新模块...")
    result = update_ui_module(module_id, "测试模块_已更新")
    if result.get("status") == "success":
        log_success(f"更新模块成功: name={result['data'].get('name')}")
    else:
        log_error(f"更新模块失败: {result}")
    
    return module_id


def test_page_crud(project_id: int, module_id: int):
    """测试页面 CRUD"""
    log_section("测试页面管理")
    
    # 创建页面
    log_info("创建页面...")
    result = create_ui_page(project_id, module_id, "测试页面", "http://test.com/page", "自动化测试页面")
    if result.get("status") == "success":
        page_id = result["data"]["id"]
        log_success(f"创建页面成功: ID={page_id}")
    else:
        log_error(f"创建页面失败: {result}")
        return None
    
    # 获取页面列表
    log_info("获取页面列表...")
    result = get_ui_pages(project_id, module_id)
    if isinstance(result, list):
        log_success(f"获取页面列表成功: {len(result)} 个页面")
    else:
        log_error(f"获取页面列表失败: {result}")
    
    # 获取页面详情
    log_info("获取页面详情...")
    result = get_ui_page(page_id)
    if isinstance(result, dict) and result.get("id") == page_id:
        log_success(f"获取页面详情成功: name={result.get('name')}")
    else:
        log_error(f"获取页面详情失败: {result}")
    
    # 更新页面
    log_info("更新页面...")
    result = update_ui_page(page_id, name="测试页面_已更新", url="http://test.com/updated")
    if result.get("status") == "success":
        log_success(f"更新页面成功")
    else:
        log_error(f"更新页面失败: {result}")
    
    return page_id


def test_element_crud(page_id: int):
    """测试元素 CRUD"""
    log_section("测试元素管理")
    
    # 创建单个元素
    log_info("创建单个元素...")
    result = create_element(
        page_id, "用户名输入框", "css", "#username",
        locator_type_2="xpath", locator_value_2="//input[@id='username']",
        description="登录页用户名输入框"
    )
    if result.get("status") == "success":
        element_id = result["data"]["id"]
        log_success(f"创建元素成功: ID={element_id}")
    else:
        log_error(f"创建元素失败: {result}")
        return []
    
    # 批量创建元素
    log_info("批量创建元素...")
    elements = [
        {"name": "密码输入框", "locator_type": "css", "locator_value": "#password"},
        {"name": "登录按钮", "locator_type": "css", "locator_value": "button[type=submit]"},
        {"name": "记住我", "locator_type": "xpath", "locator_value": "//input[@type='checkbox']"},
    ]
    result = batch_create_elements(page_id, elements)
    if result.get("status") == "success":
        created_ids = [e.get("id") for e in result.get("data", [])]
        log_success(f"批量创建元素成功: {len(created_ids)} 个")
    else:
        log_error(f"批量创建元素失败: {result}")
        created_ids = []
    
    # 获取元素列表
    log_info("获取元素列表...")
    result = get_elements(page_id)
    if isinstance(result, list):
        log_success(f"获取元素列表成功: {len(result)} 个元素")
    else:
        log_error(f"获取元素列表失败: {result}")
    
    # 更新元素
    log_info("更新元素...")
    result = update_element(element_id, name="用户名输入框_已更新", wait_time=2)
    if result.get("status") == "success":
        log_success("更新元素成功")
    else:
        log_error(f"更新元素失败: {result}")
    
    return [element_id] + created_ids


def test_page_step_crud(project_id: int, page_id: int, module_id: int, element_ids: list):
    """测试页面步骤 CRUD"""
    log_section("测试页面步骤管理")
    
    # 创建页面步骤
    log_info("创建页面步骤...")
    result = create_page_step(project_id, page_id, module_id, "登录操作", "输入用户名密码并点击登录")
    if result.get("status") == "success":
        step_id = result["data"]["id"]
        log_success(f"创建页面步骤成功: ID={step_id}")
    else:
        log_error(f"创建页面步骤失败: {result}")
        return None
    
    # 设置步骤详情
    if element_ids:
        log_info("设置步骤详情...")
        steps = [
            {"step_type": 0, "element": element_ids[0], "ope_key": "fill", "ope_value": {"value": "admin"}},
        ]
        if len(element_ids) > 1:
            steps.append({"step_type": 0, "element": element_ids[1], "ope_key": "fill", "ope_value": {"value": "password123"}})
        if len(element_ids) > 2:
            steps.append({"step_type": 0, "element": element_ids[2], "ope_key": "click", "ope_value": {}})
        
        result = set_step_details(step_id, steps)
        if result.get("status") == "success":
            log_success(f"设置步骤详情成功: {len(steps)} 个步骤")
        else:
            log_error(f"设置步骤详情失败: {result}")
    
    # 获取页面步骤列表
    log_info("获取页面步骤列表...")
    result = get_page_steps(project_id, page_id)
    if isinstance(result, list):
        log_success(f"获取页面步骤列表成功: {len(result)} 个步骤")
    else:
        log_error(f"获取页面步骤列表失败: {result}")
    
    # 获取页面步骤详情
    log_info("获取页面步骤详情...")
    result = get_page_step(step_id)
    if isinstance(result, dict) and result.get("id") == step_id:
        log_success(f"获取页面步骤详情成功: name={result.get('name')}")
    else:
        log_error(f"获取页面步骤详情失败: {result}")
    
    # 更新页面步骤
    log_info("更新页面步骤...")
    result = update_page_step(step_id, name="登录操作_已更新")
    if result.get("status") == "success":
        log_success("更新页面步骤成功")
    else:
        log_error(f"更新页面步骤失败: {result}")
    
    return step_id


def test_testcase_crud(project_id: int, module_id: int, step_id: int):
    """测试测试用例 CRUD"""
    log_section("测试测试用例管理")
    
    # 创建测试用例
    log_info("创建测试用例...")
    result = create_testcase(project_id, module_id, "登录功能测试", "验证用户登录功能", "P0")
    if result.get("status") == "success":
        testcase_id = result["data"]["id"]
        log_success(f"创建测试用例成功: ID={testcase_id}")
    else:
        log_error(f"创建测试用例失败: {result}")
        return None
    
    # 设置用例步骤
    if step_id:
        log_info("设置用例步骤...")
        result = set_case_steps(testcase_id, [step_id])
        if result.get("status") == "success":
            log_success("设置用例步骤成功")
        else:
            log_error(f"设置用例步骤失败: {result}")
    
    # 获取测试用例列表
    log_info("获取测试用例列表...")
    result = get_testcases(project_id, module_id)
    if isinstance(result, list):
        log_success(f"获取测试用例列表成功: {len(result)} 个用例")
    else:
        log_error(f"获取测试用例列表失败: {result}")
    
    # 获取测试用例详情
    log_info("获取测试用例详情...")
    result = get_testcase(testcase_id)
    if isinstance(result, dict) and result.get("id") == testcase_id:
        log_success(f"获取测试用例详情成功: name={result.get('name')}")
    else:
        log_error(f"获取测试用例详情失败: {result}")
    
    # 更新测试用例
    log_info("更新测试用例...")
    result = update_testcase(testcase_id, name="登录功能测试_已更新", level="P1")
    if result.get("status") == "success":
        log_success("更新测试用例成功")
    else:
        log_error(f"更新测试用例失败: {result}")
    
    return testcase_id


def test_public_data_crud(project_id: int):
    """测试公共数据 CRUD"""
    log_section("测试公共数据管理")
    
    # 创建公共数据
    log_info("创建公共数据...")
    result = create_public_data(project_id, "test_username", "admin", description="测试用户名")
    if result.get("status") == "success":
        data_id = result["data"]["id"]
        log_success(f"创建公共数据成功: ID={data_id}")
    else:
        log_error(f"创建公共数据失败: {result}")
        return None
    
    # 获取公共数据列表
    log_info("获取公共数据列表...")
    result = get_public_data(project_id)
    if isinstance(result, list):
        log_success(f"获取公共数据列表成功: {len(result)} 条数据")
    else:
        log_error(f"获取公共数据列表失败: {result}")
    
    # 更新公共数据
    log_info("更新公共数据...")
    result = update_public_data(data_id, value="admin_updated")
    if result.get("status") == "success":
        log_success("更新公共数据成功")
    else:
        log_error(f"更新公共数据失败: {result}")
    
    return data_id


def cleanup(module_id, page_id, element_ids, step_id, testcase_id, data_id):
    """清理测试数据"""
    log_section("清理测试数据")
    
    # 删除测试用例
    if testcase_id:
        log_info(f"删除测试用例 ID={testcase_id}...")
        result = delete_testcase(testcase_id)
        if result.get("status") == "success":
            log_success("删除测试用例成功")
        else:
            log_error(f"删除测试用例失败: {result}")
    
    # 删除页面步骤
    if step_id:
        log_info(f"删除页面步骤 ID={step_id}...")
        result = delete_page_step(step_id)
        if result.get("status") == "success":
            log_success("删除页面步骤成功")
        else:
            log_error(f"删除页面步骤失败: {result}")
    
    # 删除元素
    for eid in (element_ids or []):
        if eid:
            log_info(f"删除元素 ID={eid}...")
            result = delete_element(eid)
            if result.get("status") == "success":
                log_success(f"删除元素 {eid} 成功")
            else:
                log_error(f"删除元素 {eid} 失败: {result}")
    
    # 删除页面
    if page_id:
        log_info(f"删除页面 ID={page_id}...")
        result = delete_ui_page(page_id)
        if result.get("status") == "success":
            log_success("删除页面成功")
        else:
            log_error(f"删除页面失败: {result}")
    
    # 删除公共数据
    if data_id:
        log_info(f"删除公共数据 ID={data_id}...")
        result = delete_public_data(data_id)
        if result.get("status") == "success":
            log_success("删除公共数据成功")
        else:
            log_error(f"删除公共数据失败: {result}")
    
    # 删除模块
    if module_id:
        log_info(f"删除模块 ID={module_id}...")
        result = delete_ui_module(module_id)
        if result.get("status") == "success":
            log_success("删除模块成功")
        else:
            log_error(f"删除模块失败: {result}")


def main():
    print(f"\n{Colors.BLUE}{'='*60}")
    print("  UI Automation Skill 完整测试")
    print(f"{'='*60}{Colors.END}")
    
    project_id = 1  # 使用项目 ID 1 进行测试
    
    module_id = None
    page_id = None
    element_ids = []
    step_id = None
    testcase_id = None
    data_id = None
    
    try:
        # 1. 测试模块
        module_id = test_module_crud(project_id)
        if not module_id:
            log_error("模块测试失败，终止测试")
            return
        
        # 2. 测试页面
        page_id = test_page_crud(project_id, module_id)
        if not page_id:
            log_error("页面测试失败，继续清理...")
        
        # 3. 测试元素
        if page_id:
            element_ids = test_element_crud(page_id)
        
        # 4. 测试页面步骤
        if page_id:
            step_id = test_page_step_crud(project_id, page_id, module_id, element_ids)
        
        # 5. 测试测试用例
        if step_id:
            testcase_id = test_testcase_crud(project_id, module_id, step_id)
        
        # 6. 测试公共数据
        data_id = test_public_data_crud(project_id)
        
    finally:
        # 清理测试数据
        cleanup(module_id, page_id, element_ids, step_id, testcase_id, data_id)
    
    print(f"\n{Colors.GREEN}{'='*60}")
    print("  测试完成!")
    print(f"{'='*60}{Colors.END}\n")


if __name__ == "__main__":
    main()
