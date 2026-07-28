from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from ui_automation.models import (
    UiCaseStepsDetailed,
    UiElement,
    UiModule,
    UiPage,
    UiPageSteps,
    UiPageStepsDetailed,
    UiTestCase,
)
from ui_automation.serializers import UiPageStepsExecuteSerializer
from file_management.models import FileAsset, FileManagementSetting, FileReference


class UiPageStepsExecuteDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='tester', password='secret')
        self.project = Project.objects.create(name='Demo Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(
            project=self.project,
            name='Module A',
            creator=self.user,
        )
        self.page = UiPage.objects.create(
            project=self.project,
            module=self.module,
            name='Login Page',
            url='/login',
            creator=self.user,
        )
        self.element = UiElement.objects.create(
            page=self.page,
            name='Submit Button',
            locator_type='css',
            locator_value='button[type="submit"]',
            locator_index=2,
            locator_type_2='xpath',
            locator_value_2='//button[@type="submit"]',
            locator_index_2=1,
            locator_type_3='text',
            locator_value_3='Submit',
            is_iframe=True,
            iframe_locator='iframe.login-frame',
            creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project,
            page=self.page,
            module=self.module,
            name='Submit Login',
            creator=self.user,
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            element=self.element,
            ope_key='click',
            step_sort=0,
        )

    def test_execute_data_includes_iframe_fields(self):
        response = UiPageStepsExecuteSerializer(self.page_step).data
        self.assertEqual(len(response['step_details']), 1)
        detail = response['step_details'][0]
        self.assertEqual(detail['locator_index'], 2)
        self.assertEqual(detail['locator_type_2'], 'xpath')
        self.assertEqual(detail['locator_value_2'], '//button[@type="submit"]')
        self.assertEqual(detail['locator_index_2'], 1)
        self.assertEqual(detail['locator_type_3'], 'text')
        self.assertEqual(detail['locator_value_3'], 'Submit')
        self.assertTrue(detail['is_iframe'])
        self.assertEqual(detail['iframe_locator'], 'iframe.login-frame')

    def test_delete_referenced_element_is_rejected(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.delete(f'/api/ui-automation/elements/{self.element.id}/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('元素已被 1 个页面步骤引用', response.data['error'])
        self.assertTrue(UiElement.objects.filter(id=self.element.id).exists())
        self.assertEqual(
            UiPageStepsDetailed.objects.get(page_step=self.page_step, step_sort=0).element_id,
            self.element.id,
        )

    def test_execute_data_resolves_upload_file_id_to_file_path(self):
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='avatar.png',
            mime_type='image/png',
            size=5,
            sha256='abc',
        )
        asset.file.save('avatar.png', ContentFile(b'hello'), save=True)
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            element=self.element,
            ope_key='upload',
            ope_value={'file_id': asset.id, 'file_name': 'avatar.png', 'value': f'file_id:{asset.id}'},
            step_sort=1,
        )
        response = UiPageStepsExecuteSerializer(self.page_step).data
        upload_detail = next(item for item in response['step_details'] if item.get('ope_key') == 'upload')
        self.assertEqual(upload_detail['ope_value']['file_id'], asset.id)
        self.assertEqual(upload_detail['ope_value']['file_name'], 'avatar.png')
        self.assertIn('file_management/projects/', upload_detail['ope_value']['file_path'])
        self.assertEqual(upload_detail['ope_value']['value'], upload_detail['ope_value']['file_path'])
        self.assertEqual(
            upload_detail['ope_value']['download_url'],
            f'/api/projects/{self.project.id}/files/{asset.id}/download/',
        )
        self.assertEqual(upload_detail['ope_value']['project_id'], self.project.id)

    def test_delete_upload_step_keeps_file_when_auto_delete_disabled(self):
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='delete-me.txt',
            mime_type='text/plain',
            size=5,
            sha256='def',
        )
        asset.file.save('delete-me.txt', ContentFile(b'hello'), save=True)
        storage = asset.file.storage
        storage_name = asset.file.name
        upload_step = UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            element=self.element,
            ope_key='upload',
            ope_value={'file_id': asset.id, 'file_name': 'delete-me.txt', 'value': f'file_id:{asset.id}'},
            step_sort=2,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.delete(f'/api/ui-automation/page-steps-detailed/{upload_step.id}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))
        self.assertTrue(FileAsset.objects.filter(id=asset.id).exists())
        self.assertTrue(storage.exists(storage_name))

    def test_delete_upload_step_keeps_file_when_no_reference_exists_even_if_enabled(self):
        from file_management.models import FileManagementSetting
        FileManagementSetting.objects.update_or_create(
            project=self.project,
            defaults={'auto_delete_on_unbind': True},
        )
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='delete-me-enabled.txt',
            mime_type='text/plain',
            size=5,
            sha256='ghi',
        )
        asset.file.save('delete-me-enabled.txt', ContentFile(b'hello'), save=True)
        storage = asset.file.storage
        storage_name = asset.file.name
        upload_step = UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            element=self.element,
            ope_key='upload',
            ope_value={'file_id': asset.id, 'file_name': 'delete-me-enabled.txt', 'value': f'file_id:{asset.id}'},
            step_sort=3,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.delete(f'/api/ui-automation/page-steps-detailed/{upload_step.id}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))
        self.assertTrue(FileAsset.objects.filter(id=asset.id).exists())
        self.assertTrue(storage.exists(storage_name))

    def test_create_upload_step_creates_file_reference_count(self):
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='referenced.txt',
            mime_type='text/plain',
            size=5,
            sha256='ref',
        )
        asset.file.save('referenced.txt', ContentFile(b'hello'), save=True)
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post('/api/ui-automation/page-steps-detailed/', {
            'page_step': self.page_step.id,
            'step_type': 0,
            'element': self.element.id,
            'step_sort': 4,
            'ope_key': 'upload',
            'ope_value': {'file_id': asset.id, 'file_name': 'referenced.txt', 'value': f'file_id:{asset.id}'},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(FileReference.objects.filter(
            file=asset,
            project=self.project,
            ref_type=FileReference.REF_UI_PAGE_STEPS,
            ref_id=f"detail:{response.data['id']}",
        ).exists())
        asset.refresh_from_db()
        self.assertEqual(asset.references.count(), 1)

    def test_api_created_upload_step_deletes_file_when_auto_delete_enabled(self):
        from file_management.models import FileManagementSetting
        FileManagementSetting.objects.update_or_create(
            project=self.project,
            defaults={'auto_delete_on_unbind': True},
        )
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='delete-api-created.txt',
            mime_type='text/plain',
            size=5,
            sha256='apidel',
        )
        asset.file.save('delete-api-created.txt', ContentFile(b'hello'), save=True)
        storage = asset.file.storage
        storage_name = asset.file.name
        client = APIClient()
        client.force_authenticate(user=self.user)
        create_response = client.post('/api/ui-automation/page-steps-detailed/', {
            'page_step': self.page_step.id,
            'step_type': 0,
            'element': self.element.id,
            'step_sort': 5,
            'ope_key': 'upload',
            'ope_value': {'file_id': asset.id, 'file_name': 'delete-api-created.txt', 'value': f'file_id:{asset.id}'},
        }, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(asset.references.count(), 1)

        delete_response = client.delete(f"/api/ui-automation/page-steps-detailed/{create_response.data['id']}/")
        self.assertIn(delete_response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))
        self.assertFalse(FileAsset.objects.filter(id=asset.id).exists())
        self.assertFalse(storage.exists(storage_name))


class UiModuleSortingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='testuser',
            password='password',
            email='test@example.com',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name='Test Project',
            description='Test Description',
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')

        self.root1 = UiModule.objects.create(
            project=self.project,
            name='Root 1',
            creator=self.user,
            order=1,
        )
        self.child1_1 = UiModule.objects.create(
            project=self.project,
            name='Child 1-1',
            parent=self.root1,
            creator=self.user,
            order=1,
        )
        self.child1_1_1 = UiModule.objects.create(
            project=self.project,
            name='Child 1-1-1',
            parent=self.child1_1,
            creator=self.user,
            order=1,
        )
        self.child1_2 = UiModule.objects.create(
            project=self.project,
            name='Child 1-2',
            parent=self.root1,
            creator=self.user,
            order=2,
        )
        self.root2 = UiModule.objects.create(
            project=self.project,
            name='Root 2',
            creator=self.user,
            order=2,
        )

    def test_get_max_depth(self):
        self.assertEqual(self.root1.get_max_depth(), 3)
        self.assertEqual(self.child1_1.get_max_depth(), 2)
        self.assertEqual(self.child1_1_1.get_max_depth(), 1)

    def test_move_api_sibling_reorder_before(self):
        url = f'/api/ui-automation/modules/{self.child1_2.id}/move/'
        data = {
            'target_id': self.child1_1.id,
            'drop_position': -1,
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.child1_1.refresh_from_db()
        self.child1_2.refresh_from_db()

        self.assertEqual(self.child1_2.order, 1)
        self.assertEqual(self.child1_1.order, 2)
        self.assertEqual(self.child1_2.parent, self.root1)
        self.assertEqual(self.child1_1.parent, self.root1)

    def test_move_api_into_parent(self):
        url = f'/api/ui-automation/modules/{self.child1_2.id}/move/'
        data = {
            'target_id': self.root2.id,
            'drop_position': 0,
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.child1_2.refresh_from_db()
        self.assertEqual(self.child1_2.parent, self.root2)
        self.assertEqual(self.child1_2.level, 2)

    def test_move_api_circular_reference_protection(self):
        url = f'/api/ui-automation/modules/{self.root1.id}/move/'
        data = {
            'target_id': self.child1_1_1.id,
            'drop_position': 0,
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('无法移动模块到自身或其子模块下', response.data['error'])

    def test_move_api_depth_limit_protection(self):
        child4 = UiModule.objects.create(
            project=self.project,
            name='Child 4',
            parent=self.child1_1_1,
            creator=self.user,
        )
        UiModule.objects.create(
            project=self.project,
            name='Child 5',
            parent=child4,
            creator=self.user,
        )

        url = f'/api/ui-automation/modules/{self.root1.id}/move/'
        data = {
            'target_id': self.root2.id,
            'drop_position': 0,
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('超过5级限制', response.data['error'])


class UiStepBatchUpdatePreservesOverrideTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='batchuser', password='password', email='batch@example.com')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(name='Batch Project', description='Test Description', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='Root', creator=self.user, order=1)
        self.page = UiPage.objects.create(project=self.project, module=self.module, name='Login', url='https://example.com', creator=self.user)
        self.element = UiElement.objects.create(
            page=self.page,
            name='Username',
            locator_type='css',
            locator_value='#username',
            creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project,
            page=self.page,
            module=self.module,
            name='Fill login form',
            creator=self.user,
        )
        self.other_page_step = UiPageSteps.objects.create(
            project=self.project,
            page=self.page,
            module=self.module,
            name='Submit login form',
            creator=self.user,
        )
        self.detail_one = UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            step_type=0,
            element=self.element,
            step_sort=0,
            ope_key='fill',
            ope_value={'text': 'default-one'},
        )
        self.detail_two = UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            step_type=0,
            element=self.element,
            step_sort=1,
            ope_key='type',
            ope_value={'text': 'default-two'},
        )
        self.test_case = UiTestCase.objects.create(
            project=self.project,
            module=self.module,
            name='Login case',
            creator=self.user,
        )
        self.case_step = UiCaseStepsDetailed.objects.create(
            test_case=self.test_case,
            page_step=self.page_step,
            case_sort=0,
            case_data={
                str(self.detail_one.id): {'text': 'override-one'},
                str(self.detail_two.id): {'text': 'override-two'},
            },
        )
        self.other_case_step = UiCaseStepsDetailed.objects.create(
            test_case=self.test_case,
            page_step=self.other_page_step,
            case_sort=1,
        )

    def test_page_step_detail_reorder_keeps_detail_ids(self):
        url = '/api/ui-automation/page-steps-detailed/batch_update/'
        response = self.client.post(url, {
            'page_step': self.page_step.id,
            'steps': [
                {
                    'id': self.detail_two.id,
                    'step_type': self.detail_two.step_type,
                    'element': self.element.id,
                    'ope_key': self.detail_two.ope_key,
                    'ope_value': self.detail_two.ope_value,
                },
                {
                    'id': self.detail_one.id,
                    'step_type': self.detail_one.step_type,
                    'element': self.element.id,
                    'ope_key': self.detail_one.ope_key,
                    'ope_value': self.detail_one.ope_value,
                },
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            list(UiPageStepsDetailed.objects.filter(page_step=self.page_step).order_by('step_sort').values_list('id', flat=True)),
            [self.detail_two.id, self.detail_one.id],
        )
        self.detail_one.refresh_from_db()
        self.detail_two.refresh_from_db()
        self.assertEqual(self.detail_one.step_sort, 1)
        self.assertEqual(self.detail_two.step_sort, 0)

    def test_page_step_detail_reorder_keeps_upload_file_when_auto_delete_enabled(self):
        FileManagementSetting.objects.update_or_create(
            project=self.project,
            defaults={'auto_delete_on_unbind': True},
        )
        asset = FileAsset.objects.create(
            project=self.project,
            owner=self.user,
            original_name='reorder-upload.txt',
            mime_type='text/plain',
            size=5,
            sha256='reorder-upload',
        )
        asset.file.save('reorder-upload.txt', ContentFile(b'hello'), save=True)
        storage = asset.file.storage
        storage_name = asset.file.name
        upload_detail = UiPageStepsDetailed.objects.create(
            page_step=self.page_step,
            step_type=0,
            element=self.element,
            step_sort=2,
            ope_key='upload',
            ope_value={
                'file_id': asset.id,
                'file_name': 'reorder-upload.txt',
                'value': f'file_id:{asset.id}',
            },
        )
        FileReference.objects.create(
            file=asset,
            project=self.project,
            ref_type=FileReference.REF_UI_PAGE_STEPS,
            ref_id=f'detail:{upload_detail.id}',
            created_by=self.user,
        )

        response = self.client.post('/api/ui-automation/page-steps-detailed/batch_update/', {
            'page_step': self.page_step.id,
            'steps': [
                {
                    'id': self.detail_two.id,
                    'step_type': self.detail_two.step_type,
                    'element': self.element.id,
                    'ope_key': self.detail_two.ope_key,
                    'ope_value': self.detail_two.ope_value,
                },
                {
                    'id': upload_detail.id,
                    'step_type': upload_detail.step_type,
                    'element': self.element.id,
                    'ope_key': upload_detail.ope_key,
                    'ope_value': upload_detail.ope_value,
                },
                {
                    'id': self.detail_one.id,
                    'step_type': self.detail_one.step_type,
                    'element': self.element.id,
                    'ope_key': self.detail_one.ope_key,
                    'ope_value': self.detail_one.ope_value,
                },
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(FileAsset.objects.filter(id=asset.id).exists())
        self.assertTrue(storage.exists(storage_name))
        self.assertTrue(FileReference.objects.filter(
            file=asset,
            project=self.project,
            ref_type=FileReference.REF_UI_PAGE_STEPS,
            ref_id=f'detail:{upload_detail.id}',
        ).exists())
        upload_detail.refresh_from_db()
        self.assertEqual(upload_detail.step_sort, 1)

    def test_case_step_reorder_keeps_case_data_when_not_submitted(self):
        url = '/api/ui-automation/case-steps/batch_update/'
        expected_case_data = self.case_step.case_data

        response = self.client.post(url, {
            'test_case': self.test_case.id,
            'steps': [
                {
                    'id': self.other_case_step.id,
                    'page_step': self.other_case_step.page_step_id,
                },
                {
                    'id': self.case_step.id,
                    'page_step': self.case_step.page_step_id,
                },
            ],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(UiCaseStepsDetailed.objects.filter(id=self.case_step.id).exists())
        self.case_step.refresh_from_db()
        self.other_case_step.refresh_from_db()
        self.assertEqual(self.case_step.case_sort, 1)
        self.assertEqual(self.other_case_step.case_sort, 0)
        self.assertEqual(self.case_step.case_data, expected_case_data)
