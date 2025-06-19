
from django.urls import path
from  .views import *


urlpatterns = [
    path('unpaid-invoices/', UnpaidInvoicesAPIView.as_view(), name='unpaid-invoices'),
    path('invoice-details/<int:invoice_id>/', InvoiceDetailsAPIView.as_view(), name='invoice-details'),
    path('create-collection/', CreateCollectionAPIView.as_view(), name='create-collection'),
]



