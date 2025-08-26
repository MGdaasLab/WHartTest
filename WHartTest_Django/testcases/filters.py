import django_filters
from .models import TestCase

class TestCaseFilter(django_filters.FilterSet):
    """
    自定义测试用例过滤器，支持通过 'module_id' 和 'level' URL 参数进行过滤。
    """
    # 将 URL 参数 'module_id' 映射到 'module__id' 字段的精确查找
    # field_name='module__id' 表示我们希望过滤的是 TestCase 模型中 module 字段关联的对象的 id
    module_id = django_filters.NumberFilter(field_name='module__id', lookup_expr='exact')

    # 添加等级过滤器，支持通过 'level' URL 参数进行过滤
    # 例如: ?level=P2 将只返回等级为 P2 的测试用例
    # 使用 CharFilter 而不是 ChoiceFilter，这样可以更好地处理无效值
    level = django_filters.CharFilter(
        field_name='level',
        lookup_expr='exact'
    )

    class Meta:
        model = TestCase
        # fields 列表包含了我们希望 FilterSet 处理的字段。
        # DjangoFilterBackend 会查找与这些字段名匹配的 URL 参数。
        fields = ['module_id', 'level'] # 包含自定义的 module_id 和 level 过滤器