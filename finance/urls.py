from django.urls import path
from .views import (
    CreateRefundAPIView, RefundListAPIView, ExcessDepositsAPIView,
    UnpaidInvoicesAPIView, InvoiceDetailsAPIView, CollectionCreateAPIView,
    CollectionListAPIView, AddExpenseAPIView, CalculateTotalView,
    ExpensesByCompanyAPIView, ExpenseUpdateView
)
from .reports import (
    CollectionCSVDownloadAPIView,
    FinancialSummaryView
)

urlpatterns = [
    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------
    path(
        'create/refund/',
        CreateRefundAPIView.as_view(),
        name='create-refund'
    ), 
    path(
        'refunds/',
        RefundListAPIView.as_view(),
        name='refund-list'
    ),  
    path(
        '<int:tenancy_id>/excess-deposits/',
        ExcessDepositsAPIView.as_view(),
        name='excess-deposits'
    ),

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------
    path(
        'unpaid-invoices/',
        UnpaidInvoicesAPIView.as_view(),
        name='unpaid-invoices'
    ),  # GET: Lists all unpaid invoices
    path(
        'invoice-details/<int:invoice_id>/',
        InvoiceDetailsAPIView.as_view(),
        name='invoice-details'
    ),  
    path(
        'create-collection/',
        CollectionCreateAPIView.as_view(),
        name='create-collection'
    ),  
    path(
        'collections/',
        CollectionListAPIView.as_view(),
        name='collection-list'
    ), 

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------
    path(
        'expenses/',
        AddExpenseAPIView.as_view(),
        name='expense-create'
    ),  
    path(
        'expenses/calculate-total/',
        CalculateTotalView.as_view(),
        name='calculate-total'
    ),  
    path(
        'expenses/company/<int:company_id>/',
        ExpensesByCompanyAPIView.as_view(),
        name='expenses-by-company'
    ), 
    path(
        'expenses/<int:pk>/',
        ExpenseUpdateView.as_view(),
        name='expense-detail'
    ), 

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    path(
        'collections/download/',
        CollectionCSVDownloadAPIView.as_view(),
        name='collection-csv-download'
    ),
    path(
        'income-expenses/<int:company_id>/',
        FinancialSummaryView.as_view(),
        name='expense-csv-download'
    ),
    
]
