from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10                      # default per page
    page_size_query_param = 'page_size' # client can override limit
    max_page_size = 100                 # upper cap
