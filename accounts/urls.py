
from django.urls import path
from  .views import *

urlpatterns = [
    
    # company Management
    path('companies/create/', CompanyCreateAPIView.as_view(), name='company-list-create'),
    path('companies/', CompanyListCreateAPIView.as_view(), name='company-list-create'),
   
    path('companies/<int:pk>/', CompanyDetailAPIView.as_view(), name='company-detail'),
       
]



