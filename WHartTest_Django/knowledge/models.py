import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from projects.models import Project


class KnowledgeGlobalConfig(models.Model):
    """Global defaults for knowledge base indexing and retrieval."""

    EMBEDDING_SERVICE_CHOICES = [
        ("openai", "OpenAI"),
        ("azure_openai", "Azure OpenAI"),
        ("ollama", "Ollama"),
        ("xinference", "Xinference"),
        ("custom", "Custom API"),
    ]

    RERANKER_SERVICE_CHOICES = [
        ("none", "Disabled"),
        ("xinference", "Xinference"),
        ("custom", "Custom API"),
    ]

    CHUNK_STRATEGY_CHOICES = [
        ("recursive_character", "Fixed length"),
        ("heading_aware", "Structure aware"),
        ("markdown_header", "Markdown header"),
    ]

    embedding_service = models.CharField(
        _("Embedding service"),
        max_length=50,
        choices=EMBEDDING_SERVICE_CHOICES,
        default="custom",
        help_text=_("Embedding provider used for new or reprocessed documents."),
    )
    api_base_url = models.CharField(
        _("Embedding API URL"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_(
            "Embedding endpoint, for example https://api.openai.com/v1 or http://xinference:9997."
        ),
    )
    api_key = models.CharField(
        _("Embedding API key"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("Authentication key for the embedding service."),
    )
    model_name = models.CharField(
        _("Embedding model"),
        max_length=100,
        default="qwen3-vl-emb-2b",
        help_text=_("Model name used for embeddings."),
    )

    reranker_service = models.CharField(
        _("Reranker service"),
        max_length=50,
        choices=RERANKER_SERVICE_CHOICES,
        default="none",
        help_text=_("Optional reranker used after recall."),
    )
    reranker_api_url = models.CharField(
        _("Reranker API URL"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_(
            "Reranker endpoint. If empty, the embedding API base URL can be reused."
        ),
    )
    reranker_api_key = models.CharField(
        _("Reranker API key"),
        max_length=500,
        blank=True,
        null=True,
        help_text=_("Authentication key for the reranker service."),
    )
    reranker_model_name = models.CharField(
        _("Reranker model"),
        max_length=100,
        default="Qwen3-VL-Reranker-2B",
        blank=True,
        help_text=_("Model name used for reranking."),
    )

    chunk_size = models.PositiveIntegerField(_("Chunk size"), default=1000)
    chunk_overlap = models.PositiveIntegerField(_("Chunk overlap"), default=200)
    chunk_strategy = models.CharField(
        _("Chunk strategy"),
        max_length=50,
        choices=CHUNK_STRATEGY_CHOICES,
        default="recursive_character",
        help_text=_("Default chunking strategy for new or reprocessed documents."),
    )

    parent_child_enabled = models.BooleanField(
        _("Enable parent-child chunking"),
        default=False,
        help_text=_(
            "When enabled, documents are split into parent chunks (for context) "
            "and child chunks (for retrieval). Child chunks are indexed in the "
            "vector store; parent chunks are returned to the LLM."
        ),
    )
    parent_chunk_size = models.PositiveIntegerField(
        _("Parent chunk size"), default=2000,
        help_text=_("Character count for parent chunks."),
    )
    parent_chunk_overlap = models.PositiveIntegerField(
        _("Parent chunk overlap"), default=200,
        help_text=_("Character overlap between parent chunks."),
    )
    child_chunk_size = models.PositiveIntegerField(
        _("Child chunk size"), default=800,
        help_text=_(
            "Character count for child chunks. Should align with the embedding "
            "model's optimal input length."
        ),
    )
    child_chunk_overlap = models.PositiveIntegerField(
        _("Child chunk overlap"), default=200,
        help_text=_("Character overlap between child chunks."),
    )

    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_knowledge_configs",
        verbose_name=_("Updated by"),
    )

    class Meta:
        verbose_name = _("Knowledge global config")
        verbose_name_plural = _("Knowledge global config")

    def __str__(self):
        return f"Knowledge Global Config ({self.get_embedding_service_display()})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class KnowledgeBase(models.Model):
    """Knowledge base under a project."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Knowledge base name"), max_length=200)
    description = models.TextField(_("Description"), blank=True, null=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="knowledge_bases",
        verbose_name=_("Project"),
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_knowledge_bases",
        verbose_name=_("Creator"),
    )
    is_active = models.BooleanField(_("Is active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    chunk_size = models.PositiveIntegerField(_("Chunk size"), default=1000)
    chunk_overlap = models.PositiveIntegerField(_("Chunk overlap"), default=200)
    parent_chunk_size = models.PositiveIntegerField(
        _("Parent chunk size"), null=True, blank=True,
        help_text=_("Override global parent chunk size. Null uses global default."),
    )
    parent_chunk_overlap = models.PositiveIntegerField(
        _("Parent chunk overlap"), null=True, blank=True,
        help_text=_("Override global parent chunk overlap. Null uses global default."),
    )
    child_chunk_size = models.PositiveIntegerField(
        _("Child chunk size"), null=True, blank=True,
        help_text=_("Override global child chunk size. Null uses global default."),
    )
    child_chunk_overlap = models.PositiveIntegerField(
        _("Child chunk overlap"), null=True, blank=True,
        help_text=_("Override global child chunk overlap. Null uses global default."),
    )

    class Meta:
        verbose_name = _("Knowledge base")
        verbose_name_plural = _("Knowledge base")
        ordering = ["-created_at"]
        unique_together = ["project", "name"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


def document_upload_path(instance, filename):
    return f"knowledge_bases/{instance.knowledge_base.id}/documents/{filename}"


def document_image_upload_path(instance, filename):
    return f"knowledge_bases/{instance.document.knowledge_base.id}/images/{filename}"


class Document(models.Model):
    """Source document stored in a knowledge base."""

    DOCUMENT_TYPES = [
        ("pdf", "PDF"),
        ("docx", "Word"),
        ("doc", "Word (legacy)"),
        ("xlsx", "Excel"),
        ("xls", "Excel (legacy)"),
        ("pptx", "PowerPoint"),
        ("txt", "Text"),
        ("md", "Markdown"),
        ("html", "HTML"),
        ("url", "URL"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("Knowledge base"),
    )
    title = models.CharField(_("Document title"), max_length=200)
    document_type = models.CharField(
        _("Document type"),
        max_length=10,
        choices=DOCUMENT_TYPES,
    )
    file = models.FileField(
        _("File"),
        upload_to=document_upload_path,
        blank=True,
        null=True,
    )
    url = models.URLField(_("URL"), blank=True, null=True)
    content = models.TextField(_("Content"), blank=True, null=True)

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    error_message = models.TextField(_("Error message"), blank=True, null=True)

    file_size = models.PositiveIntegerField(_("File size"), null=True, blank=True)
    page_count = models.PositiveIntegerField(_("Page count"), null=True, blank=True)
    word_count = models.PositiveIntegerField(_("Word count"), null=True, blank=True)
    tags = models.JSONField(_("Tags"), default=list, blank=True)
    metadata = models.JSONField(_("Metadata"), default=dict, blank=True)
    module = models.CharField(_("Module"), max_length=100, blank=True, default="")
    version = models.CharField(_("Version"), max_length=100, blank=True, default="")
    business_domain = models.CharField(
        _("Business domain"),
        max_length=100,
        blank=True,
        default="",
    )
    document_stage = models.CharField(
        _("Document stage"),
        max_length=100,
        blank=True,
        default="",
    )

    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
        verbose_name=_("Uploader"),
    )
    uploaded_at = models.DateTimeField(_("Uploaded at"), auto_now_add=True)
    processed_at = models.DateTimeField(_("Processed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Document")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.knowledge_base.name} - {self.title}"

    @property
    def file_extension(self):
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return None


class DocumentChunk(models.Model):
    """Indexed chunk generated from a document."""

    CHUNK_LEVEL_CHOICES = [
        ("parent", "Parent"),
        ("child", "Child"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name=_("Document"),
    )
    chunk_index = models.PositiveIntegerField(_("Chunk index"))
    content = models.TextField(_("Content"))
    vector_id = models.CharField(_("Vector ID"), max_length=100, blank=True, null=True)
    embedding_hash = models.CharField(
        _("Embedding hash"),
        max_length=64,
        blank=True,
        null=True,
    )
    start_index = models.PositiveIntegerField(_("Start index"), null=True, blank=True)
    end_index = models.PositiveIntegerField(_("End index"), null=True, blank=True)
    page_number = models.PositiveIntegerField(_("Page number"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    parent_chunk = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent chunk"),
    )
    chunk_level = models.CharField(
        _("Chunk level"),
        max_length=10,
        choices=CHUNK_LEVEL_CHOICES,
        default="child",
    )

    class Meta:
        verbose_name = _("Document chunk")
        verbose_name_plural = _("Document chunk")
        ordering = ["document", "chunk_index"]
        unique_together = ["document", "chunk_index", "chunk_level"]

    def __str__(self):
        level_label = self.get_chunk_level_display()
        return f"{self.document.title} - {level_label} Chunk {self.chunk_index}"


class QueryLog(models.Model):
    """Query history for knowledge retrieval."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name="query_logs",
        verbose_name=_("Knowledge base"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="knowledge_queries",
        verbose_name=_("User"),
    )
    query = models.TextField(_("Query"))
    response = models.TextField(_("Response"), blank=True, null=True)
    retrieved_chunks = models.JSONField(_("Retrieved chunks"), default=list, blank=True)
    similarity_scores = models.JSONField(
        _("Similarity scores"),
        default=list,
        blank=True,
    )
    metadata_filter = models.JSONField(
        _("Metadata filter"),
        default=dict,
        blank=True,
    )
    retrieval_time = models.FloatField(_("Retrieval time"), null=True, blank=True)
    generation_time = models.FloatField(_("Generation time"), null=True, blank=True)
    total_time = models.FloatField(_("Total time"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Query log")
        verbose_name_plural = _("Query log")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.knowledge_base.name} - {self.query[:50]}..."
