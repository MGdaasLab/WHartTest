# -*- coding: utf-8 -*-
"""UI 自动化视图"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('ui_automation')

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models.deletion import ProtectedError
from django.db.models import Count
from django.db import transaction
from copy import deepcopy
from file_management.services import maybe_cleanup_unreferenced_files, sync_file_references

from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiPublicData, UiEnvironmentConfig,
    UiBatchExecutionRecord, UiAuthState
)
from file_management.models import FileReference
from .serializers import (
    UiModuleSerializer, UiPageSerializer, UiPageDetailSerializer,
    UiElementSerializer, UiPageStepsSerializer, UiPageStepsListSerializer, UiPageStepsDetailSerializer,
    UiPageStepsDetailedSerializer, UiTestCaseSerializer, UiTestCaseListSerializer, UiTestCaseDetailSerializer,
    UiCaseStepsDetailedSerializer, UiExecutionRecordSerializer, UiExecutionRecordListSerializer,
    UiPublicDataSerializer, UiEnvironmentConfigSerializer, UiAuthStateSerializer,
    UiTestCaseExecuteSerializer, UiPageStepsExecuteSerializer, UiBatchExecutionRecordSerializer,
    UiBatchExecutionRecordDetailSerializer
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
        # 显式检查：页面下存在步骤集合时，需先删除步骤
        step_count = instance.page_steps.count()
        if step_count:
            return Response(
                {'error': f'页面下存在 {step_count} 个页面步骤，无法删除页面。请先删除页面下的步骤'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # 显式检查：页面下的元素被页面步骤引用时，不允许删除页面
        element_usage = UiPageStepsDetailed.objects.filter(element__page=instance).count()
        if element_usage:
            return Response(
                {'error': f'页面下的元素已被 {element_usage} 个页面步骤引用，无法删除页面。请先删除引用这些元素的步骤'},
                status=status.HTTP_400_BAD_REQUEST
            )
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

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除元素。POST: {"ids": [1, 2]}；被页面步骤引用的元素拒绝删除。"""
        ids = request.data.get('ids') or []
        if not ids:
            return Response({'error': 'ids 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            elements = list(UiElement.objects.filter(id__in=ids).annotate(
                usage=Count('step_details'),
            ))
            if not elements:
                return Response({'deleted': 0, 'blocked': []})
            blocked = [(e.id, e.name, e.usage) for e in elements if e.usage]
            if blocked:
                detail = '、'.join(f'「{name}」（被 {usage} 个步骤引用）' for _, name, usage in blocked[:10])
                return Response(
                    {'error': f'以下元素存在引用无法删除：{detail}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            deleted_ids = [e.id for e in elements]
            UiElement.objects.filter(id__in=deleted_ids).delete()
        return Response({'deleted': len(deleted_ids), 'blocked': []})


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
        # 显式检查：被测试用例引用时不允许删除步骤
        usage_count = instance.case_usages.count()
        if usage_count:
            return Response(
                {'error': f'步骤已被 {usage_count} 个测试用例引用，无法删除。请先删除引用该步骤的测试用例'},
                status=status.HTTP_400_BAD_REQUEST
            )
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

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除步骤明细。POST: {"ids": [1, 2]}；同步清理附件引用。"""
        ids = request.data.get('ids') or []
        if not ids:
            return Response({'error': 'ids 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            qs = self.get_queryset().select_related('page_step', 'page_step__project').filter(id__in=ids)
            old_file_ids = []
            project = None
            for step in qs:
                old_file_ids.extend(_remove_upload_step_file_reference(step, request.user))
                if project is None and step.page_step_id and step.page_step:
                    project = step.page_step.project
            deleted_count = qs.delete()[0]
            if old_file_ids and project:
                maybe_cleanup_unreferenced_files(project, candidate_file_ids=old_file_ids, reason='unbind')
        return Response({'deleted': deleted_count})

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
    filterset_fields = ['project', 'is_default']
    search_fields = ['name', 'base_url']
    ordering_fields = ['name', 'created_at']
    ordering = ['project', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class UiAuthStateViewSet(viewsets.ModelViewSet):
    """环境登录态管理视图（登录态绑定环境配置，执行时按环境自动注入）"""
    queryset = UiAuthState.objects.select_related('env_config', 'creator')
    serializer_class = UiAuthStateSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['env_config', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['updated_at', 'created_at']
    ordering = ['-updated_at']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def perform_update(self, serializer):
        # 登录态注入仅由"是否显式选择绑定"决定，不再维护"环境生效登录态"互斥
        serializer.save()

# 注意：刻意不含 client_cert_passphrase —— 客户端证书口令不下发、不回传、不落盘，
# 只能由执行器本机的 config.toml / 环境变量提供。
_ACTUATOR_CONFIG_FIELDS = frozenset({
    'name', 'browser_type', 'persistent', 'launch_timeout', 'action_timeout',
    'retry_count', 'step_interval', 'max_concurrent', 'log_level',
    'trace_enabled', 'trace_screenshots', 'trace_snapshots', 'trace_sources',
    'headless', 'viewport_width', 'viewport_height', 'fail_fast',
    'client_cert_enabled', 'client_cert_pfx_path', 'client_cert_cert_path',
    'client_cert_key_path', 'client_cert_origins',
})


class ActuatorViewSet(viewsets.ViewSet):
    """执行器管理视图"""
    permission_classes = []  # 公开访问，不需要特殊权限

    def get_permissions(self):
        """config 为写操作，需要登录；其余保持公开"""
        if self.action == 'config':
            return [IsAuthenticated()]
        return []

    @action(detail=False, methods=['get'])
    def list_actuators(self, request):
        """获取所有在线执行器列表"""
        from .consumers import SocketUserManager

        from .actuator_registry import list_capabilities

        actuators = []
        for cap in list_capabilities():
            # preserve raw extras
            raw = SocketUserManager.get_actuator_info(cap['id']) or {}
            item = {
                'id': cap['id'],
                'name': cap.get('name') or cap['id'],
                'ip': raw.get('ip', 'unknown'),
                'type': raw.get('type', 'web_ui'),
                'is_open': cap.get('is_open', True),
                'debug': raw.get('debug', False),
                'browser_type': cap.get('browser_type') or cap.get('default_browser'),
                'headless': raw.get('headless', False),
                'supported_browsers': cap.get('supported_browsers') or [],
                'default_browser': cap.get('default_browser'),
                'supports_headed': cap.get('supports_headed', True),
                'supports_headless': cap.get('supports_headless', True),
                'max_slots': cap.get('max_slots', 1),
                'busy_slots': cap.get('busy_slots', 0),
                'version': raw.get('version') or cap.get('version'),
                'os': cap.get('os'),
                'labels': cap.get('labels') or [],
                'connected_at': raw.get('connected_at'),
                # 运行配置（供编辑弹窗预填）
                'persistent': raw.get('persistent', True),
                'launch_timeout': raw.get('launch_timeout', 30),
                'action_timeout': raw.get('action_timeout', 30),
                'retry_count': raw.get('retry_count', 3),
                'step_interval': raw.get('step_interval', 500),
                'fail_fast': raw.get('fail_fast', False),
                'log_level': raw.get('log_level', 'INFO'),
                'trace_enabled': raw.get('trace_enabled', True),
                'trace_screenshots': raw.get('trace_screenshots', True),
                'trace_snapshots': raw.get('trace_snapshots', True),
                'trace_sources': raw.get('trace_sources', False),
                'headless': raw.get('headless', False),
                'viewport_width': raw.get('viewport_width', 1280),
                'viewport_height': raw.get('viewport_height', 720),
                'in_container': raw.get('in_container', False),
                # HTTPS 客户端证书（供编辑弹窗预填）。
                # 必须回填：前端用 record.x ?? '' 初始化表单，拿不到值时会提交空串，
                # 而 config 接口的过滤是「value is not None」（空串放行），会误清执行器上已配置的路径。
                'client_cert_enabled': bool(raw.get('client_cert_enabled', False)),
                'client_cert_pfx_path': raw.get('client_cert_pfx_path') or '',
                'client_cert_cert_path': raw.get('client_cert_cert_path') or '',
                'client_cert_key_path': raw.get('client_cert_key_path') or '',
                'client_cert_origins': raw.get('client_cert_origins') or '',
            }
            actuators.append(item)

        return Response({
            'status': 'success',
            'data': {
                'count': len(actuators),
                'items': actuators
            }
        })

    @action(detail=False, methods=['post'])
    def config(self, request):
        """保存执行器配置：更新 registry 并实时下发到执行器"""
        from .consumers import SocketUserManager
        from .actuator_registry import update_capability
        from .socket_models import (
            SocketDataModel, QueueModel, NoticeType, ResponseCode, UiSocketEnum,
        )
        from asgiref.sync import async_to_sync

        actuator_id = request.data.get('actuator_id')
        config = request.data.get('config')
        if not actuator_id:
            return Response({'error': 'actuator_id 必填'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(config, dict) or not config:
            return Response({'error': 'config 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        consumer = SocketUserManager.get_actuator_by_id(str(actuator_id))
        if not consumer:
            return Response(
                {'error': f'执行器 {actuator_id} 不在线'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 只允许编辑白名单字段
        normalized = {}
        for key, value in config.items():
            if key in _ACTUATOR_CONFIG_FIELDS and value is not None:
                normalized[key] = value

        # 校验浏览器类型在支持列表内
        if 'browser_type' in normalized:
            supported = consumer.actuator_info.get('supported_browsers') or []
            if normalized['browser_type'] not in supported:
                return Response(
                    {
                        'error': (
                            f'执行器不支持浏览器类型 {normalized["browser_type"]}，'
                            f'支持: {", ".join(supported) or "无"}'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 数值范围校验
        int_ranges = {
            'launch_timeout': (10, 120),
            'action_timeout': (5, 60),
            'retry_count': (0, 10),
            'step_interval': (0, 60000),
            'max_concurrent': (1, 20),
            'viewport_width': (320, 3840),
            'viewport_height': (240, 2160),
        }
        for key, (lo, hi) in int_ranges.items():
            if key in normalized:
                try:
                    value = int(normalized[key])
                except (TypeError, ValueError):
                    return Response(
                        {'error': f'{key} 必须是整数'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not lo <= value <= hi:
                    return Response(
                        {'error': f'{key} 必须在 {lo}-{hi} 之间'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                normalized[key] = value

        if 'log_level' in normalized and normalized['log_level'].upper() not in (
            'DEBUG', 'INFO', 'WARNING', 'ERROR',
        ):
            return Response(
                {'error': 'log_level 必须是 DEBUG/INFO/WARNING/ERROR 之一'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for key in ('persistent', 'trace_enabled', 'trace_screenshots', 'trace_snapshots', 'trace_sources', 'headless', 'client_cert_enabled', 'fail_fast'):
            if key in normalized:
                normalized[key] = bool(normalized[key])

        # 执行器名称校验
        if 'name' in normalized:
            name = str(normalized['name']).strip()
            if not name or len(name) > 50:
                return Response(
                    {'error': '执行器名称不能为空且不能超过50个字符'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            normalized['name'] = name

        # 更新 registry，使列表立即反映新配置
        try:
            update_capability(str(actuator_id), normalized)
        except Exception as exc:
            return Response({'error': f'更新执行器配置失败: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 实时下发到执行器
        try:
            async_to_sync(consumer.send_json)(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="set_config",
                user=request.user.username if request.user.is_authenticated else None,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.SET_ACTUATOR_CONFIG,
                    func_args=normalized,
                )
            ))
        except Exception as exc:
            return Response(
                {'error': f'配置已保存但下发失败: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'status': 'success', 'data': normalized})

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

    from . import actuator_registry
    from .models import UiEnvironmentConfig

    env_config_id = request.data.get('env_config_id')
    run_options = request.data.get('run_options') or {}

    env = None
    if env_config_id:
        env = UiEnvironmentConfig.objects.filter(id=env_config_id).first()
        if env is None:
            return Response(
                {'error': f'环境配置 {env_config_id} 不存在'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    effective, selected, err = actuator_registry.resolve_and_select(
        env=env,
        run_options=run_options if run_options else None,
        preferred_actuator_id=actuator_id or None,
    )
    if err:
        return Response({'error': err}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    actuator = actuator_registry.get_raw_consumer(selected['id'])
    if not actuator:
        return Response({'error': f"执行器 {selected['id']} 不在线"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    actuator_id = selected['id']
    ttl = None
    try:
        timeout_ms = int((effective or {}).get("timeout") or 0)
    except (TypeError, ValueError):
        timeout_ms = 0
    if timeout_ms > 0:
        ttl = max(15 * 60, min(int(timeout_ms / 1000) * 3 * max(len(case_ids), 1), 6 * 60 * 60))
    ok, err = actuator_registry.reserve_slots(
        actuator_id,
        len(case_ids),
        ttl_seconds=ttl,
        meta={"case_ids": case_ids, "trigger": "http_trigger_batch"},
    )
    if not ok:
        return Response({'error': err}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # 创建批量执行记录
    from django.utils import timezone as tz

    reserved_count = len(case_ids)
    batch = None
    try:
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

        # 批量执行不展示执行画面：强制无头（执行器优先采用下发的 effective_runtime）
        if isinstance(effective, dict) and effective.get("browser"):
            effective["headless"] = True
        if isinstance(run_options, dict):
            run_options["headless"] = True

        args = {
            'case_ids': case_ids,
            'actuator_id': actuator_id,
            'batch_id': batch.id,
            'executor_id': request.user.id,
            'env_config_id': env_config_id,
            'run_options': run_options or None,
            'effective_runtime': effective,
            'trigger_type': trigger_type,
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
    except Exception:
        actuator_registry.adjust_busy_slots(actuator_id, -reserved_count)
        if batch is not None:
            batch.status = 4  # all failed
            batch.end_time = tz.now()
            if batch.start_time:
                batch.duration = (batch.end_time - batch.start_time).total_seconds()
            batch.save(update_fields=['status', 'end_time', 'duration'])
        raise

    return Response({
        'status': 'success',
        'data': {
            'batch_id': batch.id,
            'total_cases': len(case_ids),
            'actuator_id': actuator_id,
            'effective_runtime': effective,
        },
    })


# ---------------------------------------------------------------------------
# 录制器会话（Playwright 无头浏览器录制，方案：截图帧流式）
# ---------------------------------------------------------------------------

_DEFAULT_RECORDER_VIEWPORT = {'width': 1400, 'height': 900}


def _resolve_recorder_skill_dir() -> str:
    """定位 playwright npm 依赖所在目录（录制器运行目录）。

    优先级：环境变量 RECORDER_SKILL_DIR（兼容旧配置）> 录制器自身目录
    （ui_automation/recorder/，自带 package.json，首次自动 npm install）>
    DB 中已部署的 playwright skill > 仓库内 WHartTest_Skills 兜底。
    录制器不再依赖可卸载的 skill 资产。
    """
    env_dir = os.environ.get('RECORDER_SKILL_DIR', '').strip()
    if env_dir and os.path.isdir(env_dir):
        return env_dir

    own_dir = Path(__file__).parent / 'recorder'
    if (own_dir / 'package.json').is_file():
        return str(own_dir)

    try:
        from skills.models import Skill
        skill = (
            Skill.objects.filter(name__in=['playwright-skill', 'playwright-cli'], is_active=True)
            .order_by('id')
            .first()
        )
        if skill:
            full = skill.get_full_path()
            if full and os.path.isdir(full):
                return full
    except Exception:
        pass  # skills 应用不可用/被移除时忽略

    fallback = Path(settings.BASE_DIR).parent / 'WHartTest_Skills' / 'playwright-skill'
    if fallback.is_dir():
        return str(fallback)
    return ''


def _parse_opt_int(value):
    """请求参数转 int，空/非法返回 None（避免各处重复 try）。"""
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _auth_state_by_id(auth_state_id):
    """按 id 取登录态快照（录制表单选择的绑定登录态），无效返回 None。"""
    if not auth_state_id:
        return None
    state = UiAuthState.objects.filter(id=auth_state_id).first()
    if state is None or not isinstance(state.state_json, dict):
        return None
    return state

def _start_recorder_session(env_config, page, base_url, skill_dir, request, meta):
    """创建录制会话并启动浏览器（含可选前置步骤执行）。

    失败时关闭会话并抛出 RecorderSessionError（detail 可直接展示给用户）。
    返回 (session_id, viewport, pre_result)。
    """
    from .recorder.session_manager import (
        recorder_manager, RecorderSessionError,
    )

    session = recorder_manager.create_session(
        user_id=request.user.username,
        project_id=env_config.project_id,
        skill_dir=skill_dir,
    )
    recorder_manager.set_meta(session.session_id, meta)
    session_id = session.session_id
    try:
        session.start(timeout=120)
        # 仅当录制表单选择了绑定登录态时才注入；清空选择框 → 无痕启动（不注入任何登录态）
        storage_state = None
        if meta.auth_state_id:
            bound = _auth_state_by_id(meta.auth_state_id)
            if bound is not None:
                storage_state = bound.state_json
                logger.info(
                    '录制器注入绑定登录态（auth_state_id=%s）', meta.auth_state_id,
                )
            else:
                logger.info(
                    '绑定登录态无效（auth_state_id=%s），录制器按无痕上下文启动', meta.auth_state_id,
                )
        start_params = {
            'url': base_url,
            'viewport': meta.viewport,
        }
        if storage_state:
            start_params['storage_state'] = storage_state
        result = session.request('start', start_params, timeout=90)
    except RecorderSessionError:
        recorder_manager.close(session_id, graceful=False)
        raise

    # 执行前置步骤（自动完成登录等可复用操作，执行过程不进入录制动作）
    pre_result = {'executed': 0, 'failed': False}
    if meta.pre_page_step_id:
        pre_page_step = UiPageSteps.objects.filter(id=meta.pre_page_step_id).first()
        if pre_page_step is None:
            recorder_manager.close(session_id, graceful=False)
            raise RecorderSessionError('前置步骤不存在或不属于当前项目')
        pre_steps = _serialize_page_step_for_recorder(pre_page_step)
        try:
            pre_resp = session.request(
                'run_steps', {'steps': pre_steps}, timeout=180,
            )
            pre_result = {
                'executed': pre_resp.get('state', {}).get('executed', 0),
                'failed': pre_resp.get('state', {}).get('failed', False),
            }
            # 不再重建页面：reset_page 会关闭当前页并重新导航，清空前置步骤
            # 已填写的表单值（如登录页账号输入）。页面的滚动/弹层残留已由
            # 录制器 run_steps 结束时的"归位"（Escape/滚顶/失焦）清理。
        except RecorderSessionError:
            recorder_manager.close(session_id, graceful=False)
            raise

    viewport = result.get('state', {}).get('viewport') or meta.viewport
    return session_id, viewport, pre_result


def _serialize_page_step_for_recorder(page_step: UiPageSteps) -> list[dict]:
    """把页面步骤序列化为录制器可执行的动作列表（含元素定位）。

    上传步骤（ope_key=upload）解析附件为本地可访问路径（file_path），
    录制器 run_steps 用 setInputFiles 执行。
    """
    from file_management.services import validate_file_ids, serialize_file_for_runtime
    steps = []
    details = (
        UiPageStepsDetailed.objects.filter(page_step=page_step)
        .select_related('element')
        .order_by('step_sort')
    )
    for detail in details:
        selector = None
        if detail.element is not None:
            selector = {
                'locator_type': detail.element.locator_type,
                'locator_value': detail.element.locator_value,
                'locator_index': detail.element.locator_index,
            }
            # 备用定位器：主定位 strict 冲突/失效时回退（与执行器降级链一致）
            if detail.element.locator_type_2 and detail.element.locator_value_2:
                selector['locator_type_2'] = detail.element.locator_type_2
                selector['locator_value_2'] = detail.element.locator_value_2
                selector['locator_index_2'] = detail.element.locator_index_2
            if detail.element.locator_type_3 and detail.element.locator_value_3:
                selector['locator_type_3'] = detail.element.locator_type_3
                selector['locator_value_3'] = detail.element.locator_value_3
                selector['locator_index_3'] = detail.element.locator_index_3
            # iframe 元素：录制器执行步骤时按链式 frame 定位下钻
            if detail.element.is_iframe and detail.element.iframe_locator:
                selector['is_iframe'] = True
                selector['iframe_locator'] = detail.element.iframe_locator
        ope_value = dict(detail.ope_value or {})
        if detail.ope_key == 'upload' and ope_value.get('file_id'):
            # 与执行器 execute-data 同规则：解析附件为本地路径
            try:
                project = detail.page_step.project if detail.page_step else None
                files = validate_file_ids([ope_value['file_id']], project, None)
                if files:
                    runtime_file = serialize_file_for_runtime(files[0])
                    resolved = runtime_file.get('path') or ''
                    if resolved:
                        ope_value['file_path'] = resolved
                        ope_value['value'] = resolved
                        ope_value['file_name'] = runtime_file.get('name') or ope_value.get('file_name')
                        ope_value['mime_type'] = runtime_file.get('mime_type')
            except Exception as exc:
                logger.warning('录制器上传步骤解析文件失败: %s', exc, exc_info=True)
        steps.append({
            'ope_key': detail.ope_key,
            'ope_value': ope_value,
            'step_type': detail.step_type,
            'element': selector,
            # 与执行器 description 同源：元素名称（回退步骤描述），执行记录步骤名展示用
            'element_name': (detail.element.name if detail.element is not None else None),
            'description': detail.description or (detail.element.name if detail.element is not None else ''),
        })
    return steps


class UiRecorderSessionViewSet(viewsets.ViewSet):
    """录制会话生命周期：创建（启动浏览器）/ 结束（存脚本+解析入库）/ 取消。"""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _owner_ok(request, meta) -> bool:
        return meta.user_id == request.user.username or request.user.is_superuser

    def create(self, request):
        """POST recorder-sessions/
        {env_config_id, page_id, page_step_id, create_elements, create_steps}
        """
        from .recorder.session_manager import (
            recorder_manager, RecorderSessionError, RecorderSessionMeta,
        )

        env_config = UiEnvironmentConfig.objects.filter(
            id=request.data.get('env_config_id')
        ).first()
        if env_config is None:
            return Response({'detail': '请选择有效的环境配置'}, status=status.HTTP_400_BAD_REQUEST)

        page = UiPage.objects.filter(id=request.data.get('page_id'), project=env_config.project).first()
        if page is None:
            return Response({'detail': '请选择当前项目下的页面'}, status=status.HTTP_400_BAD_REQUEST)

        page_step = UiPageSteps.objects.filter(
            id=request.data.get('page_step_id'),
            project=env_config.project,
            page=page,
        ).first()
        if page_step is None:
            return Response({'detail': '请选择当前页面下的页面步骤'}, status=status.HTTP_400_BAD_REQUEST)

        base_url = (env_config.base_url or page.url or '').strip()
        if not base_url:
            return Response(
                {
                    'detail': (
                        f'所选环境「{env_config.name}」未配置 base_url，且页面「{page.name}」也未配置 url，'
                        '无法确定录制导航地址。请先在环境配置中填写 base_url（录制优先使用环境地址），'
                        '或填写页面 url。'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        skill_dir = _resolve_recorder_skill_dir()
        if not skill_dir:
            return Response(
                {'detail': '未找到 playwright skill 目录（可设置环境变量 RECORDER_SKILL_DIR）'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 前置步骤（可选）：录制前自动执行的可复用页面步骤（如登录）
        pre_page_step = None
        pre_step_id = request.data.get('pre_page_step_id')
        if pre_step_id not in (None, ''):
            pre_page_step = UiPageSteps.objects.filter(
                id=pre_step_id, project=env_config.project,
            ).first()
            if pre_page_step is None:
                return Response(
                    {'detail': '前置步骤不存在或不属于当前项目'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        session_id = None
        meta = RecorderSessionMeta(
            user_id=request.user.username,
            project_id=env_config.project_id,
            page_id=page.id,
            page_step_id=page_step.id,
            # 录制结束后必定创建页面元素与页面步骤
            create_elements=True,
            create_steps=True,
            base_url=base_url,
            viewport=_DEFAULT_RECORDER_VIEWPORT,
            kind='record',
            pre_page_step_id=(
                int(pre_step_id) if pre_step_id not in (None, '') else None
            ),
            env_config_id=env_config.id,
            auth_state_id=_parse_opt_int(request.data.get('auth_state_id')),
        )

        try:
            session_id, viewport, pre_result = _start_recorder_session(
                env_config=env_config,
                page=page,
                base_url=base_url,
                skill_dir=skill_dir,
                request=request,
                meta=meta,
            )
        except RecorderSessionError as exc:
            return Response({'detail': f'启动录制失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'session_id': session_id,
            'viewport': viewport,
            'base_url': base_url,
            'page_id': page.id,
            'page_step_id': page_step.id,
            'pre_executed': pre_result.get('executed', 0),
            'pre_failed': pre_result.get('failed', False),
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        """POST recorder-sessions/{id}/finish/
        停止录制 → 动作解析入库（record 模式：动作全部解析到所选页面步骤下）。
        """
        from .recorder.session_manager import (
            recorder_manager, RecorderSessionError,
        )
        from .recorder_apply import apply_recorded_actions

        session_id = pk
        session = recorder_manager.get(session_id)
        meta = recorder_manager.get_meta(session_id)
        if session is None or meta is None or not self._owner_ok(request, meta):
            return Response({'detail': '录制会话不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = session.request('finish', {}, timeout=30)
        except RecorderSessionError as exc:
            recorder_manager.close(session_id, graceful=False)
            return Response({'detail': f'结束录制失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

        actions = result.get('state', {}).get('actions') or []

        # ---------- record 模式：动作解析到所选页面步骤下 ----------
        apply_stats = {
            'elements_created': 0,
            'elements_updated': 0,
            'steps_created': 0,
        }
        if (meta.create_elements or meta.create_steps) and meta.page_step_id:
            page = UiPage.objects.filter(id=meta.page_id).first()
            page_step = UiPageSteps.objects.filter(id=meta.page_step_id).first()
            if page and page_step:
                apply_stats = apply_recorded_actions(
                    page=page,
                    page_step=page_step,
                    user=request.user,
                    actions=actions,
                    auth_state_id=meta.auth_state_id,  # 录制表单选择的登录态：绑定到所选步骤
                )

        recorder_manager.close(session_id)
        return Response({
            'message': '录制完成',
            'actions_count': len(actions),
            **apply_stats,
        })

    @action(detail=False, methods=['post'], url_path='auth-capture')
    def auth_capture(self, request):
        """POST recorder-sessions/auth-capture/
        登录态录制会话：无痕启动浏览器导航到环境登录页，仅暴露"保存登录态"，
        保存后会话由 cancel 关闭。不注入既有登录态（本次就是要录登录流程）。
        """
        from .recorder.session_manager import (
            recorder_manager, RecorderSessionError, RecorderSessionMeta,
        )
        env_config = UiEnvironmentConfig.objects.filter(
            id=request.data.get('env_config_id')
        ).first()
        if env_config is None:
            return Response({'detail': '请选择有效的环境配置'}, status=status.HTTP_400_BAD_REQUEST)
        skill_dir = _resolve_recorder_skill_dir()
        if not skill_dir:
            return Response(
                {'detail': '未找到 playwright skill 目录（可设置环境变量 RECORDER_SKILL_DIR）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        meta = RecorderSessionMeta(
            user_id=request.user.username,
            project_id=env_config.project_id,
            page_id=None,
            page_step_id=None,
            create_elements=False,
            create_steps=False,
            base_url=env_config.base_url or '',
            viewport=_DEFAULT_RECORDER_VIEWPORT,
            kind='auth',
            env_config_id=env_config.id,
        )
        try:
            session_id, viewport, _pre = _start_recorder_session(
                env_config=env_config,
                page=None,
                base_url=env_config.base_url or '',
                skill_dir=skill_dir,
                request=request,
                meta=meta,
            )
        except RecorderSessionError as exc:
            return Response({'detail': f'启动录制失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'session_id': session_id,
            'viewport': viewport,
            'base_url': env_config.base_url or '',
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST recorder-sessions/{id}/cancel/ 取消录制，释放浏览器进程。"""
        from .recorder.session_manager import recorder_manager

        session_id = pk
        session = recorder_manager.get(session_id)
        meta = recorder_manager.get_meta(session_id)
        if session is None or meta is None or not self._owner_ok(request, meta):
            return Response({'detail': '录制会话不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)
        recorder_manager.close(session_id, graceful=False)
        return Response({'message': '录制已取消'})

    @action(detail=True, methods=['post'], url_path='save-login-state')
    def save_login_state(self, request, pk=None):
        """POST recorder-sessions/{id}/save-login-state/
        保存当前录制浏览器上下文登录态，绑定到录制会话所属的环境配置。
        同环境旧登录态自动停用（每环境一份生效登录态），执行时由执行器
        按环境自动拉取注入。
        """
        from .recorder.session_manager import (
            recorder_manager, RecorderSessionError,
        )

        session_id = pk
        session = recorder_manager.get(session_id)
        meta = recorder_manager.get_meta(session_id)
        if session is None or meta is None or not self._owner_ok(request, meta):
            return Response({'detail': '录制会话不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

        if not meta.env_config_id:
            return Response(
                {'detail': '该录制会话未关联环境配置，无法保存登录态（请使用新的录制会话）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        env_config = UiEnvironmentConfig.objects.filter(id=meta.env_config_id).first()
        if env_config is None:
            return Response({'detail': '关联的环境配置不存在，无法保存登录态'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            storage_state = session.save_login_state()
        except RecorderSessionError as exc:
            return Response({'detail': f'保存登录态失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

        cookies = storage_state.get('cookies') or []
        origins = storage_state.get('origins') or []
        ls_total = sum(len(o.get('localStorage') or []) for o in origins)
        if not cookies and ls_total == 0:
            return Response(
                {'detail': '当前浏览器没有捕获到任何登录凭据（cookies/localStorage），'
                           '请先在录制画布中完成目标系统登录后再保存登录态'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = str(request.data.get('name') or '').strip() or f"录制登录态-{env_config.name}"
        description = str(request.data.get('description') or '').strip()
        auth_state = UiAuthState.objects.create(
            name=name,
            env_config=env_config,
            state_json=storage_state,
            description=description,
            creator=request.user,
        )
        # 录制过程中重新保存的登录态：作为会话当前生效绑定，本步骤及以下步骤继承
        meta.auth_state_id = auth_state.id
        return Response({
            'message': '登录态已保存到环境「%s」' % env_config.name,
            'auth_state_id': auth_state.id,
            'name': auth_state.name,
            'env_config_id': env_config.id,
            'cookies': len(cookies),
            'local_storage_keys': ls_total,
        }, status=status.HTTP_201_CREATED)
