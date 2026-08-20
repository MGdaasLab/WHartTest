import os
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import transaction
from django.db import models
from django.utils import timezone
from wharttest_django.viewsets import BaseModelViewSet
from .models import (
    KnowledgeBase,
    Document,
    DocumentChunk,
    QueryLog,
    KnowledgeGlobalConfig,
)
from .serializers import (
    KnowledgeBaseSerializer,
    DocumentUploadSerializer,
    DocumentSerializer,
    DocumentChunkSerializer,
    QueryLogSerializer,
    KnowledgeQuerySerializer,
    KnowledgeQueryResponseSerializer,
    KnowledgeGlobalConfigSerializer,
)
from .services import KnowledgeBaseService, VectorStoreManager
import time

logger = logging.getLogger(__name__)


def _mask_secret(secret):
    """对敏感字段进行脱敏展示。"""
    if not secret:
        return secret
    if len(secret) > 8:
        return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
    return "*" * len(secret)


def _restore_masked_secret(candidate, stored_secret):
    """
    将前端回传的脱敏值还原为数据库中的真实密钥。

    前端 GET 全局配置时会拿到脱敏后的 api_key / reranker_api_key，
    如果用户未修改该字段直接测试或保存，后端需要识别这种占位值并保留真实密钥。
    """
    if not candidate or not stored_secret:
        return candidate
    if candidate == _mask_secret(stored_secret):
        return stored_secret
    return candidate


def _dispatch_document_task(document):
    """派发文档处理任务：优先 Celery，不可用时同步执行"""
    from .tasks import process_document_task

    def _send():
        try:
            process_document_task.delay(str(document.id))
        except Exception as e:
            logger.warning(f"Celery 不可用 ({e})，降级为同步处理")
            process_document_task(str(document.id))

    transaction.on_commit(_send)


class KnowledgeGlobalConfigView(APIView):
    """知识库全局配置视图（单例模式）"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取全局配置"""
        config = KnowledgeGlobalConfig.get_config()
        serializer = KnowledgeGlobalConfigSerializer(config)
        data = serializer.data
        # 对API Key进行脱敏处理
        if data.get("api_key"):
            data["api_key"] = _mask_secret(data["api_key"])
        if data.get("reranker_api_key"):
            data["reranker_api_key"] = _mask_secret(data["reranker_api_key"])
        return Response(data)

    def put(self, request):
        """更新全局配置（仅管理员可操作）"""
        if not request.user.is_superuser:
            return Response(
                {"error": "只有管理员可以修改全局配置"},
                status=status.HTTP_403_FORBIDDEN,
            )

        config = KnowledgeGlobalConfig.get_config()
        data = request.data.copy()
        if "api_key" in data:
            data["api_key"] = _restore_masked_secret(
                data.get("api_key"), config.api_key
            )
        if "reranker_api_key" in data:
            data["reranker_api_key"] = _restore_masked_secret(
                data.get("reranker_api_key"), config.reranker_api_key
            )

        serializer = KnowledgeGlobalConfigSerializer(config, data=data, partial=True)

        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            # 清理全局配置缓存和嵌入模型缓存，使新配置立即生效
            VectorStoreManager.clear_global_config_cache()
            VectorStoreManager._embeddings_cache.clear()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KnowledgeBaseViewSet(BaseModelViewSet):
    """知识库视图集"""

    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["project", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]
    ordering = ["-created_at"]

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
        return KnowledgeBase.objects.filter(project__members__user=user).distinct()

    def perform_create(self, serializer):
        """创建知识库时自动设置创建人"""
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=["post"])
    def query(self, request, pk=None):
        """查询知识库"""
        knowledge_base = self.get_object()

        # 验证查询参数
        query_serializer = KnowledgeQuerySerializer(
            data=request.data, context={"request": request}
        )
        query_serializer.is_valid(raise_exception=True)

        try:
            # 执行查询
            service = KnowledgeBaseService(knowledge_base)
            result = service.query(
                query_text=query_serializer.validated_data["query"],
                top_k=query_serializer.validated_data.get("top_k", 5),
                similarity_threshold=query_serializer.validated_data.get(
                    "similarity_threshold", 0.1
                ),
                user=request.user,
            )

            # 序列化响应
            response_serializer = KnowledgeQueryResponseSerializer(result)
            return Response(response_serializer.data)

        except Exception as e:
            logger.error(f"知识库查询失败: {e}")
            return Response(
                {"error": f"查询失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """获取知识库统计信息"""
        knowledge_base = self.get_object()

        stats = {
            "document_count": knowledge_base.documents.count(),
            "chunk_count": DocumentChunk.objects.filter(
                document__knowledge_base=knowledge_base
            ).count(),
            "query_count": knowledge_base.query_logs.count(),
            "document_status_distribution": {},
            "recent_queries": knowledge_base.query_logs.order_by("-created_at")[
                :5
            ].values("query", "total_time", "created_at"),
        }

        # 文档状态分布
        status_counts = knowledge_base.documents.values("status").annotate(
            count=models.Count("status")
        )
        for item in status_counts:
            stats["document_status_distribution"][item["status"]] = item["count"]

        return Response(stats)

    @action(detail=True, methods=["get"])
    def content(self, request, pk=None):
        """查看知识库内容"""
        knowledge_base = self.get_object()

        # 获取查询参数
        search = request.query_params.get("search", "")
        document_type = request.query_params.get("document_type", "")
        status = request.query_params.get("status", "completed")
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))

        # 构建查询
        documents = knowledge_base.documents.filter(status=status)

        if search:
            documents = documents.filter(
                models.Q(title__icontains=search) | models.Q(content__icontains=search)
            )

        if document_type:
            documents = documents.filter(document_type=document_type)

        # 排序
        documents = documents.order_by("-uploaded_at")

        # 分页
        total_count = documents.count()
        start = (page - 1) * page_size
        end = start + page_size
        documents = documents[start:end]

        # 序列化文档数据
        content_data = []
        for doc in documents:
            doc_data = {
                "id": doc.id,
                "title": doc.title,
                "document_type": doc.document_type,
                "status": doc.status,
                "uploader_name": doc.uploader.username,
                "uploaded_at": doc.uploaded_at,
                "chunk_count": doc.chunks.count(),
                "content_preview": doc.content[:500]
                if doc.content
                else None,  # 内容预览
                "file_size": doc.file_size,
                "page_count": doc.page_count,
                "word_count": doc.word_count,
            }

            # 如果是文件类型，添加文件信息
            if doc.file:
                doc_data["file_name"] = doc.file.name.split("/")[-1]
                doc_data["file_url"] = (
                    doc.file.url if hasattr(doc.file, "url") else None
                )

            # 如果是URL类型，添加URL信息
            if doc.url:
                doc_data["url"] = doc.url

            content_data.append(doc_data)

        # 返回分页数据
        return Response(
            {
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
                "documents": content_data,
                "knowledge_base": {
                    "id": knowledge_base.id,
                    "name": knowledge_base.name,
                    "description": knowledge_base.description,
                },
            }
        )

    @action(detail=False, methods=["get"])
    def system_status(self, request):
        """检查知识库系统状态"""
        try:
            # 检查核心依赖
            deps = {}
            for mod in ("langchain_qdrant", "fastembed"):
                try:
                    __import__(mod)
                    deps[mod] = True
                except ImportError:
                    deps[mod] = False

            # 知识库统计
            total_kb = KnowledgeBase.objects.count()
            active_kb = KnowledgeBase.objects.filter(is_active=True).count()
            cache_count = len(VectorStoreManager._vector_store_cache)

            # Qdrant 连通性检测
            qdrant_ok = False
            try:
                qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:8918")
                from qdrant_client import QdrantClient

                client = QdrantClient(url=qdrant_url, timeout=3)
                client.get_collections()
                qdrant_ok = True
            except Exception:
                pass

            all_deps_ok = all(deps.values())
            overall = (
                "healthy"
                if all_deps_ok and qdrant_ok
                else "degraded"
                if qdrant_ok
                else "error"
            )

            return Response(
                {
                    "timestamp": time.time(),
                    "overall_status": overall,
                    "embedding": {
                        "type": "api_based",
                        "note": "使用 CustomAPIEmbeddings 通过 API 调用嵌入模型",
                    },
                    "dependencies": deps,
                    "qdrant": {
                        "connected": qdrant_ok,
                    },
                    "knowledge_bases": {
                        "total": total_kb,
                        "active": active_kb,
                        "cache_count": cache_count,
                    },
                }
            )

        except Exception as e:
            logger.error(f"系统状态检查失败: {e}")
            return Response(
                {"error": f"系统状态检查失败: {str(e)}", "overall_status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentViewSet(BaseModelViewSet):
    """文档视图集"""

    queryset = Document.objects.all()
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["knowledge_base", "document_type", "status"]
    search_fields = ["title", "content"]
    ordering_fields = ["uploaded_at", "processed_at", "title"]
    ordering = ["-uploaded_at"]

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + 模型权限）
        return super().get_permissions()

    def get_serializer_class(self):
        """根据操作返回不同的序列化器"""
        if self.action == "create":
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
        _dispatch_document_task(document)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """获取文档处理状态"""
        document = self.get_object()
        return Response(
            {
                "id": document.id,
                "status": document.status,
                "progress": getattr(document, "progress", 0),
                "error_message": document.error_message,
                "chunk_count": document.chunks.count(),
                "processed_at": document.processed_at,
            }
        )

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """重新处理文档"""
        document = self.get_object()

        document.status = "pending"
        document.error_message = ""
        document.save()

        _dispatch_document_task(document)

        return Response({"message": "文档重新处理已启动，请稍后查看状态"})

    def _get_document_content(self, document):
        """获取文档的实际内容"""
        try:
            # 如果数据库中有内容，直接返回
            if document.content:
                return document.content

            # 如果是文件类型，从文件中读取
            if document.file and hasattr(document.file, "path"):
                file_path = document.file.path

                # Windows路径兼容性处理
                if os.name == "nt":
                    file_path = os.path.normpath(file_path)
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(file_path)

                if os.path.exists(file_path):
                    # 根据文件类型选择读取方式
                    if document.document_type == "txt":
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                return f.read()
                        except UnicodeDecodeError:
                            # 如果UTF-8失败，尝试其他编码
                            with open(file_path, "r", encoding="gbk") as f:
                                return f.read()
                    else:
                        # 对于其他文件类型，使用DocumentProcessor加载
                        from .services import DocumentProcessor

                        processor = DocumentProcessor()
                        docs = processor.load_document(document)
                        if docs:
                            return "\n\n".join([doc.page_content for doc in docs])

            # 如果是URL类型，从分块中重建内容
            if document.document_type == "url" or not document.content:
                chunks = document.chunks.order_by("chunk_index")
                if chunks.exists():
                    return "\n\n".join([chunk.content for chunk in chunks])

            return None

        except Exception as e:
            logger.error(f"获取文档内容失败: {e}")
            return None

    @action(detail=True, methods=["get"])
    def content(self, request, pk=None):
        """获取文档完整内容"""
        document = self.get_object()

        # 检查文档状态
        if document.status != "completed":
            return Response(
                {"error": "文档尚未处理完成或处理失败"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 获取查询参数
        include_chunks = (
            request.query_params.get("include_chunks", "false").lower() == "true"
        )
        chunk_page = int(request.query_params.get("chunk_page", 1))
        chunk_page_size = int(request.query_params.get("chunk_page_size", 10))

        # 获取文档实际内容
        document_content = self._get_document_content(document)

        # 基础文档信息
        content_data = {
            "id": document.id,
            "title": document.title,
            "document_type": document.document_type,
            "status": document.status,
            "content": document_content,
            "uploader_name": document.uploader.username,
            "uploaded_at": document.uploaded_at,
            "processed_at": document.processed_at,
            "file_size": document.file_size,
            "page_count": document.page_count,
            "word_count": document.word_count,
            "knowledge_base": {
                "id": document.knowledge_base.id,
                "name": document.knowledge_base.name,
            },
        }

        # 如果是文件类型，添加文件信息
        if document.file:
            content_data["file_name"] = document.file.name.split("/")[-1]
            content_data["file_url"] = (
                document.file.url if hasattr(document.file, "url") else None
            )

        # 如果是URL类型，添加URL信息
        if document.url:
            content_data["url"] = document.url

        # 如果需要包含分块信息
        if include_chunks:
            chunks = document.chunks.order_by("chunk_index")
            total_chunks = chunks.count()

            # 分页处理分块
            start = (chunk_page - 1) * chunk_page_size
            end = start + chunk_page_size
            chunk_list = chunks[start:end]

            content_data["chunks"] = {
                "total_count": total_chunks,
                "page": chunk_page,
                "page_size": chunk_page_size,
                "total_pages": (total_chunks + chunk_page_size - 1) // chunk_page_size,
                "items": [
                    {
                        "id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "start_index": chunk.start_index,
                        "end_index": chunk.end_index,
                        "page_number": chunk.page_number,
                    }
                    for chunk in chunk_list
                ],
            }
        else:
            content_data["chunk_count"] = document.chunks.count()

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
                {"error": f"删除失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentChunkViewSet(BaseModelViewSet):
    """文档分块视图集"""

    queryset = DocumentChunk.objects.all()
    serializer_class = DocumentChunkSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["document", "document__knowledge_base"]
    search_fields = ["content"]
    ordering_fields = ["created_at", "chunk_index"]
    ordering = ["document", "chunk_index"]

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
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["knowledge_base", "user"]
    search_fields = ["query", "response"]
    ordering_fields = ["created_at", "total_time"]
    ordering = ["-created_at"]

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def embedding_services(request):
    """获取可用的嵌入服务选项"""
    services = []
    for value, label in KnowledgeGlobalConfig.EMBEDDING_SERVICE_CHOICES:
        services.append({"value": value, "label": label})

    return Response({"services": services})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def test_embedding_connection(request):
    """测试嵌入服务连接"""
    import requests as http_requests

    config = KnowledgeGlobalConfig.get_config()
    embedding_service = request.data.get("embedding_service")
    api_base_url = request.data.get("api_base_url", "").rstrip("/")
    api_key = request.data.get("api_key")
    if api_key is None:
        api_key = config.api_key or ""
    else:
        api_key = _restore_masked_secret(api_key, config.api_key)
    model_name = request.data.get("model_name", "")

    logger.info(
        f"[嵌入测试] 收到请求: embedding_service={embedding_service}, api_base_url={api_base_url}, model_name={model_name}"
    )

    if not embedding_service:
        return Response({"error": "请选择嵌入服务"}, status=status.HTTP_400_BAD_REQUEST)
    if not api_base_url:
        return Response(
            {"error": "请输入API基础URL"}, status=status.HTTP_400_BAD_REQUEST
        )
    if not model_name:
        return Response({"error": "请输入模型名称"}, status=status.HTTP_400_BAD_REQUEST)

    # 检查是否需要 API 密钥
    if embedding_service in ["openai", "azure_openai"] and not api_key:
        service_name = "OpenAI" if embedding_service == "openai" else "Azure OpenAI"
        return Response(
            {"error": f"{service_name} 服务需要API密钥"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    test_text = "This is a test embedding request."

    try:
        if embedding_service == "openai":
            test_url = f"{api_base_url}/embeddings"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            request_body = {"input": test_text, "model": model_name}

        elif embedding_service == "azure_openai":
            test_url = f"{api_base_url}/openai/deployments/{model_name}/embeddings?api-version=2024-02-15-preview"
            headers = {"Content-Type": "application/json", "api-key": api_key}
            request_body = {"input": test_text}

        elif embedding_service == "ollama":
            test_url = f"{api_base_url}/api/embeddings"
            headers = {"Content-Type": "application/json"}
            request_body = {"model": model_name, "prompt": test_text}

        elif embedding_service == "xinference":
            test_url = f"{api_base_url}/v1/embeddings"
            headers = {"Content-Type": "application/json"}
            request_body = {"input": test_text, "model": model_name}

        elif embedding_service == "custom":
            test_url = api_base_url
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            request_body = {"input": test_text, "model": model_name}
        else:
            return Response(
                {"error": f"不支持的嵌入服务类型: {embedding_service}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"[嵌入测试] 发送请求: URL={test_url}")

        session = http_requests.Session()
        session.trust_env = False
        response = session.post(
            test_url, json=request_body, headers=headers, timeout=30
        )

        logger.info(f"[嵌入测试] 响应状态: {response.status_code}")

        if response.ok:
            data = response.json()

            # 验证返回的数据包含 embedding
            has_embedding = False
            if embedding_service == "ollama":
                # Ollama 返回格式: {"embedding": [...]}
                has_embedding = data.get("embedding") and isinstance(
                    data["embedding"], list
                )
            else:
                # OpenAI 兼容格式 (Xinference, OpenAI, Azure, Custom)
                has_embedding = (
                    data.get("data")
                    and isinstance(data["data"], list)
                    and len(data["data"]) > 0
                    and data["data"][0].get("embedding")
                )

            if has_embedding:
                logger.info("[嵌入测试] 测试成功")
                return Response(
                    {"success": True, "message": "嵌入模型测试成功！服务运行正常"}
                )
            else:
                logger.warning(f"[嵌入测试] 数据格式异常: {str(data)[:200]}")
                return Response(
                    {
                        "success": False,
                        "message": "服务响应成功但数据格式异常，请检查配置",
                    }
                )
        else:
            error_text = response.text[:500]
            logger.warning(
                f"[嵌入测试] HTTP错误: {response.status_code} - {error_text}"
            )
            return Response(
                {
                    "success": False,
                    "message": f"嵌入模型测试失败: HTTP {response.status_code} - {error_text}",
                }
            )

    except http_requests.Timeout:
        logger.warning("[嵌入测试] 请求超时")
        return Response(
            {"success": False, "message": "请求超时，请检查服务是否正常运行"}
        )
    except http_requests.ConnectionError as e:
        logger.warning(f"[嵌入测试] 连接失败: {e}")
        return Response(
            {"success": False, "message": f"无法连接到服务，请检查URL和网络: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"[嵌入测试] 未知错误: {e}", exc_info=True)
        return Response({"success": False, "message": f"嵌入模型测试失败: {str(e)}"})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def test_reranker_connection(request):
    """测试 Reranker 服务连接"""
    import requests as http_requests

    config = KnowledgeGlobalConfig.get_config()
    reranker_service = request.data.get("reranker_service")
    reranker_api_url = request.data.get("reranker_api_url", "").rstrip("/")
    reranker_api_key = request.data.get("reranker_api_key")
    if reranker_api_key is None:
        reranker_api_key = config.reranker_api_key or ""
    else:
        reranker_api_key = _restore_masked_secret(
            reranker_api_key, config.reranker_api_key
        )
    reranker_model_name = request.data.get("reranker_model_name", "")

    logger.info(
        f"[Reranker测试] 收到请求: service={reranker_service}, url={reranker_api_url}, model={reranker_model_name}"
    )

    if not reranker_service or reranker_service == "none":
        return Response(
            {"error": "请选择 Reranker 服务"}, status=status.HTTP_400_BAD_REQUEST
        )
    if not reranker_api_url:
        return Response(
            {"error": "请输入 Reranker API 地址"}, status=status.HTTP_400_BAD_REQUEST
        )
    if not reranker_model_name:
        return Response(
            {"error": "请输入 Reranker 模型名称"}, status=status.HTTP_400_BAD_REQUEST
        )

    test_query = "What is machine learning?"
    test_documents = [
        "Machine learning is a subset of AI.",
        "The weather is nice today.",
    ]

    try:
        if reranker_service == "xinference":
            test_url = f"{reranker_api_url}/v1/rerank"
            headers = {"Content-Type": "application/json"}
            request_body = {
                "model": reranker_model_name,
                "query": test_query,
                "documents": test_documents,
            }
        elif reranker_service == "custom":
            test_url = reranker_api_url
            headers = {"Content-Type": "application/json"}
            if reranker_api_key:
                headers["Authorization"] = f"Bearer {reranker_api_key}"
            request_body = {
                "model": reranker_model_name,
                "query": test_query,
                "documents": test_documents,
            }
        else:
            return Response(
                {"error": f"不支持的 Reranker 服务类型: {reranker_service}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"[Reranker测试] 发送请求: URL={test_url}")

        session = http_requests.Session()
        session.trust_env = False
        response = session.post(
            test_url, json=request_body, headers=headers, timeout=30
        )

        logger.info(f"[Reranker测试] 响应状态: {response.status_code}")

        if response.ok:
            data = response.json()
            # Xinference rerank 返回格式: {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
            has_results = (
                data.get("results")
                and isinstance(data["results"], list)
                and len(data["results"]) > 0
            )

            if has_results:
                logger.info("[Reranker测试] 测试成功")
                return Response(
                    {"success": True, "message": "Reranker 服务测试成功！服务运行正常"}
                )
            else:
                logger.warning(f"[Reranker测试] 数据格式异常: {str(data)[:200]}")
                return Response(
                    {
                        "success": False,
                        "message": "服务响应成功但数据格式异常，请检查配置",
                    }
                )
        else:
            error_text = response.text[:500]
            logger.warning(
                f"[Reranker测试] HTTP错误: {response.status_code} - {error_text}"
            )
            return Response(
                {
                    "success": False,
                    "message": f"Reranker 测试失败: HTTP {response.status_code} - {error_text}",
                }
            )

    except http_requests.Timeout:
        logger.warning("[Reranker测试] 请求超时")
        return Response(
            {"success": False, "message": "请求超时，请检查服务是否正常运行"}
        )
    except http_requests.ConnectionError as e:
        logger.warning(f"[Reranker测试] 连接失败: {e}")
        return Response(
            {
                "success": False,
                "message": f"无法连接到 Reranker 服务，请检查URL和网络: {str(e)}",
            }
        )
    except Exception as e:
        logger.error(f"[Reranker测试] 未知错误: {e}", exc_info=True)
        return Response({"success": False, "message": f"Reranker 测试失败: {str(e)}"})
