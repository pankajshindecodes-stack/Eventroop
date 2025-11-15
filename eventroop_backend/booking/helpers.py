def get_city_filtered_queryset(request, queryset):
    """
    Filters a queryset based on 'city' value sent in query params.
    """
    city = request.query_params.get('city')
    
    if city:
        return queryset.filter(location__city__iexact=city)
    
    return queryset
