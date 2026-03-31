# -*- coding: utf-8 -*-
"""UI 自动化路由配置"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    UiModuleViewSet, UiPageViewSet, UiElementViewSet,
    UiPageStepsViewSet, UiPageStepsDetailedViewSet,
    UiTestCaseViewSet, UiCaseStepsDetailedViewSet,
    UiExecutionRecordViewSet, UiPublicDataViewSet, UiEnvironmentConfigViewSet,
    ActuatorViewSet, UiBatchExecutionRecordViewSet, upload_screenshot, upload_trace,
    trigger_batch_execution
)

router = DefaultRouter()
router.register('modules', UiModuleViewSet, basename='ui-modules')
router.register('pages', UiPageViewSet, basename='ui-pages')
router.register('elements', UiElementViewSet, basename='ui-elements')
router.register('page-steps', UiPageStepsViewSet, basename='ui-page-steps')
router.register('page-steps-detailed', UiPageStepsDetailedViewSet, basename='ui-page-steps-detailed')
router.register('testcases', UiTestCaseViewSet, basename='ui-testcases')
router.register('case-steps', UiCaseStepsDetailedViewSet, basename='ui-case-steps')
router.register('execution-records', UiExecutionRecordViewSet, basename='ui-execution-records')
router.register('public-data', UiPublicDataViewSet, basename='ui-public-data')
router.register('env-configs', UiEnvironmentConfigViewSet, basename='ui-env-configs')
router.register('actuators', ActuatorViewSet, basename='ui-actuators')
router.register('batch-records', UiBatchExecutionRecordViewSet, basename='ui-batch-records')

urlpatterns = router.urls + [
    path('screenshots/upload/', upload_screenshot, name='ui-screenshot-upload'),
    path('traces/upload/', upload_trace, name='ui-trace-upload'),
    path('trigger-batch/', trigger_batch_execution, name='ui-trigger-batch'),
]