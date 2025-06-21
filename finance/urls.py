
from django.urls import path
from  .views import *


urlpatterns = [
    # Invoices
    path('unpaid-invoices/', UnpaidInvoicesAPIView.as_view(), name='unpaid-invoices'),
    path('invoice-details/<int:invoice_id>/', InvoiceDetailsAPIView.as_view(), name='invoice-details'),
    path('create-collection/', CreateCollectionAPIView.as_view(), name='create-collection'),
    path('collections/', CollectionListAPIView.as_view(), name='collection-list'),

    # Expenses
    path('expenses/',AddExpenseAPIView.as_view(), name='expense-list-create'),
    path('expenses/calculate-total/',CalculateTotalView.as_view(), name='calculate-total'),
    path('expenses/company/<int:company_id>/', ExpensesByCompanyAPIView.as_view(), name='get-all-expenses'),
    path('expenses/<int:pk>/', ExpenseUpdateView.as_view(), name='invoice-detail'),
        
]



