import logging

import pymysql
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import NoSuchModuleError

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from wharttest_django.api_permissions import IsProjectMemberForResource
from wharttest_django.pagination import StandardPagination

from .models import ApiDatabaseConfig
from .serializers import ApiDatabaseConfigSerializer

logger = logging.getLogger(__name__)



class ApiDatabaseConfigViewSet(BaseModelViewSet):
    serializer_class = ApiDatabaseConfigSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'db_type']
    search_fields = ['name', 'host', 'database']
    ordering_fields = ['name', 'created_at', 'updated_at']

    def get_permissions(self):
        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),
            IsProjectMemberForResource(),
        ]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        return ApiDatabaseConfig.objects.filter(project_id=project_pk)

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_saved_connection(self, request, **kwargs):
        """Test connectivity for an existing saved database config."""
        db_config = self.get_object()
        return self._do_test_connection(
            db_type=db_config.db_type,
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
            user=db_config.username,
            password=db_config.password,
        )

    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection(self, request, **kwargs):
        """Test connectivity with ad-hoc connection parameters."""
        db_type = request.data.get('db_type', 'mysql')
        host = request.data.get('host')
        port_raw = request.data.get('port', 3306)
        database = request.data.get('database')
        user = request.data.get('user') or request.data.get('username')
        password = request.data.get('password')

        if not database or not all([host, user, password]):
            return Response(
                {"detail": "Missing required connection parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            port = int(port_raw)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid port number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self._do_test_connection(
            db_type=db_type,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    @staticmethod
    def _do_test_connection(*, db_type, host, port, database, user, password):
        """Execute a lightweight SELECT 1 against the target database."""
        validation_sql = "SELECT 1"
        try:
            if db_type == 'mysql':
                conn = pymysql.connect(
                    host=host, port=port, user=user,
                    password=password, database=database, connect_timeout=5,
                )
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.close()

            elif db_type == 'postgresql':
                conn = psycopg2.connect(
                    host=host, port=port, user=user,
                    password=password, dbname=database, connect_timeout=5,
                )
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.close()

            elif db_type == 'oracle':
                # Oracle 12c+ 默认是 CDB/PDB 架构，FREEPDB1 这类是 PDB 的
                # 服务名(service name)而非 SID，SQLAlchemy URL 中 /xxx 是 SID，
                # 服务名必须用 ?service_name=xxx 传参。
                # 先按服务名连接（现代 Oracle 标准），失败再回退 SID 格式。
                service_name_uri = (
                    f"oracle+oracledb://{user}:{password}"
                    f"@{host}:{port}?service_name={database}"
                )
                try:
                    engine = create_engine(service_name_uri)
                    with engine.connect() as conn:
                        conn.execute(text(validation_sql))
                except Exception as first_exc:
                    sid_uri = (
                        f"oracle+oracledb://{user}:{password}"
                        f"@{host}:{port}/{database}"
                    )
                    try:
                        engine = create_engine(sid_uri)
                        with engine.connect() as conn:
                            conn.execute(text(validation_sql))
                    except Exception:
                        raise first_exc

            else:
                return Response(
                    {"detail": f"Unsupported database type: {db_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({
                "connected": True,
                "db_type": db_type,
                "message": "Connection successful",
            })

        except NoSuchModuleError as e:
            return Response(
                {"detail": f"Connection failed: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": f"Connection failed: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
