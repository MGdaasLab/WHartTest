from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    # 大文档导入后单项目接口可达数千；接口选择树等场景按 500 拉取减少翻页次数
    max_page_size = 500
