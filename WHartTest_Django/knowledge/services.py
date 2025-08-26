"""
知识库服务模块
提供文档处理、向量化、检索等核心功能
"""
import os
import time
import hashlib
from typing import List, Dict, Any

# 设置完全离线模式，避免任何网络请求
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
# 禁用网络连接
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
# 设置极短的连接超时，强制快速失败
os.environ['HF_HUB_TIMEOUT'] = '1'
os.environ['REQUESTS_TIMEOUT'] = '1'
from django.conf import settings
from django.utils import timezone
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, UnstructuredPowerPointLoader,
    TextLoader, UnstructuredMarkdownLoader, UnstructuredHTMLLoader,
    WebBaseLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document as LangChainDocument
from .models import KnowledgeBase, Document, DocumentChunk, QueryLog
import logging
import requests
from typing import List
from langchain.embeddings.base import Embeddings

logger = logging.getLogger(__name__)


class CustomAPIEmbeddings(Embeddings):
    """自定义HTTP API嵌入服务"""
    
    def __init__(self, api_base_url: str, api_key: str = None, custom_headers: dict = None, model_name: str = 'text-embedding'):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        self.custom_headers = custom_headers or {}
        self.model_name = model_name
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入多个文档"""
        return [self.embed_query(text) for text in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        headers = {
            'Content-Type': 'application/json',
            **self.custom_headers
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        data = {
            'input': text,
            'model': self.model_name  # 使用配置的模型名
        }
        
        try:
            response = requests.post(
                self.api_base_url,  # 直接使用完整的API URL
                json=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if 'data' in result and len(result['data']) > 0:
                return result['data'][0]['embedding']
            else:
                raise ValueError(f"API响应格式错误: {result}")
                
        except Exception as e:
            raise RuntimeError(f"自定义API嵌入失败: {str(e)}")




class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        self.loaders = {
            'pdf': PyPDFLoader,
            'docx': Docx2txtLoader,
            'pptx': UnstructuredPowerPointLoader,
            'txt': TextLoader,
            'md': UnstructuredMarkdownLoader,
            'html': UnstructuredHTMLLoader,
        }

    def load_document(self, document: Document) -> List[LangChainDocument]:
        """加载文档内容"""
        try:
            logger.info(f"开始加载文档: {document.title} (ID: {document.id})")
            logger.info(f"文档类型: {document.document_type}")

            # 优先级：URL > 文本内容 > 文件
            if document.document_type == 'url' and document.url:
                logger.info(f"从URL加载: {document.url}")
                return self._load_from_url(document.url)
            elif document.content:
                # 如果有文本内容，直接使用
                logger.info("从文本内容加载")
                return self._load_from_content(document.content, document.title)
            elif document.file and hasattr(document.file, 'path'):
                file_path = document.file.path
                logger.info(f"从文件加载: {file_path}")

                # Windows路径兼容性处理
                if os.name == 'nt':  # Windows系统
                    file_path = os.path.normpath(file_path)
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(file_path)

                # 检查文件是否存在
                if os.path.exists(file_path):
                    logger.info(f"文件存在，开始加载: {file_path}")
                    return self._load_from_file(document)
                else:
                    raise FileNotFoundError(f"文件不存在: {file_path}")
            else:
                raise ValueError("文档没有可用的内容源（无URL、无文本内容、无文件）")
        except Exception as e:
            logger.error(f"加载文档失败 {document.id}: {e}")
            raise

    def _load_from_url(self, url: str) -> List[LangChainDocument]:
        """从URL加载文档"""
        loader = WebBaseLoader(url)
        return loader.load()

    def _load_from_content(self, content: str, title: str) -> List[LangChainDocument]:
        """从文本内容加载文档"""
        return [LangChainDocument(
            page_content=content,
            metadata={"source": title, "title": title}
        )]

    def _load_from_file(self, document: Document) -> List[LangChainDocument]:
        """从文件加载文档"""
        file_path = document.file.path

        # Windows路径兼容性处理
        if os.name == 'nt':  # Windows系统
            # 确保路径使用正确的分隔符
            file_path = os.path.normpath(file_path)
            # 转换为绝对路径
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

        logger.info(f"尝试加载文件: {file_path}")

        # 再次检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        loader_class = self.loaders.get(document.document_type)
        if not loader_class:
            raise ValueError(f"不支持的文档类型: {document.document_type}")

        try:
            # 对于文本文件，使用UTF-8编码
            if document.document_type == 'txt':
                loader = loader_class(file_path, encoding='utf-8')
            else:
                loader = loader_class(file_path)

            docs = loader.load()

            # 检查是否成功加载内容
            if not docs:
                raise ValueError(f"文档加载失败，没有内容: {file_path}")

            logger.info(f"成功加载文档，页数: {len(docs)}")

            # 添加元数据
            for doc in docs:
                doc.metadata.update({
                    "source": document.title,
                    "document_id": str(document.id),
                    "document_type": document.document_type,
                    "title": document.title,
                    "file_path": file_path
                })

            return docs

        except Exception as e:
            logger.error(f"文档加载器失败: {e}")
            # 如果是文本文件，尝试直接读取
            if document.document_type == 'txt':
                try:
                    logger.info("尝试直接读取文本文件...")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if not content.strip():
                        raise ValueError("文件内容为空")

                    return [LangChainDocument(
                        page_content=content,
                        metadata={
                            "source": document.title,
                            "document_id": str(document.id),
                            "document_type": document.document_type,
                            "title": document.title,
                            "file_path": file_path
                        }
                    )]
                except Exception as read_error:
                    logger.error(f"直接读取文件也失败: {read_error}")
                    raise
            else:
                raise


class VectorStoreManager:
    """向量存储管理器"""

    # 类级别的向量存储缓存
    _vector_store_cache = {}
    _embeddings_cache = {}

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.embeddings = self._get_embeddings_instance(knowledge_base)
        self._log_embedding_info()

    def _get_embeddings_instance(self, knowledge_base):
        """获取嵌入模型实例，支持多种服务类型"""
        cache_key = f"{knowledge_base.embedding_service}_{knowledge_base.id}"
        if cache_key not in self._embeddings_cache:
            embedding_service = knowledge_base.embedding_service
            
            try:
                if embedding_service == 'openai':
                    # OpenAI Embeddings
                    self._embeddings_cache[cache_key] = self._create_openai_embeddings(knowledge_base)
                elif embedding_service == 'azure_openai':
                    # Azure OpenAI Embeddings
                    self._embeddings_cache[cache_key] = self._create_azure_embeddings(knowledge_base)
                elif embedding_service == 'ollama':
                    # Ollama Embeddings
                    self._embeddings_cache[cache_key] = self._create_ollama_embeddings(knowledge_base)
                elif embedding_service == 'custom':
                    # 自定义HTTP API
                    self._embeddings_cache[cache_key] = self._create_custom_api_embeddings(knowledge_base)
                else:
                    # 不支持的嵌入服务
                    raise ValueError(f"不支持的嵌入服务: {embedding_service}")
                    
                # 测试嵌入功能
                test_embedding = self._embeddings_cache[cache_key].embed_query("模型功能测试")
                logger.info(f"✅ 嵌入模型测试成功: {embedding_service}, 维度: {len(test_embedding)}")
                
            except Exception as e:
                logger.error(f"❌ 嵌入服务 {embedding_service} 初始化失败: {str(e)}")
                raise
                
        return self._embeddings_cache[cache_key]
    
    def _create_openai_embeddings(self, knowledge_base):
        """创建OpenAI Embeddings实例"""
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            raise ImportError("需要安装langchain-openai: pip install langchain-openai")
        
        kwargs = {
            'model': knowledge_base.model_name or 'text-embedding-ada-002',
        }
        
        if knowledge_base.api_key:
            kwargs['api_key'] = knowledge_base.api_key
        if knowledge_base.api_base_url:
            kwargs['base_url'] = knowledge_base.api_base_url
            
        logger.info(f"🚀 初始化OpenAI嵌入模型: {kwargs['model']}")
        return OpenAIEmbeddings(**kwargs)
    
    def _create_azure_embeddings(self, knowledge_base):
        """创建Azure OpenAI Embeddings实例"""
        try:
            from langchain_openai import AzureOpenAIEmbeddings
        except ImportError:
            raise ImportError("需要安装langchain-openai: pip install langchain-openai")
        
        if not all([knowledge_base.api_key, knowledge_base.api_base_url]):
            raise ValueError("Azure OpenAI需要配置api_key和api_base_url")
        
        kwargs = {
            'model': knowledge_base.model_name or 'text-embedding-ada-002',
            'api_key': knowledge_base.api_key,
            'azure_endpoint': knowledge_base.api_base_url,
            'api_version': '2024-02-15-preview',  # 默认版本
        }
        
        # 部署名默认使用模型名
        kwargs['deployment'] = knowledge_base.model_name or 'text-embedding-ada-002'
            
        logger.info(f"🚀 初始化Azure OpenAI嵌入模型: {kwargs['model']}")
        return AzureOpenAIEmbeddings(**kwargs)
    
    def _create_ollama_embeddings(self, knowledge_base):
        """创建Ollama Embeddings实例"""
        try:
            from langchain_ollama import OllamaEmbeddings
        except ImportError:
            raise ImportError("需要安装langchain-ollama: pip install langchain-ollama")
        
        kwargs = {
            'model': knowledge_base.model_name or 'nomic-embed-text',
        }
        
        if knowledge_base.api_base_url:
            kwargs['base_url'] = knowledge_base.api_base_url
        else:
            kwargs['base_url'] = 'http://localhost:11434'  # Ollama默认地址
            
        logger.info(f"🚀 初始化Ollama嵌入模型: {kwargs['model']}")
        return OllamaEmbeddings(**kwargs)
    
    def _create_custom_api_embeddings(self, knowledge_base):
        """创建自定义API Embeddings实例"""
        if not knowledge_base.api_base_url:
            raise ValueError("自定义API需要配置api_base_url")
        
        logger.info(f"🚀 初始化自定义API嵌入模型: {knowledge_base.api_base_url}")
        return CustomAPIEmbeddings(
            api_base_url=knowledge_base.api_base_url,
            api_key=knowledge_base.api_key,
            custom_headers={},  # 不再使用数据库中的custom_headers字段
            model_name=knowledge_base.model_name
        )
    
    def _log_embedding_info(self):
        """记录嵌入模型信息"""
        embedding_type = type(self.embeddings).__name__
        logger.info(f"   🌟 知识库: {self.knowledge_base.name}")
        logger.info(f"   🎯 配置的嵌入模型: {self.knowledge_base.model_name}")
        logger.info(f"   ✅ 实际使用的嵌入模型: {embedding_type}")

        # 模型说明
        if embedding_type == "OpenAIEmbeddings":
            logger.info(f"   🎉 说明: 使用OpenAI嵌入API服务")
        elif embedding_type == "AzureOpenAIEmbeddings":
            logger.info(f"   🎉 说明: 使用Azure OpenAI嵌入API服务")
        elif embedding_type == "OllamaEmbeddings":
            logger.info(f"   🎉 说明: 使用Ollama本地API嵌入服务")
        elif embedding_type == "CustomAPIEmbeddings":
            logger.info(f"   🎉 说明: 使用自定义HTTP API嵌入服务")

        self._vector_store = None
        embedding_type = type(self.embeddings).__name__
        logger.info(f"🤖 向量存储管理器初始化完成:")
        logger.info(f"   📋 知识库: {self.knowledge_base.name} (ID: {self.knowledge_base.id})")
        logger.info(f"   🎯 配置的嵌入模型: {self.knowledge_base.model_name}")
        logger.info(f"   ✅ 实际使用的嵌入模型: {embedding_type}")
        logger.info(f"   💾 向量存储类型: ChromaDB")

    @property
    def vector_store(self):
        """获取向量存储实例（带缓存）"""
        if self._vector_store is None:
            # 使用知识库ID作为缓存键
            cache_key = str(self.knowledge_base.id)

            if cache_key not in self._vector_store_cache:
                logger.info(f"创建新的向量存储实例: {cache_key}")
                self._vector_store_cache[cache_key] = self._create_vector_store()

                # 创建后立即检查和修复权限
                persist_directory = os.path.join(
                    settings.MEDIA_ROOT,
                    'knowledge_bases',
                    str(self.knowledge_base.id),
                    'chroma_db'
                )
                self._ensure_permissions(persist_directory)
            else:
                logger.info(f"使用缓存的向量存储实例: {cache_key}")

            self._vector_store = self._vector_store_cache[cache_key]

        return self._vector_store

    @classmethod
    def clear_cache(cls, knowledge_base_id=None):
        """清理向量存储缓存"""
        if knowledge_base_id:
            # 清理特定知识库的缓存
            cache_key = str(knowledge_base_id)
            if cache_key in cls._vector_store_cache:
                del cls._vector_store_cache[cache_key]
                logger.info(f"已清理知识库 {cache_key} 的向量存储缓存")

            # 同时清理ChromaDB持久化目录
            try:
                import shutil
                persist_directory = os.path.join(
                    settings.MEDIA_ROOT,
                    'knowledge_bases',
                    str(knowledge_base_id),
                    'chroma_db'
                )
                if os.path.exists(persist_directory):
                    shutil.rmtree(persist_directory)
                    logger.info(f"已清理知识库 {knowledge_base_id} 的ChromaDB持久化数据")
            except Exception as e:
                logger.warning(f"清理ChromaDB持久化数据失败: {e}")
        else:
            # 清理所有缓存
            cls._vector_store_cache.clear()
            cls._embeddings_cache.clear()
            logger.info("已清理所有向量存储缓存")

    def _create_vector_store(self):
        """创建ChromaDB向量存储"""
        persist_directory = os.path.join(
            settings.MEDIA_ROOT,
            'knowledge_bases',
            str(self.knowledge_base.id),
            'chroma_db'
        )

        # 确保权限正确
        self._ensure_permissions(persist_directory)

        # 临时设置umask确保新文件有正确权限
        old_umask = os.umask(0o000)
        try:
            # 创建ChromaDB实例
            chroma_instance = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings,
                collection_name=f"kb_{self.knowledge_base.id}"
            )
        finally:
            # 恢复原来的umask
            os.umask(old_umask)

        # 创建后立即修复新生成的SQLite文件权限
        self._fix_sqlite_permissions_after_creation(persist_directory)

        return chroma_instance

    def _fix_sqlite_permissions_after_creation(self, persist_directory):
        """在ChromaDB创建SQLite文件后修复权限"""
        import time

        # 等待一小段时间确保文件已创建
        time.sleep(0.2)

        sqlite_files = [
            'chroma.sqlite3',
            'chroma.sqlite3-wal',
            'chroma.sqlite3-shm'
        ]

        # 多次尝试修复权限，因为文件可能延迟创建
        for attempt in range(3):
            files_fixed = 0
            for filename in sqlite_files:
                filepath = os.path.join(persist_directory, filename)
                if os.path.exists(filepath):
                    try:
                        # 先检查当前权限
                        current_mode = oct(os.stat(filepath).st_mode)[-3:]
                        if current_mode < '666':
                            os.chmod(filepath, 0o666)
                            logger.info(f"修复SQLite文件权限: {filepath} ({current_mode} -> 666)")
                        files_fixed += 1
                    except Exception as e:
                        logger.warning(f"修复SQLite文件权限失败 {filepath}: {e}")

            if files_fixed > 0:
                break

            # 如果没有找到文件，等待更长时间再试
            if attempt < 2:
                time.sleep(0.3)

        # 再次确保目录权限正确
        try:
            current_dir_mode = oct(os.stat(persist_directory).st_mode)[-3:]
            if current_dir_mode < '777':
                os.chmod(persist_directory, 0o777)
                logger.info(f"重新设置目录权限: {persist_directory} ({current_dir_mode} -> 777)")
        except Exception as e:
            logger.warning(f"重新设置目录权限失败: {e}")

        # 设置父目录权限
        try:
            parent_dir = os.path.dirname(persist_directory)
            parent_mode = oct(os.stat(parent_dir).st_mode)[-3:]
            if parent_mode < '777':
                os.chmod(parent_dir, 0o777)
                logger.info(f"设置父目录权限: {parent_dir} ({parent_mode} -> 777)")
        except Exception as e:
            logger.warning(f"设置父目录权限失败: {e}")

    def _ensure_permissions(self, persist_directory):
        """确保目录和文件权限正确"""
        try:
            # 确保目录存在
            os.makedirs(persist_directory, exist_ok=True)

            # 设置目录权限
            os.chmod(persist_directory, 0o777)

            # 设置父目录权限
            parent_dirs = [
                os.path.dirname(persist_directory),  # chroma_db的父目录
                os.path.dirname(os.path.dirname(persist_directory)),  # knowledge_bases目录
                os.path.dirname(os.path.dirname(os.path.dirname(persist_directory)))  # media目录
            ]

            for parent_dir in parent_dirs:
                if os.path.exists(parent_dir):
                    try:
                        os.chmod(parent_dir, 0o777)
                    except Exception as e:
                        logger.warning(f"设置父目录权限失败 {parent_dir}: {e}")

            # 修复现有SQLite文件权限
            sqlite_patterns = ['*.sqlite3', '*.sqlite3-wal', '*.sqlite3-shm', '*.db']
            for pattern in sqlite_patterns:
                import glob
                for filepath in glob.glob(os.path.join(persist_directory, pattern)):
                    try:
                        os.chmod(filepath, 0o666)
                        logger.info(f"修复现有SQLite文件权限: {filepath}")
                    except Exception as e:
                        logger.warning(f"修复SQLite文件权限失败 {filepath}: {e}")

        except Exception as e:
            logger.warning(f"确保权限失败: {e}")

    def add_documents(self, documents: List[LangChainDocument], document_obj: Document) -> List[str]:
        """添加文档到向量存储"""
        try:
            # 文档分块
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.knowledge_base.chunk_size,
                chunk_overlap=self.knowledge_base.chunk_overlap
            )
            chunks = text_splitter.split_documents(documents)

            # 临时设置umask确保新文件有正确权限
            old_umask = os.umask(0o000)
            try:
                # 添加到向量存储
                vector_ids = self.vector_store.add_documents(chunks)
            finally:
                # 恢复原来的umask
                os.umask(old_umask)

            # 添加文档后修复可能新创建的SQLite文件权限
            persist_directory = os.path.join(
                settings.MEDIA_ROOT,
                'knowledge_bases',
                str(self.knowledge_base.id),
                'chroma_db'
            )
            # 使用统一的权限确保方法
            self._ensure_permissions(persist_directory)
            # 额外的SQLite文件权限修复
            self._fix_sqlite_permissions_after_creation(persist_directory)

            # 保存分块信息到数据库
            self._save_chunks_to_db(chunks, vector_ids, document_obj)

            return vector_ids
        except Exception as e:
            logger.error(f"添加文档到向量存储失败: {e}")
            raise

    def _save_chunks_to_db(self, chunks: List[LangChainDocument], vector_ids: List[str], document_obj: Document):
        """保存分块信息到数据库"""
        chunk_objects = []
        for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids)):
            # 计算内容哈希
            content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()

            chunk_obj = DocumentChunk(
                document=document_obj,
                chunk_index=i,
                content=chunk.page_content,
                vector_id=vector_id,
                embedding_hash=content_hash,
                start_index=chunk.metadata.get('start_index'),
                end_index=chunk.metadata.get('end_index'),
                page_number=chunk.metadata.get('page')
            )
            chunk_objects.append(chunk_obj)

        DocumentChunk.objects.bulk_create(chunk_objects)

    def similarity_search(self, query: str, k: int = 5, score_threshold: float = 0.1) -> List[Dict[str, Any]]:
        """相似度搜索"""
        try:
            # 记录搜索开始信息
            embedding_type = type(self.embeddings).__name__
            logger.info(f"🔍 开始相似度搜索:")
            logger.info(f"   📝 查询: '{query}'")
            logger.info(f"   🤖 使用嵌入模型: {embedding_type}")
            logger.info(f"   🎯 返回数量: {k}, 相似度阈值: {score_threshold}")

            # 执行相似度搜索
            results = self.vector_store.similarity_search_with_score(query, k=k)

            logger.debug(f"原始搜索结果数量: {len(results)}")
            for i, (doc, score) in enumerate(results):
                logger.debug(f"结果 {i+1}: 原始相似度={score:.4f}, 内容={doc.page_content[:50]}...")

            # 处理相似度分数
            processed_results = []
            for doc, score in results:
                # 对于不同的向量存储和嵌入模型，相似度分数的含义不同
                processed_score = self._process_similarity_score(score)
                processed_results.append((doc, processed_score))
                logger.debug(f"处理后相似度: {score:.4f} -> {processed_score:.4f}")

            # 相似度过滤
            if processed_results:
                filtered_results = [
                    (doc, score) for doc, score in processed_results
                    if score >= score_threshold
                ]

                # 如果没有结果且阈值较高，降低阈值重试
                if not filtered_results and score_threshold > 0.1:
                    logger.info(f"阈值 {score_threshold} 过高，降低到 0.1 重试")
                    score_threshold = 0.1
                    filtered_results = [
                        (doc, score) for doc, score in processed_results
                        if score >= score_threshold
                    ]

                # 如果仍然没有结果，返回得分最高的结果
                if not filtered_results:
                    logger.info("没有结果通过阈值过滤，返回得分最高的结果")
                    # 按相似度排序，返回前k个
                    sorted_results = sorted(processed_results, key=lambda x: x[1], reverse=True)
                    filtered_results = sorted_results[:min(k, len(sorted_results))]
            else:
                filtered_results = []

            logger.info(f"📊 搜索结果统计:")
            logger.info(f"   🔢 原始结果数量: {len(results)}")
            logger.info(f"   ✅ 过滤后结果数量: {len(filtered_results)}")
            logger.info(f"   🎯 使用的阈值: {score_threshold}")

            # 格式化结果
            formatted_results = []
            for i, (doc, score) in enumerate(filtered_results):
                result = {
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'similarity_score': float(score)
                }
                formatted_results.append(result)

                # 记录每个结果的详细信息
                source = doc.metadata.get('source', '未知来源')
                percentage = score * 100
                logger.info(f"   📄 结果{i+1}: 相似度={score:.4f} ({percentage:.1f}%), 来源={source}")

            return formatted_results
        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            raise

    def _process_similarity_score(self, raw_score: float) -> float:
        """处理相似度分数，确保分数有意义"""
        try:
            # ChromaDB 使用距离度量，需要转换为相似度
            # 对于余弦距离：相似度 = 1 - 距离
            # 对于欧几里得距离：相似度 = 1 / (1 + 距离)

            if raw_score == 0.0:
                # 0距离表示完全匹配
                return 1.0

            # ChromaDB 默认使用余弦距离，范围是 [0, 2]
            # 转换为相似度：相似度 = 1 - (距离 / 2)
            if raw_score <= 2.0:
                similarity = 1.0 - (raw_score / 2.0)
                return max(0.0, min(1.0, similarity))  # 确保在 [0, 1] 范围内
            else:
                # 如果距离大于2，可能是欧几里得距离
                # 使用 1 / (1 + 距离) 公式
                similarity = 1.0 / (1.0 + raw_score)
                return similarity

        except Exception as e:
            logger.warning(f"处理相似度分数失败: {e}, 原始分数: {raw_score}")
            return max(0.0, min(1.0, raw_score))  # 返回原始分数，确保在合理范围内

    def delete_document(self, document: Document):
        """从向量存储中删除文档"""
        try:
            # 获取文档的所有分块
            chunks = document.chunks.all()
            vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]

            # 从向量存储中删除
            if vector_ids:
                self.vector_store.delete(vector_ids)

            # 从数据库中删除分块记录
            chunks.delete()
        except Exception as e:
            logger.error(f"删除文档向量失败: {e}")
            raise


class KnowledgeBaseService:
    """知识库服务"""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.document_processor = DocumentProcessor()
        self.vector_manager = VectorStoreManager(knowledge_base)

    def process_document(self, document: Document) -> bool:
        """处理文档"""
        try:
            # 更新状态为处理中
            document.status = 'processing'
            document.save()

            # 清理已存在的分块（如果有的话）
            document.chunks.all().delete()

            # 加载文档
            langchain_docs = self.document_processor.load_document(document)

            # 计算文档统计信息
            total_content = '\n'.join([doc.page_content for doc in langchain_docs])
            document.word_count = len(total_content.split())
            document.page_count = len(langchain_docs)

            # 向量化并存储
            vector_ids = self.vector_manager.add_documents(langchain_docs, document)

            # 更新状态为完成
            document.status = 'completed'
            document.processed_at = timezone.now()
            document.error_message = None
            document.save()

            logger.info(f"文档处理成功: {document.id}, 生成 {len(vector_ids)} 个分块")
            return True

        except Exception as e:
            # 更新状态为失败
            document.status = 'failed'
            document.error_message = str(e)
            document.save()

            logger.error(f"文档处理失败: {document.id}, 错误: {e}")
            return False

    def query(self, query_text: str, top_k: int = 5, similarity_threshold: float = 0.7,
              user=None) -> Dict[str, Any]:
        """查询知识库"""
        start_time = time.time()

        try:
            # 记录查询开始信息
            embedding_type = type(self.vector_manager.embeddings).__name__
            logger.info(f"🚀 知识库查询开始:")
            logger.info(f"   📚 知识库: {self.knowledge_base.name}")
            logger.info(f"   👤 用户: {user.username if user else '匿名'}")
            logger.info(f"   🤖 嵌入模型: {embedding_type}")
            logger.info(f"   💾 向量存储: ChromaDB")

            # 执行检索
            retrieval_start = time.time()
            search_results = self.vector_manager.similarity_search(
                query_text, k=top_k, score_threshold=similarity_threshold
            )
            retrieval_time = time.time() - retrieval_start

            # 生成回答（这里可以集成LLM）
            generation_start = time.time()
            answer = self._generate_answer(query_text, search_results)
            generation_time = time.time() - generation_start

            total_time = time.time() - start_time

            # 记录查询日志
            self._log_query(
                query_text, answer, search_results,
                retrieval_time, generation_time, total_time, user
            )

            # 记录查询完成信息
            logger.info(f"✅ 知识库查询完成:")
            logger.info(f"   ⏱️  检索耗时: {retrieval_time:.3f}s")
            logger.info(f"   🤖 生成耗时: {generation_time:.3f}s")
            logger.info(f"   🕐 总耗时: {total_time:.3f}s")
            logger.info(f"   📊 返回结果数: {len(search_results)}")

            return {
                'query': query_text,
                'answer': answer,
                'sources': search_results,
                'retrieval_time': retrieval_time,
                'generation_time': generation_time,
                'total_time': total_time
            }

        except Exception as e:
            logger.error(f"知识库查询失败: {e}")
            raise

    def _generate_answer(self, query: str, sources: List[Dict[str, Any]]) -> str:
        """生成回答（简单版本，后续可集成LLM）"""
        if not sources:
            return "抱歉，没有找到相关信息。"

        # 简单的基于检索结果的回答生成
        context = "\n\n".join([source['content'] for source in sources[:3]])
        return f"基于查询「{query}」检索到的相关内容：\n\n{context}"

    def _log_query(self, query: str, answer: str, sources: List[Dict[str, Any]],
                   retrieval_time: float, generation_time: float, total_time: float, user):
        """记录查询日志"""
        try:
            QueryLog.objects.create(
                knowledge_base=self.knowledge_base,
                user=user,
                query=query,
                response=answer,
                retrieved_chunks=[{
                    'content': source['content'][:200] + '...' if len(source['content']) > 200 else source['content'],
                    'metadata': source['metadata'],
                    'score': source['similarity_score']
                } for source in sources],
                similarity_scores=[source['similarity_score'] for source in sources],
                retrieval_time=retrieval_time,
                generation_time=generation_time,
                total_time=total_time
            )
        except Exception as e:
            logger.error(f"记录查询日志失败: {e}")

    def delete_document(self, document: Document):
        """删除文档"""
        try:
            # 从向量存储中删除
            self.vector_manager.delete_document(document)

            # 删除文件
            if document.file:
                if os.path.exists(document.file.path):
                    os.remove(document.file.path)

            # 删除数据库记录
            document.delete()

            # 清理向量存储缓存（因为内容已变化）
            VectorStoreManager.clear_cache(self.knowledge_base.id)

            logger.info(f"文档删除成功: {document.id}")

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            raise
