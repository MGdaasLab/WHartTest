"""
修复知识库向量存储的管理命令
用于重建损坏的向量索引
"""
from django.core.management.base import BaseCommand, CommandError
from knowledge.models import KnowledgeBase, Document
from knowledge.services import KnowledgeBaseService, VectorStoreManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '修复知识库向量存储,重建损坏的索引'

    def add_arguments(self, parser):
        parser.add_argument(
            '--kb-id',
            type=str,
            help='指定要修复的知识库ID'
        )
        parser.add_argument(
            '--rebuild-all',
            action='store_true',
            help='重建所有活跃知识库的索引'
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='仅清理所有向量存储缓存'
        )

    def handle(self, *args, **options):
        if options['clear_cache']:
            self._clear_all_cache()
        elif options['rebuild_all']:
            self._rebuild_all()
        elif options['kb_id']:
            self._rebuild_single(options['kb_id'])
        else:
            self.stdout.write(
                self.style.ERROR(
                    '请指定操作: --kb-id <ID> 或 --rebuild-all 或 --clear-cache'
                )
            )

    def _clear_all_cache(self):
        """清理所有缓存"""
        try:
            VectorStoreManager.clear_cache()
            self.stdout.write(self.style.SUCCESS('✅ 已清理所有向量存储缓存'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 清理缓存失败: {e}'))

    def _rebuild_all(self):
        """重建所有知识库"""
        kbs = KnowledgeBase.objects.filter(is_active=True)
        total = kbs.count()
        
        self.stdout.write(f'准备重建 {total} 个活跃知识库...\n')
        
        success_count = 0
        fail_count = 0
        
        for i, kb in enumerate(kbs, 1):
            self.stdout.write(f'[{i}/{total}] 处理知识库: {kb.name} ({kb.id})')
            if self._rebuild_kb(kb):
                success_count += 1
            else:
                fail_count += 1
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'✅ 成功: {success_count}'))
        if fail_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ 失败: {fail_count}'))
        self.stdout.write('='*50)

    def _rebuild_single(self, kb_id):
        """重建单个知识库"""
        try:
            kb = KnowledgeBase.objects.get(id=kb_id)
            self.stdout.write(f'准备重建知识库: {kb.name} ({kb.id})\n')
            
            if self._rebuild_kb(kb):
                self.stdout.write(self.style.SUCCESS('\n✅ 知识库重建完成'))
            else:
                self.stdout.write(self.style.ERROR('\n❌ 知识库重建失败'))
                
        except KnowledgeBase.DoesNotExist:
            raise CommandError(f'知识库不存在: {kb_id}')

    def _rebuild_kb(self, kb):
        """重建单个知识库的实现"""
        try:
            # 1. 删除旧的 Qdrant 集合并清理缓存
            self.stdout.write('  🗑️  清理旧的向量存储...')
            VectorStoreManager.drop_collection(kb.id)
            
            # 2. 获取已完成的文档
            docs = kb.documents.filter(status='completed')
            doc_count = docs.count()
            
            if doc_count == 0:
                self.stdout.write(self.style.WARNING('  ⚠️  没有已完成的文档,跳过'))
                return True
            
            self.stdout.write(f'  📄 找到 {doc_count} 个文档')
            
            # 3. 重新处理所有文档
            service = KnowledgeBaseService(kb)
            success = 0
            failed = 0
            
            for i, doc in enumerate(docs, 1):
                try:
                    self.stdout.write(f'    [{i}/{doc_count}] 处理: {doc.title}', ending='')
                    
                    # 删除旧的分块
                    doc.chunks.all().delete()
                    
                    # 重新处理
                    service.process_document(doc)
                    success += 1
                    self.stdout.write(self.style.SUCCESS(' ✓'))
                    
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f' ✗ ({str(e)[:50]})'))
            
            self.stdout.write(f'  📊 成功: {success}, 失败: {failed}')
            
            if failed == 0:
                self.stdout.write(self.style.SUCCESS(f'  ✅ 知识库 {kb.name} 重建完成'))
                return True
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠️  知识库 {kb.name} 部分重建成功'))
                return False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ 重建失败: {e}'))
            logger.error(f'重建知识库 {kb.id} 失败: {e}', exc_info=True)
            return False