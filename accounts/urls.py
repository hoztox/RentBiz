
from django.urls import path
from  .views import *

urlpatterns = [

    
    path('companies/', CompanyListCreateAPIView.as_view(), name='company-list-create'),
    path('company/create/', CompanyCreateAPIView.as_view(), name='company-create'),
    path('companies/<int:pk>/', CompanyDetailAPIView.as_view(), name='company-detail'),
    path('company/<int:company_id>/detail/', CompanyDetailView.as_view(), name='company-by-id'),
    path('countries/', CountryListView.as_view(), name='country-list'),
    path('countries/<int:country_id>/states/', StateListView.as_view(), name='state-list')
       
]



