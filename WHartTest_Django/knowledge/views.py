import os
import threading
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.db import models
from django.utils import timezone
from wharttest_django.viewsets import BaseModelViewSet
from .models import KnowledgeBase, Document, DocumentChunk, QueryLog
from .serializers import (
    KnowledgeBaseSerializer, DocumentUploadSerializer, DocumentSerializer,
    DocumentChunkSerializer, QueryLogSerializer, KnowledgeQuerySerializer,
    KnowledgeQueryResponseSerializer
)
from .services import KnowledgeBaseService, VectorStoreManager
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class KnowledgeBaseViewSet(BaseModelViewSet):
    """知识库视图集"""
    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'is_active', 'embedding_service']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + 模型权限）
        return super().get_permissions()

    def get_queryset(self):
        """只返回用户有权限访问的知识库"""
        user = self.request.user
        if user.is_superuser:
            return KnowledgeBase.objects.all()

        # 普通用户只能看到自己是成员的项目的知识库
        return KnowledgeBase.objects.filter(
            project__members__user=user
        ).distinct()

    def perform_create(self, serializer):
        """创建知识库时自动设置创建人"""
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['post'])
    def query(self, request, pk=None):
        """查询知识库"""
        knowledge_base = self.get_object()

        # 验证查询参数
        query_serializer = KnowledgeQuerySerializer(
            data=request.data,
            context={'request': request}
        )
        query_serializer.is_valid(raise_exception=True)

        try:
            # 执行查询
            service = KnowledgeBaseService(knowledge_base)
            result = service.query(
                query_text=query_serializer.validated_data['query'],
                top_k=query_serializer.validated_data.get('top_k', 5),
                similarity_threshold=query_serializer.validated_data.get('similarity_threshold', 0.1),
                user=request.user
            )

            # 序列化响应
            response_serializer = KnowledgeQueryResponseSerializer(result)
            return Response(response_serializer.data)

        except Exception as e:
            logger.error(f"知识库查询失败: {e}")
            return Response(
                {'error': f'查询失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """获取知识库统计信息"""
        knowledge_base = self.get_object()

        stats = {
            'document_count': knowledge_base.documents.count(),
            'chunk_count': DocumentChunk.objects.filter(
                document__knowledge_base=knowledge_base
            ).count(),
            'query_count': knowledge_base.query_logs.count(),
            'document_status_distribution': {},
            'recent_queries': knowledge_base.query_logs.order_by('-created_at')[:5].values(
                'query', 'total_time', 'created_at'
            )
        }

        # 文档状态分布
        status_counts = knowledge_base.documents.values('status').annotate(
            count=models.Count('status')
        )
        for item in status_counts:
            stats['document_status_distribution'][item['status']] = item['count']

        return Response(stats)

    @action(detail=True, methods=['get'])
    def content(self, request, pk=None):
        """查看知识库内容"""
        knowledge_base = self.get_object()

        # 获取查询参数
        search = request.query_params.get('search', '')
        document_type = request.query_params.get('document_type', '')
        status = request.query_params.get('status', 'completed')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        # 构建查询
        documents = knowledge_base.documents.filter(status=status)

        if search:
            documents = documents.filter(
                models.Q(title__icontains=search) |
                models.Q(content__icontains=search)
            )

        if document_type:
            documents = documents.filter(document_type=document_type)

        # 排序
        documents = documents.order_by('-uploaded_at')

        # 分页
        total_count = documents.count()
        start = (page - 1) * page_size
        end = start + page_size
        documents = documents[start:end]

        # 序列化文档数据
        content_data = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'title': doc.title,
                'document_type': doc.document_type,
                'status': doc.status,
                'uploader_name': doc.uploader.username,
                'uploaded_at': doc.uploaded_at,
                'chunk_count': doc.chunks.count(),
                'content_preview': doc.content[:500] if doc.content else None,  # 内容预览
                'file_size': doc.file_size,
                'page_count': doc.page_count,
                'word_count': doc.word_count,
            }

            # 如果是文件类型，添加文件信息
            if doc.file:
                doc_data['file_name'] = doc.file.name.split('/')[-1]
                doc_data['file_url'] = doc.file.url if hasattr(doc.file, 'url') else None

            # 如果是URL类型，添加URL信息
            if doc.url:
                doc_data['url'] = doc.url

            content_data.append(doc_data)

        # 返回分页数据
        return Response({
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'documents': content_data,
            'knowledge_base': {
                'id': knowledge_base.id,
                'name': knowledge_base.name,
                'description': knowledge_base.description,
            }
        })

    @action(detail=False, methods=['get'])
    def system_status(self, request):
        """检查知识库系统状态"""
        try:
            status_info = {
                'timestamp': time.time(),
                'embedding_model': {
                    'status': 'unknown',
                    'model_name': 'BAAI/bge-m3',
                    'cache_path': None,
                    'model_exists': False,
                    'load_test': False,
                    'error': None
                },
                'dependencies': {
                    'langchain_huggingface': False,
                    'langchain_chroma': False,
                    'sentence_transformers': False,
                    'torch': False
                },
                'vector_stores': {
                    'total_knowledge_bases': 0,
                    'active_knowledge_bases': 0,
                    'cache_status': 'unknown'
                },
                'overall_status': 'unknown'
            }

            # 检查依赖库
            try:
                import langchain_huggingface
                status_info['dependencies']['langchain_huggingface'] = True
            except ImportError:
                pass

            try:
                import langchain_chroma
                status_info['dependencies']['langchain_chroma'] = True
            except ImportError:
                pass

            try:
                import sentence_transformers
                status_info['dependencies']['sentence_transformers'] = True
            except ImportError:
                pass

            try:
                import torch
                status_info['dependencies']['torch'] = True
            except ImportError:
                pass

            # 检查BGE-M3模型
            cache_dir = Path('.cache/huggingface')
            model_cache_name = "BAAI--bge-m3"
            model_path = cache_dir / f'models--{model_cache_name}'

            status_info['embedding_model']['cache_path'] = str(model_path)
            status_info['embedding_model']['model_exists'] = model_path.exists()

            if model_path.exists():
                status_info['embedding_model']['status'] = 'available'

                # 尝试加载测试
                try:
                    from langchain_huggingface import HuggingFaceEmbeddings

                    embeddings = HuggingFaceEmbeddings(
                        model_name="BAAI/bge-m3",
                        cache_folder=str(cache_dir),
                        model_kwargs={'device': 'cpu'},
                        encode_kwargs={'normalize_embeddings': True}
                    )

                    # 简单测试
                    test_vector = embeddings.embed_query("测试")
                    if len(test_vector) > 0:
                        status_info['embedding_model']['load_test'] = True
                        status_info['embedding_model']['status'] = 'working'
                        status_info['embedding_model']['dimension'] = len(test_vector)

                except Exception as e:
                    status_info['embedding_model']['status'] = 'error'
                    status_info['embedding_model']['error'] = str(e)
            else:
                status_info['embedding_model']['status'] = 'missing'

            # 检查知识库统计
            total_kb = KnowledgeBase.objects.count()
            active_kb = KnowledgeBase.objects.filter(is_active=True).count()

            status_info['vector_stores']['total_knowledge_bases'] = total_kb
            status_info['vector_stores']['active_knowledge_bases'] = active_kb

            # 检查向量存储缓存
            cache_count = len(VectorStoreManager._vector_store_cache)
            status_info['vector_stores']['cache_status'] = f'{cache_count} cached instances'

            # 确定整体状态
            all_deps = all(status_info['dependencies'].values())
            model_working = status_info['embedding_model']['status'] == 'working'

            if all_deps and model_working:
                status_info['overall_status'] = 'healthy'
            elif all_deps and status_info['embedding_model']['status'] == 'available':
                status_info['overall_status'] = 'ready'
            elif status_info['embedding_model']['status'] == 'missing':
                status_info['overall_status'] = 'model_missing'
            else:
                status_info['overall_status'] = 'error'

            return Response(status_info)

        except Exception as e:
            logger.error(f"系统状态检查失败: {e}")
            return Response(
                {
                    'error': f'系统状态检查失败: {str(e)}',
                    'overall_status': 'error'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentViewSet(BaseModelViewSet):
    """文档视图集"""
    queryset = Document.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['knowledge_base', 'document_type', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['uploaded_at', 'processed_at', 'title']
    ordering = ['-uploaded_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + 模型权限）
        return super().get_permissions()

    def get_serializer_class(self):
        """根据操作返回不同的序列化器"""
        if self.action == 'create':
            return DocumentUploadSerializer
        return DocumentSerializer

    def get_queryset(self):
        """只返回用户有权限访问的文档"""
        user = self.request.user
        if user.is_superuser:
            return Document.objects.all()

        # 普通用户只能看到自己是成员的项目的文档
        return Document.objects.filter(
            knowledge_base__project__members__user=user
        ).distinct()

    def perform_create(self, serializer):
        """创建文档时自动设置上传人"""
        document = serializer.save(uploader=self.request.user)

        # 启动后台任务处理文档（避免超时）
        import threading

        def process_document_async():
            try:
                service = KnowledgeBaseService(document.knowledge_base)
                service.process_document(document)
                logger.info(f"文档 {document.id} 处理完成")
            except Exception as e:
                logger.error(f"文档 {document.id} 处理失败: {e}")
                # 更新文档状态为失败
                document.status = 'failed'
                document.error_message = str(e)
                document.save()

        # 在后台线程中处理文档
        thread = threading.Thread(target=process_document_async)
        thread.daemon = True
        thread.start()

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """获取文档处理状态"""
        document = self.get_object()
        return Response({
            'id': document.id,
            'status': document.status,
            'progress': getattr(document, 'progress', 0),
            'error_message': document.error_message,
            'chunk_count': document.chunks.count(),
            'processed_at': document.processed_at
        })

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """重新处理文档"""
        document = self.get_object()

        # 重置状态
        document.status = 'pending'
        document.error_message = ''
        document.save()

        # 启动后台处理
        import threading

        def reprocess_document_async():
            try:
                service = KnowledgeBaseService(document.knowledge_base)
                service.process_document(document)
                logger.info(f"文档 {document.id} 重新处理完成")
            except Exception as e:
                logger.error(f"文档 {document.id} 重新处理失败: {e}")
                document.status = 'failed'
                document.error_message = str(e)
                document.save()

        thread = threading.Thread(target=reprocess_document_async)
        thread.daemon = True
        thread.start()

        return Response({'message': '文档重新处理已启动，请稍后查看状态'})

    def _get_document_content(self, document):
        """获取文档的实际内容"""
        try:
            # 如果数据库中有内容，直接返回
            if document.content:
                return document.content

            # 如果是文件类型，从文件中读取
            if document.file and hasattr(document.file, 'path'):
                file_path = document.file.path

                # Windows路径兼容性处理
                if os.name == 'nt':
                    file_path = os.path.normpath(file_path)
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(file_path)

                if os.path.exists(file_path):
                    # 根据文件类型选择读取方式
                    if document.document_type == 'txt':
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                return f.read()
                        except UnicodeDecodeError:
                            # 如果UTF-8失败，尝试其他编码
                            with open(file_path, 'r', encoding='gbk') as f:
                                return f.read()
                    else:
                        # 对于其他文件类型，使用DocumentProcessor加载
                        from .services import DocumentProcessor
                        processor = DocumentProcessor()
                        docs = processor.load_document(document)
                        if docs:
                            return '\n\n'.join([doc.page_content for doc in docs])

            # 如果是URL类型，从分块中重建内容
            if document.document_type == 'url' or not document.content:
                chunks = document.chunks.order_by('chunk_index')
                if chunks.exists():
                    return '\n\n'.join([chunk.content for chunk in chunks])

            return None

        except Exception as e:
            logger.error(f"获取文档内容失败: {e}")
            return None

    @action(detail=True, methods=['get'])
    def content(self, request, pk=None):
        """获取文档完整内容"""
        document = self.get_object()

        # 检查文档状态
        if document.status != 'completed':
            return Response(
                {'error': '文档尚未处理完成或处理失败'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取查询参数
        include_chunks = request.query_params.get('include_chunks', 'false').lower() == 'true'
        chunk_page = int(request.query_params.get('chunk_page', 1))
        chunk_page_size = int(request.query_params.get('chunk_page_size', 10))

        # 获取文档实际内容
        document_content = self._get_document_content(document)

        # 基础文档信息
        content_data = {
            'id': document.id,
            'title': document.title,
            'document_type': document.document_type,
            'status': document.status,
            'content': document_content,
            'uploader_name': document.uploader.username,
            'uploaded_at': document.uploaded_at,
            'processed_at': document.processed_at,
            'file_size': document.file_size,
            'page_count': document.page_count,
            'word_count': document.word_count,
            'knowledge_base': {
                'id': document.knowledge_base.id,
                'name': document.knowledge_base.name,
            }
        }

        # 如果是文件类型，添加文件信息
        if document.file:
            content_data['file_name'] = document.file.name.split('/')[-1]
            content_data['file_url'] = document.file.url if hasattr(document.file, 'url') else None

        # 如果是URL类型，添加URL信息
        if document.url:
            content_data['url'] = document.url

        # 如果需要包含分块信息
        if include_chunks:
            chunks = document.chunks.order_by('chunk_index')
            total_chunks = chunks.count()

            # 分页处理分块
            start = (chunk_page - 1) * chunk_page_size
            end = start + chunk_page_size
            chunk_list = chunks[start:end]

            content_data['chunks'] = {
                'total_count': total_chunks,
                'page': chunk_page,
                'page_size': chunk_page_size,
                'total_pages': (total_chunks + chunk_page_size - 1) // chunk_page_size,
                'items': [
                    {
                        'id': chunk.id,
                        'chunk_index': chunk.chunk_index,
                        'content': chunk.content,
                        'start_index': chunk.start_index,
                        'end_index': chunk.end_index,
                        'page_number': chunk.page_number,
                    }
                    for chunk in chunk_list
                ]
            }
        else:
            content_data['chunk_count'] = document.chunks.count()

        return Response(content_data)

    def destroy(self, request, *args, **kwargs):
        """删除文档时同时删除向量数据"""
        document = self.get_object()

        try:
            service = KnowledgeBaseService(document.knowledge_base)
            service.delete_document(document)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return Response(
                {'error': f'删除失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentChunkViewSet(BaseModelViewSet):
    """文档分块视图集"""
    queryset = DocumentChunk.objects.all()
    serializer_class = DocumentChunkSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['document', 'document__knowledge_base']
    search_fields = ['content']
    ordering_fields = ['created_at', 'chunk_index']
    ordering = ['document', 'chunk_index']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + 模型权限）
        return super().get_permissions()

    def get_queryset(self):
        """只返回用户有权限访问的分块"""
        user = self.request.user
        if user.is_superuser:
            return DocumentChunk.objects.all()

        # 普通用户只能看到自己是成员的项目的分块
        return DocumentChunk.objects.filter(
            document__knowledge_base__project__members__user=user
        ).distinct()


class QueryLogViewSet(BaseModelViewSet):
    """查询日志视图集"""
    queryset = QueryLog.objects.all()
    serializer_class = QueryLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['knowledge_base', 'user']
    search_fields = ['query', 'response']
    ordering_fields = ['created_at', 'total_time']
    ordering = ['-created_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + 模型权限）
        return super().get_permissions()

    def get_queryset(self):
        """只返回用户有权限访问的查询日志"""
        user = self.request.user
        if user.is_superuser:
            return QueryLog.objects.all()

        # 普通用户只能看到自己是成员的项目的查询日志
        return QueryLog.objects.filter(
            knowledge_base__project__members__user=user
        ).distinct()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def embedding_services(request):
    """获取可用的嵌入服务选项"""
    services = []
    for value, label in KnowledgeBase.EMBEDDING_SERVICE_CHOICES:
        services.append({
            'value': value,
            'label': label
        })
    
    return Response({
        'services': services
    })
