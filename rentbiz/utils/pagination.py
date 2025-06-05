
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomPagination(PageNumberPagination):
    page_size = 10  # Default page size
    page_size_query_param = 'page_size'  # Optional: allow clients to override page size
   

def paginate_queryset(queryset, request, serializer_class):
    paginator = CustomPagination()
    paginated_qs = paginator.paginate_queryset(queryset, request)
    serialized_data = serializer_class(paginated_qs, many=True)
    return paginator.get_paginated_response(serialized_data.data)

