"""清理磁盘上已无对应数据库记录的 Skill 残留目录"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from skills.models import Skill


class Command(BaseCommand):
    help = '清理磁盘上已无对应数据库记录的 Skill 残留目录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅列出待清理目录，不实际删除',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skills_root = Path(settings.MEDIA_ROOT) / 'skills'

        if not skills_root.is_dir():
            self.stdout.write('skills 目录不存在，无需清理')
            return

        # 收集数据库中仍存在的 skill 路径
        existing_paths = set(
            Skill.objects.exclude(skill_path='')
            .values_list('skill_path', flat=True)
        )

        removed = 0
        for project_dir in skills_root.iterdir():
            if not project_dir.is_dir():
                continue
            for skill_dir in project_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                relative = f'skills/{project_dir.name}/{skill_dir.name}'
                if relative not in existing_paths:
                    if dry_run:
                        self.stdout.write(f'[dry-run] 将删除: {skill_dir}')
                    else:
                        try:
                            shutil.rmtree(skill_dir)
                            self.stdout.write(f'已删除: {skill_dir}')
                        except PermissionError:
                            self.stderr.write(self.style.WARNING(
                                f'权限不足，无法删除: {skill_dir}（尝试 sudo 运行）'
                            ))
                    removed += 1
            # 项目目录为空时一并清理
            if not dry_run and project_dir.is_dir() and not any(project_dir.iterdir()):
                project_dir.rmdir()
                self.stdout.write(f'已删除空项目目录: {project_dir}')

        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry_run else ""}清理完成，共 {removed} 个残留目录'
        ))
