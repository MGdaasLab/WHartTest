"""
Django管理命令：检查知识库系统状态
"""
import os
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from knowledge.models import KnowledgeBase, Document
from knowledge.services import VectorStoreManager


class Command(BaseCommand):
    help = '检查知识库系统状态和配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='尝试自动修复发现的问题',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息',
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.fix_issues = options['fix']
        
        self.stdout.write(
            self.style.SUCCESS('🤖 知识库系统状态检查')
        )
        self.stdout.write('=' * 50)
        
        issues = []
        
        # 检查环境变量
        issues.extend(self.check_environment())
        
        # 检查依赖库
        issues.extend(self.check_dependencies())
        
        # 检查BGE-M3模型
        issues.extend(self.check_embedding_model())
        
        # 检查数据库状态
        issues.extend(self.check_database())
        
        # 检查向量存储
        issues.extend(self.check_vector_stores())
        
        # 总结
        self.stdout.write('\n' + '=' * 50)
        if issues:
            self.stdout.write(
                self.style.WARNING(f'⚠️  发现 {len(issues)} 个问题:')
            )
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f'  {i}. {issue}')
                
            if self.fix_issues:
                self.stdout.write('\n🔧 尝试自动修复...')
                self.attempt_fixes()
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ 知识库系统状态良好！')
            )

    def check_environment(self):
        """检查环境变量配置"""
        self.stdout.write('\n🔍 检查环境变量...')
        issues = []
        
        # 检查HuggingFace缓存目录配置
        cache_dir = Path('.cache/huggingface')
        
        if not cache_dir.exists():
            issues.append('HuggingFace缓存目录不存在')
            if self.fix_issues:
                cache_dir.mkdir(parents=True, exist_ok=True)
                self.stdout.write('  ✅ 已创建缓存目录')
        
        # 检查环境变量
        env_vars = {
            'HF_HOME': str(cache_dir),
            'HF_HUB_CACHE': str(cache_dir),
            'SENTENCE_TRANSFORMERS_HOME': str(cache_dir),
        }
        
        for var, expected in env_vars.items():
            current = os.environ.get(var)
            if current != expected:
                if self.verbose:
                    self.stdout.write(f'  ⚠️  {var}: {current} -> {expected}')
                os.environ[var] = expected
        
        self.stdout.write('  ✅ 环境变量配置完成')
        return issues

    def check_dependencies(self):
        """检查依赖库"""
        self.stdout.write('\n📦 检查依赖库...')
        issues = []
        
        required_packages = {
            'langchain_huggingface': 'LangChain HuggingFace集成',
            'langchain_chroma': 'LangChain ChromaDB集成',
            'sentence_transformers': 'SentenceTransformers库',
            'torch': 'PyTorch深度学习框架',
            'transformers': 'HuggingFace Transformers库'
        }
        
        for package, description in required_packages.items():
            try:
                __import__(package)
                self.stdout.write(f'  ✅ {description}')
            except ImportError:
                issue = f'缺少依赖库: {package} ({description})'
                issues.append(issue)
                self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_embedding_model(self):
        """检查BGE-M3嵌入模型"""
        self.stdout.write('\n🤖 检查BGE-M3嵌入模型...')
        issues = []
        
        cache_dir = Path('.cache/huggingface')
        model_name = "BAAI/bge-m3"
        model_cache_name = model_name.replace('/', '--')
        model_path = cache_dir / f'models--{model_cache_name}'
        
        if not model_path.exists():
            issue = 'BGE-M3模型未下载'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
            self.stdout.write(f'     💡 请运行: python download_embedding_models.py --download bge-m3')
        else:
            self.stdout.write(f'  ✅ 模型文件存在: {model_path}')
            
            # 计算模型大小
            total_size = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
            size_gb = total_size / (1024**3)
            self.stdout.write(f'     💾 模型大小: {size_gb:.1f}GB')
            
            # 测试模型加载
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
                
                self.stdout.write('  🧪 测试模型加载...')
                start_time = time.time()
                
                embeddings = HuggingFaceEmbeddings(
                    model_name=model_name,
                    cache_folder=str(cache_dir),
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )
                
                # 测试嵌入
                test_vector = embeddings.embed_query("测试文本")
                load_time = time.time() - start_time
                
                self.stdout.write(f'  ✅ 模型加载成功 (耗时: {load_time:.2f}s)')
                self.stdout.write(f'     📊 嵌入维度: {len(test_vector)}')
                
            except Exception as e:
                issue = f'BGE-M3模型加载失败: {str(e)}'
                issues.append(issue)
                self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_database(self):
        """检查数据库状态"""
        self.stdout.write('\n💾 检查数据库状态...')
        issues = []
        
        try:
            # 检查知识库数量
            kb_count = KnowledgeBase.objects.count()
            active_kb_count = KnowledgeBase.objects.filter(is_active=True).count()
            doc_count = Document.objects.count()
            completed_doc_count = Document.objects.filter(status='completed').count()
            
            self.stdout.write(f'  📚 知识库总数: {kb_count} (活跃: {active_kb_count})')
            self.stdout.write(f'  📄 文档总数: {doc_count} (已处理: {completed_doc_count})')
            
            # 检查失败的文档
            failed_docs = Document.objects.filter(status='failed').count()
            if failed_docs > 0:
                issue = f'有 {failed_docs} 个文档处理失败'
                issues.append(issue)
                self.stdout.write(f'  ⚠️  {issue}')
            
        except Exception as e:
            issue = f'数据库查询失败: {str(e)}'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def check_vector_stores(self):
        """检查向量存储状态"""
        self.stdout.write('\n🗄️  检查向量存储...')
        issues = []
        
        try:
            # 检查向量存储缓存
            cache_count = len(VectorStoreManager._vector_store_cache)
            self.stdout.write(f'  💾 向量存储缓存: {cache_count} 个实例')
            
            # 检查知识库目录
            kb_dir = Path(settings.MEDIA_ROOT) / 'knowledge_bases'
            if kb_dir.exists():
                kb_dirs = [d for d in kb_dir.iterdir() if d.is_dir()]
                self.stdout.write(f'  📁 知识库目录数量: {len(kb_dirs)}')
                
                # 检查ChromaDB文件
                for kb_path in kb_dirs:
                    chroma_path = kb_path / 'chroma_db'
                    if chroma_path.exists():
                        sqlite_files = list(chroma_path.glob('*.sqlite3*'))
                        if sqlite_files:
                            self.stdout.write(f'     ✅ {kb_path.name}: {len(sqlite_files)} 个数据库文件')
                        else:
                            issue = f'知识库 {kb_path.name} 缺少ChromaDB文件'
                            issues.append(issue)
                            if self.verbose:
                                self.stdout.write(f'     ⚠️  {issue}')
            else:
                self.stdout.write('  📁 知识库目录不存在')
                
        except Exception as e:
            issue = f'向量存储检查失败: {str(e)}'
            issues.append(issue)
            self.stdout.write(f'  ❌ {issue}')
        
        return issues

    def attempt_fixes(self):
        """尝试自动修复问题"""
        self.stdout.write('🔧 自动修复功能开发中...')
        self.stdout.write('💡 请根据上述提示手动修复问题')
