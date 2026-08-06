# -*- coding: utf-8 -*-
"""UI 自动化视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models.deletion import ProtectedError
from django.db import transaction
from copy import deepcopy
from file_management.services import maybe_cleanup_unreferenced_files, sync_file_references

from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiPublicData, UiEnvironmentConfig,
    UiBatchExecutionRecord
)
from file_management.models import FileReference
from .serializers import (
    UiModuleSerializer, UiPageSerializer, UiPageDetailSerializer,
    UiElementSerializer, UiPageStepsSerializer, UiPageStepsListSerializer, UiPageStepsDetailSerializer,
    UiPageStepsDetailedSerializer, UiTestCaseSerializer, UiTestCaseListSerializer, UiTestCaseDetailSerializer,
    UiCaseStepsDetailedSerializer, UiExecutionRecordSerializer, UiExecutionRecordListSerializer,
    UiPublicDataSerializer, UiEnvironmentConfigSerializer, UiTestCaseExecuteSerializer,
    UiPageStepsExecuteSerializer, UiBatchExecutionRecordSerializer, UiBatchExecutionRecordDetailSerializer
)



def _ui_step_detail_ref_id(step_or_id):
    step_id = getattr(step_or_id, 'id', step_or_id)
    return f'detail:{step_id}'


def _extract_upload_file_id_from_step(step):
    if not step or step.ope_key != 'upload' or not isinstance(step.ope_value, dict):
        return None
    file_id = step.ope_value.get('file_id')
    if file_id in (None, ''):
        value = step.ope_value.get('value')
        if isinstance(value, str) and value.startswith('file_id:'):
            file_id = value.split(':', 1)[1]
    try:
        return int(file_id) if file_id not in (None, '') else None
    except (TypeError, ValueError):
        return None




def _sync_upload_step_file_reference(step, user=None):
    if not step or not step.id:
        return []
    project = step.page_step.project if step.page_step_id and step.page_step else None
    if not project:
        return []
    file_id = _extract_upload_file_id_from_step(step)
    file_ids = [file_id] if file_id else []
    return sync_file_references(
        file_ids,
        project,
        FileReference.REF_UI_PAGE_STEPS,
        _ui_step_detail_ref_id(step),
        user,
    )


def _remove_upload_step_file_reference(step, user=None):
    if not step or not step.id:
        return []
    project = step.page_step.project if step.page_step_id and step.page_step else None
    if not project:
        return []
    old_file_ids = list(FileReference.objects.filter(
        project=project,
        ref_type=FileReference.REF_UI_PAGE_STEPS,
        ref_id=_ui_step_detail_ref_id(step),
    ).values_list('file_id', flat=True))
    sync_file_references([], project, FileReference.REF_UI_PAGE_STEPS, _ui_step_detail_ref_id(step), user)
    return old_file_ids


class UiModuleViewSet(viewsets.ModelViewSet):
    """模块管理视图"""
    queryset = UiModule.objects.select_related('project', 'parent', 'creator')
    serializer_class = UiModuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'parent', 'level']
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'order', 'created_at']
    ordering = ['level', 'order', 'id']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取模块树形结构"""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': 'project 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        modules = UiModule.objects.filter(project_id=project_id, parent__isnull=True)
        serializer = self.get_serializer(modules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """
        移动模块：支持移动到另一个模块的之前、之后或作为其子模块。
        """
        from django.db.models import Max

        instance = self.get_object()
        project_id = instance.project_id
        target_id = request.data.get("target_id")
        drop_position = request.data.get("drop_position")  # -1 (before), 1 (after), 0 (inside)

        if drop_position is None:
            return Response(
                {"error": "参数 drop_position 必填。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            drop_position = int(drop_position)
            if drop_position not in [-1, 0, 1]:
                raise ValueError()
        except (TypeError, ValueError):
            return Response(
                {"error": "参数 drop_position 必须为 -1、0 或 1。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # 如果 target_id 为 None，说明移动到根节点层级
            if target_id is None:
                if drop_position == 0:
                    return Response(
                        {"error": "无法将模块拖入空位置中。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = None
                instance.level = 1
                instance.save()

                # 重新排序根节点模块
                root_modules = UiModule.objects.filter(
                    project_id=project_id, parent=None
                ).exclude(id=instance.id).order_by("order", "id")

                reordered = list(root_modules)
                reordered.append(instance)

                for index, m in enumerate(reordered, start=1):
                    m.order = index
                    m.save(update_fields=["order"])

                serializer = self.get_serializer(instance)
                return Response(serializer.data)

            # 如果 target_id 不为 None
            try:
                target_module = UiModule.objects.get(
                    id=target_id, project_id=project_id
                )
            except UiModule.DoesNotExist:
                return Response(
                    {"error": "目标模块不存在。"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 循环引用校验：目标模块不能是自己或自己的子模块
            descendant_ids = instance.get_all_descendant_ids()
            if target_module.id in descendant_ids:
                return Response(
                    {"error": "无法移动模块到自身或其子模块下。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if drop_position == 0:
                # 移动到目标模块内部，作为其子模块
                if target_module.level >= 5:
                    return Response(
                        {"error": "模块级别不能超过5级。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # 校验子树最大深度
                subtree_depth = instance.get_max_depth()
                if target_module.level + subtree_depth > 5:
                    return Response(
                        {"error": f"移动后模块层级将超过5级限制（当前子树深度: {subtree_depth}）。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = target_module
                instance.level = target_module.level + 1

                # 获取目标模块下已有子模块的最大 order
                max_order = UiModule.objects.filter(
                    parent=target_module
                ).aggregate(Max("order"))["order__max"] or 0

                instance.order = max_order + 1
                instance.save()

            else:
                # 移动到目标模块的前面或后面，成为同级模块
                parent = target_module.parent

                # 校验子树最大深度
                target_parent_level = target_module.parent.level if target_module.parent else 0
                subtree_depth = instance.get_max_depth()
                if target_parent_level + subtree_depth > 5:
                    return Response(
                        {"error": f"移动后模块层级将超过5级限制（当前子树深度: {subtree_depth}）。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = parent
                instance.level = target_module.level
                instance.save()

                # 重新排序所有同级模块
                siblings = UiModule.objects.filter(
                    project_id=project_id, parent=parent
                ).exclude(id=instance.id).order_by("order", "id")

                reordered = []
                for s in siblings:
                    if s.id == target_module.id and drop_position == -1:
                        reordered.append(instance)
                        reordered.append(s)
                    elif s.id == target_module.id and drop_position == 1:
                        reordered.append(s)
                        reordered.append(instance)
                    else:
                        reordered.append(s)

                # 防御，如果目标模块没在 siblings 里（理论上不可能）
                if instance not in reordered:
                    reordered.append(instance)

                for index, m in enumerate(reordered, start=1):
                    m.order = index
                    m.save(update_fields=["order"])

            serializer = self.get_serializer(instance)
            return Response(serializer.data)


class UiPageViewSet(viewsets.ModelViewSet):
    """页面管理视图"""
    queryset = UiPage.objects.select_related('project', 'module', 'creator')
    serializer_class = UiPageSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'module']
    search_fields = ['name', 'url']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UiPageDetailSerializer
        return UiPageSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='copy')
    def copy(self, request, pk=None):
        """复制页面，并复制页面下的元素。"""
        source = self.get_object()
        target_module_id = request.data.get('target_module_id') or request.data.get('module')

        if target_module_id:
            target_module = UiModule.objects.get(pk=target_module_id, project=source.project)
        else:
            target_module = source.module

        with transaction.atomic():
            base_name = request.data.get('name') or f'{source.name} - 副本'
            candidate_name = base_name
            suffix = 2
            while UiPage.objects.filter(project=source.project, module=target_module, name=candidate_name).exists():
                candidate_name = f'{base_name} {suffix}'
                suffix += 1

            copied_page = UiPage.objects.create(
                project=source.project,
                module=target_module,
                name=candidate_name,
                url=source.url,
                description=source.description,
                creator=request.user,
            )

            for element in source.elements.all():
                UiElement.objects.create(
                    page=copied_page,
                    name=element.name,
                    locator_type=element.locator_type,
                    locator_value=element.locator_value,
                    locator_index=element.locator_index,
                    locator_type_2=element.locator_type_2,
                    locator_value_2=element.locator_value_2,
                    locator_index_2=element.locator_index_2,
                    locator_type_3=element.locator_type_3,
                    locator_value_3=element.locator_value_3,
                    locator_index_3=element.locator_index_3,
                    wait_time=element.wait_time,
                    is_iframe=element.is_iframe,
                    iframe_locator=element.iframe_locator,
                    description=element.description,
                    creator=request.user,
                )

        serializer = self.get_serializer(copied_page)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UiElementViewSet(viewsets.ModelViewSet):
    """元素管理视图"""
    queryset = UiElement.objects.select_related('page', 'creator')
    serializer_class = UiElementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['page', 'locator_type', 'is_iframe']
    search_fields = ['name', 'locator_value']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        usage_count = instance.step_details.count()
        if usage_count:
            return Response(
                {'error': f'元素已被 {usage_count} 个页面步骤引用，无法删除。请先移除相关步骤中的元素引用'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class UiPageStepsViewSet(viewsets.ModelViewSet):
    """页面步骤管理视图"""
    queryset = UiPageSteps.objects.select_related('project', 'page', 'module', 'creator')
    serializer_class = UiPageStepsSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'page', 'module', 'status']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def get_queryset(self):
        """列表查询时排除大字段"""
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.defer('result_data', 'flow_data', 'run_flow', 'description')
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiPageStepsListSerializer
        if self.action == 'retrieve':
            return UiPageStepsDetailSerializer
        if self.action == 'execute_data':
            return UiPageStepsExecuteSerializer
        return UiPageStepsSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='copy')
    def copy(self, request, pk=None):
        """复制页面步骤，并复制其步骤详情。"""
        source = self.get_object()
        target_page_id = request.data.get('target_page_id') or request.data.get('page')

        if target_page_id:
            target_page = UiPage.objects.get(pk=target_page_id, project=source.project)
            target_module = target_page.module
        else:
            target_page = source.page
            target_module = source.module

        with transaction.atomic():
            base_name = request.data.get('name') or f'{source.name} - 副本'
            candidate_name = base_name
            suffix = 2
            while UiPageSteps.objects.filter(project=source.project, page=target_page, name=candidate_name).exists():
                candidate_name = f'{base_name} {suffix}'
                suffix += 1

            copied_step = UiPageSteps.objects.create(
                project=source.project,
                page=target_page,
                module=target_module,
                name=candidate_name,
                description=source.description,
                run_flow=source.run_flow,
                flow_data=deepcopy(source.flow_data or {}),
                file_ids=deepcopy(source.file_ids or []),
                status=0,
                result_data=None,
                creator=request.user,
            )
            sync_file_references(
                copied_step.file_ids or [],
                copied_step.project,
                FileReference.REF_UI_PAGE_STEPS,
                copied_step.id,
                request.user,
            )

            for detail in source.step_details.all().order_by('step_sort'):
                copied_detail = UiPageStepsDetailed.objects.create(
                    page_step=copied_step,
                    step_type=detail.step_type,
                    element=detail.element,
                    step_sort=detail.step_sort,
                    ope_key=detail.ope_key,
                    ope_value=deepcopy(detail.ope_value),
                    sql_execute=deepcopy(detail.sql_execute),
                    custom=deepcopy(detail.custom),
                    condition_value=deepcopy(detail.condition_value),
                    func=detail.func,
                    description=detail.description,
                )
                _sync_upload_step_file_reference(copied_detail, request.user)

        serializer = self.get_serializer(copied_step)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='execute-data')
    def execute_data(self, request, pk=None):
        """获取页面步骤执行数据（包含元素定位信息）"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class UiPageStepsDetailedViewSet(viewsets.ModelViewSet):
    """步骤详情管理视图"""
    queryset = UiPageStepsDetailed.objects.select_related('page_step', 'page_step__project', 'element')
    serializer_class = UiPageStepsDetailedSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['page_step', 'step_type']
    ordering_fields = ['step_sort', 'created_at']
    ordering = ['page_step', 'step_sort']

    def perform_create(self, serializer):
        instance = serializer.save()
        _sync_upload_step_file_reference(instance, self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        _sync_upload_step_file_reference(instance, self.request.user)

    def perform_destroy(self, instance):
        project = instance.page_step.project if instance.page_step_id and instance.page_step else None
        old_file_ids = _remove_upload_step_file_reference(instance, self.request.user)
        instance.delete()
        if old_file_ids and project:
            maybe_cleanup_unreferenced_files(project, candidate_file_ids=old_file_ids, reason='unbind')

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新步骤详情"""
        page_step_id = request.data.get('page_step')
        steps = request.data.get('steps', [])
        if not page_step_id:
            return Response({'error': 'page_step 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            qs = self.get_queryset().select_related('page_step', 'page_step__project').filter(page_step_id=page_step_id)
            submitted_ids = [s.get('id') for s in steps if s.get('id')]
            old_file_ids = []
            project = None

            # 仅删除被移除的步骤详情，对已提交的进行原地更新，
            # 避免重建改变主键 id 导致引用该步骤详情的用例 case_data 全部失效；
            # 同时同步维护上传文件引用，避免删除/更新步骤后遗留无效引用。
            removed_steps = list(qs.exclude(id__in=submitted_ids)) if submitted_ids else list(qs)
            for old_step in removed_steps:
                old_file_ids.extend(_remove_upload_step_file_reference(old_step, request.user))
                if project is None and old_step.page_step_id and old_step.page_step:
                    project = old_step.page_step.project
            if submitted_ids:
                qs.exclude(id__in=submitted_ids).delete()
            else:
                qs.delete()

            for idx, step_data in enumerate(steps):
                step_data['page_step'] = page_step_id
                step_data['step_sort'] = idx
                # 兼容 element_id 和 element 两种参数名
                if 'element_id' in step_data and 'element' not in step_data:
                    step_data['element'] = step_data.pop('element_id')
                sid = step_data.pop('id', None)
                instance = qs.filter(id=sid).first() if sid else None
                if instance:
                    if project is None and instance.page_step_id and instance.page_step:
                        project = instance.page_step.project
                    serializer = self.get_serializer(instance, data=step_data, partial=True)
                else:
                    serializer = self.get_serializer(data=step_data)
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()
                _sync_upload_step_file_reference(instance, request.user)
                if project is None and instance.page_step_id and instance.page_step:
                    project = instance.page_step.project

            if old_file_ids and project:
                maybe_cleanup_unreferenced_files(project, candidate_file_ids=old_file_ids, reason='unbind')
        return Response({'message': '批量更新成功'})


class UiTestCaseViewSet(viewsets.ModelViewSet):
    """测试用例管理视图"""
    queryset = UiTestCase.objects.select_related('project', 'module', 'creator')
    serializer_class = UiTestCaseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'module', 'level', 'status']
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时排除大字段"""
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.defer(
                'result_data', 'front_custom', 'front_sql', 'posterior_sql',
                'parametrize', 'case_flow', 'error_message', 'description'
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiTestCaseListSerializer
        if self.action == 'retrieve':
            return UiTestCaseDetailSerializer
        if self.action == 'execute_data':
            return UiTestCaseExecuteSerializer
        return UiTestCaseSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['get'], url_path='execute-data')
    def execute_data(self, request, pk=None):
        """获取测试用例执行数据（包含完整的步骤详情）"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='copy')
    def copy(self, request, pk=None):
        """复制 UI 自动化测试用例，并复制用例步骤。"""
        source = self.get_object()
        target_module_id = request.data.get('target_module_id') or request.data.get('module')

        if target_module_id:
            target_module = UiModule.objects.get(pk=target_module_id, project=source.project)
        else:
            target_module = source.module

        with transaction.atomic():
            base_name = request.data.get('name') or f'{source.name} - 副本'
            candidate_name = base_name
            suffix = 2
            while UiTestCase.objects.filter(project=source.project, module=target_module, name=candidate_name).exists():
                candidate_name = f'{base_name} {suffix}'
                suffix += 1

            copied_case = UiTestCase.objects.create(
                project=source.project,
                module=target_module,
                name=candidate_name,
                description=source.description,
                level=source.level,
                status=0,
                front_custom=deepcopy(source.front_custom or []),
                front_sql=deepcopy(source.front_sql or []),
                posterior_sql=deepcopy(source.posterior_sql or []),
                parametrize=deepcopy(source.parametrize or []),
                case_flow=source.case_flow,
                file_ids=deepcopy(source.file_ids or []),
                result_data=None,
                error_message=None,
                creator=request.user,
            )
            sync_file_references(
                copied_case.file_ids or [],
                copied_case.project,
                FileReference.REF_UI_TESTCASE,
                copied_case.id,
                request.user,
            )

            for case_step in source.case_steps.all().order_by('case_sort'):
                UiCaseStepsDetailed.objects.create(
                    test_case=copied_case,
                    page_step=case_step.page_step,
                    case_sort=case_step.case_sort,
                    case_data=deepcopy(case_step.case_data),
                    case_cache_data=deepcopy(case_step.case_cache_data),
                    case_cache_ass=deepcopy(case_step.case_cache_ass),
                    switch_step_open_url=case_step.switch_step_open_url,
                    error_retry=case_step.error_retry,
                    status=0,
                    error_message=None,
                    result_data=None,
                )

        serializer = self.get_serializer(copied_case)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request, **kwargs):
        """
        批量删除UI自动化测试用例
        POST请求体格式: {"ids": [1, 2, 3, 4]}
        """
        # 获取要删除的用例ID列表
        ids_data = request.data.get('ids', [])

        if not ids_data:
            return Response(
                {'error': '请提供要删除的用例ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证ID格式
        try:
            testcase_ids = [int(id) for id in ids_data]
        except (ValueError, TypeError):
            return Response(
                {'error': 'ids参数格式错误，应为数字列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not testcase_ids:
            return Response(
                {'error': '用例ID列表不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取当前查询集，确保数据隔离
        queryset = self.get_queryset()

        # 过滤出要删除的用例
        testcases_to_delete = queryset.filter(id__in=testcase_ids)

        # 检查是否所有请求的ID都存在
        found_ids = list(testcases_to_delete.values_list('id', flat=True))
        not_found_ids = [id for id in testcase_ids if id not in found_ids]

        if not_found_ids:
            return Response(
                {
                    'error': f'以下用例ID不存在: {not_found_ids}',
                    'not_found_ids': not_found_ids
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 记录删除前的信息用于返回
        deleted_testcases_info = []
        for testcase in testcases_to_delete:
            deleted_testcases_info.append({
                'id': testcase.id,
                'name': testcase.name,
                'module': testcase.module.name if testcase.module else None
            })

        # 执行批量删除
        try:
            with transaction.atomic():
                # 删除用例（关联的步骤会因为外键级联删除而自动删除）
                deleted_count, deleted_details = testcases_to_delete.delete()

                return Response({
                    'message': f'成功删除 {len(deleted_testcases_info)} 个UI自动化测试用例',
                    'deleted_count': len(deleted_testcases_info),
                    'deleted_testcases': deleted_testcases_info,
                    'deletion_details': deleted_details
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'删除过程中发生错误: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UiCaseStepsDetailedViewSet(viewsets.ModelViewSet):
    """用例步骤管理视图"""
    queryset = UiCaseStepsDetailed.objects.select_related('test_case', 'page_step')
    serializer_class = UiCaseStepsDetailedSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['test_case', 'status']
    ordering_fields = ['case_sort', 'created_at']
    ordering = ['test_case', 'case_sort']

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新用例步骤"""
        test_case_id = request.data.get('test_case')
        steps = request.data.get('steps', [])
        if not test_case_id:
            return Response({'error': 'test_case 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            qs = self.get_queryset().filter(test_case_id=test_case_id)
            submitted_ids = [s.get('id') for s in steps if s.get('id')]
            # 仅删除被移除的步骤，对已提交的进行原地更新，
            # 避免重建丢失 case_data 等未提交字段（数据填充被清空）
            if submitted_ids:
                qs.exclude(id__in=submitted_ids).delete()
            else:
                qs.delete()
            for idx, step_data in enumerate(steps):
                step_data['test_case'] = test_case_id
                step_data['case_sort'] = idx
                sid = step_data.pop('id', None)
                instance = qs.filter(id=sid).first() if sid else None
                if instance:
                    serializer = self.get_serializer(instance, data=step_data, partial=True)
                else:
                    serializer = self.get_serializer(data=step_data)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        return Response({'message': '批量更新成功'})


class UiExecutionRecordViewSet(viewsets.ModelViewSet):
    """执行记录管理视图"""
    queryset = UiExecutionRecord.objects.select_related('test_case', 'executor')
    serializer_class = UiExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {'test_case': ['exact'], 'status': ['exact'], 'trigger_type': ['exact'], 'test_case__project': ['exact']}
    ordering_fields = ['created_at', 'duration']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时排除大字段，支持 project 参数过滤"""
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(test_case__project_id=project_id)
        if self.action == 'list':
            return queryset.defer(
                'step_results', 'screenshots', 'trace_data', 'log',
                'error_message', 'environment'
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiExecutionRecordListSerializer
        return UiExecutionRecordSerializer

    def perform_create(self, serializer):
        serializer.save(executor=self.request.user)

    def perform_destroy(self, instance):
        """删除执行记录及其关联文件"""
        import os
        from django.conf import settings

        def safe_delete(path):
            if not path:
                return
            full_path = path if os.path.isabs(path) else os.path.join(settings.MEDIA_ROOT, path.lstrip('/'))
            if os.path.exists(full_path):
                os.remove(full_path)

        # 删除截图
        for screenshot in instance.screenshots or []:
            if isinstance(screenshot, str):
                safe_delete(screenshot.replace(settings.MEDIA_URL, ''))

        # 删除视频
        safe_delete(instance.video_path)

        # 删除 Trace 文件
        safe_delete(instance.trace_path)

        instance.delete()

    @action(detail=True, methods=['get'], url_path='trace')
    def get_trace_data(self, request, pk=None):
        """获取执行记录的 Trace 数据

        如果 trace_data 已解析则直接返回，否则尝试解析 trace_path
        可通过 ?refresh=1 强制重新解析
        """
        instance = self.get_object()
        refresh = request.query_params.get('refresh', '').lower() in ('1', 'true')

        # 如果已有解析数据且不需要刷新，直接返回
        if instance.trace_data and not refresh:
            return Response({
                'status': 'success',
                'data': instance.trace_data
            })

        # 尝试解析 trace 文件
        if not instance.trace_path:
            return Response({
                'status': 'error',
                'message': '此执行记录没有 Trace 数据'
            }, status=status.HTTP_404_NOT_FOUND)

        from .trace_parser import parse_trace_file
        import os
        from django.conf import settings

        # 构建完整路径
        trace_path = instance.trace_path
        if not os.path.isabs(trace_path):
            trace_path = os.path.join(settings.MEDIA_ROOT, trace_path)

        trace_data = parse_trace_file(trace_path)
        if not trace_data:
            return Response({
                'status': 'error',
                'message': 'Trace 文件解析失败'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 保存解析结果
        instance.trace_data = trace_data
        instance.save(update_fields=['trace_data'])

        return Response({
            'status': 'success',
            'data': trace_data
        })


class UiPublicDataViewSet(viewsets.ModelViewSet):
    """公共数据管理视图"""
    queryset = UiPublicData.objects.select_related('project', 'creator')
    serializer_class = UiPublicDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'type', 'is_enabled']
    search_fields = ['key']
    ordering_fields = ['key', 'created_at']
    ordering = ['project', 'key']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=False, methods=['get'], url_path='by-project/(?P<project_id>[^/.]+)')
    def by_project(self, request, project_id=None):
        """获取指定项目的所有启用公共数据（供执行器使用）

        返回格式（经 UnifiedResponseRenderer 包装后）:
        {"status": "success", "code": 200, "data": [{"key": "username", "value": "admin", "type": 0}, ...]}
        """
        public_data = UiPublicData.objects.filter(
            project_id=project_id,
            is_enabled=True
        ).values('key', 'value', 'type')
        # 直接返回列表，由 UnifiedResponseRenderer 统一包装为标准格式
        return Response(list(public_data))


class UiEnvironmentConfigViewSet(viewsets.ModelViewSet):
    """环境配置管理视图"""
    queryset = UiEnvironmentConfig.objects.select_related('project', 'creator')
    serializer_class = UiEnvironmentConfigSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'browser', 'headless', 'is_default']
    search_fields = ['name', 'base_url']
    ordering_fields = ['name', 'created_at']
    ordering = ['project', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class ActuatorViewSet(viewsets.ViewSet):
    """执行器管理视图"""
    permission_classes = []  # 公开访问，不需要特殊权限

    @action(detail=False, methods=['get'])
    def list_actuators(self, request):
        """获取所有在线执行器列表"""
        from .consumers import SocketUserManager

        actuators = []
        for actuator_id, consumer in SocketUserManager._actuator_users.items():
            actuator_info = getattr(consumer, 'actuator_info', {})
            actuators.append({
                'id': actuator_id,
                'name': actuator_info.get('name', actuator_id),
                'ip': actuator_info.get('ip', 'unknown'),
                'type': actuator_info.get('type', 'web_ui'),
                'is_open': actuator_info.get('is_open', True),
                'debug': actuator_info.get('debug', False),
                'browser_type': actuator_info.get('browser_type', 'chromium'),
                'headless': actuator_info.get('headless', False),
                'connected_at': actuator_info.get('connected_at'),
            })

        return Response({
            'status': 'success',
            'data': {
                'count': len(actuators),
                'items': actuators
            }
        })

    @action(detail=False, methods=['get'])
    def status(self, request):
        """获取执行器状态统计"""
        from .consumers import SocketUserManager

        return Response({
            'status': 'success',
            'data': {
                'total_actuators': SocketUserManager.get_actuator_count(),
                'has_available': SocketUserManager.has_actuator(),
                'web_users': len(SocketUserManager._web_users),
            }
        })


class UiBatchExecutionRecordViewSet(viewsets.ModelViewSet):
    """批量执行记录管理视图"""
    queryset = UiBatchExecutionRecord.objects.select_related('executor')
    serializer_class = UiBatchExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'trigger_type']
    ordering_fields = ['created_at', 'duration', 'total_cases']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时不预加载执行记录，支持 project 参数过滤"""
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(execution_records__test_case__project_id=project_id).distinct()
        # 详情时预加载执行记录
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('execution_records', 'execution_records__test_case')
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UiBatchExecutionRecordDetailSerializer
        return UiBatchExecutionRecordSerializer

    def perform_destroy(self, instance):
        """删除批量执行记录及其关联的执行记录"""
        instance.execution_records.all().delete()
        instance.delete()


# ---------- 截图上传 ----------
import os
import uuid
from datetime import datetime
from django.conf import settings
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated


from rest_framework.permissions import AllowAny


@api_view(['POST'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_screenshot(request):
    """上传执行截图，返回可访问 URL

    注意：此接口使用 Bearer Token 认证
    执行器通过 /api/token/ 获取 JWT Token 后调用此接口
    """
    file = request.FILES.get('file')
    if not file:
        return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)

    # 保存到 media/ui_screenshots/{日期}/
    date_dir = datetime.now().strftime('%Y%m%d')
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'ui_screenshots', date_dir)
    os.makedirs(upload_dir, exist_ok=True)

    # 生成唯一文件名
    ext = os.path.splitext(file.name)[1] or '.png'
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)

    url = f"{settings.MEDIA_URL}ui_screenshots/{date_dir}/{filename}"
    return Response({'status': 'success', 'url': url}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_trace(request):
    """上传 Playwright Trace 文件，返回可访问 URL

    注意：此接口使用 Bearer Token 认证
    执行器执行完成后调用此接口上传 trace.zip 文件
    """
    file = request.FILES.get('file')
    if not file:
        return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)

    # 保存到 media/ui_traces/{日期}/
    date_dir = datetime.now().strftime('%Y%m%d')
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'ui_traces', date_dir)
    os.makedirs(upload_dir, exist_ok=True)

    # 生成唯一文件名
    ext = os.path.splitext(file.name)[1] or '.zip'
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)

    # 返回相对路径（用于存储到数据库）和 URL（用于下载）
    relative_path = f"ui_traces/{date_dir}/{filename}"
    url = f"{settings.MEDIA_URL}{relative_path}"
    return Response({
        'status': 'success',
        'url': url,
        'path': relative_path
    }, status=status.HTTP_201_CREATED)


# ---------- 内部触发批量执行（供 Celery 任务调用） ----------
from asgiref.sync import async_to_sync


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_batch_execution(request):
    """内部 API：创建批量执行记录并通过 WebSocket 发送给执行器

    请求体:
        case_ids: list[int] - 用例 ID 列表
        actuator_id: str - 执行器 ID
        batch_name: str - 批次名称（可选）
        trigger_type: str - 触发类型（默认 scheduled）
    """
    from .consumers import SocketUserManager
    from .socket_models import SocketDataModel, QueueModel, NoticeType, ResponseCode, UiSocketEnum

    case_ids = request.data.get('case_ids', [])
    actuator_id = request.data.get('actuator_id', '')
    batch_name = request.data.get('batch_name', '')
    trigger_type = request.data.get('trigger_type', 'scheduled')

    if not case_ids:
        return Response({'error': '未提供用例 ID'}, status=status.HTTP_400_BAD_REQUEST)

    # 查找执行器
    if actuator_id:
        actuator = SocketUserManager.get_actuator_by_id(actuator_id)
    else:
        actuator = SocketUserManager.get_actuator()

    if not actuator:
        return Response(
            {'error': f'执行器 {actuator_id} 不在线' if actuator_id else '没有可用的执行器'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # 创建批量执行记录
    from django.utils import timezone as tz
    case_names = list(UiTestCase.objects.filter(id__in=case_ids).values_list('name', flat=True)[:3])
    if not batch_name:
        batch_name = f"定时任务: {', '.join(case_names)}"
        if len(case_ids) > 3:
            batch_name += f" 等{len(case_ids)}个用例"

    batch = UiBatchExecutionRecord.objects.create(
        name=batch_name,
        total_cases=len(case_ids),
        status=1,
        trigger_type=trigger_type,
        executor=request.user,
        start_time=tz.now(),
    )

    args = {
        'case_ids': case_ids,
        'actuator_id': actuator_id,
        'batch_id': batch.id,
    }

    # 通过 WebSocket 发送给执行器
    async_to_sync(actuator.send_json)(SocketDataModel(
        code=ResponseCode.SUCCESS,
        msg='execute_batch',
        user='system',
        is_notice=NoticeType.ACTUATOR,
        data=QueueModel(
            func_name=UiSocketEnum.TEST_CASE_BATCH,
            func_args=args,
        ),
    ))

    return Response({
        'status': 'success',
        'data': {'batch_id': batch.id, 'total_cases': len(case_ids)},
    })
