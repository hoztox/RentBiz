
from django.urls import path
from  .views import *

urlpatterns = [

    # Expenses
    path('expenses/',AddExpenseAPIView.as_view(), name='expense-list-create'),
    path('expenses/calculate-total/',CalculateTotalView.as_view(), name='calculate-total'),
    path('expenses/company/<int:company_id>/', ExpensesByCompanyAPIView.as_view(), name='get-all-expenses'),
    path('expenses/<int:pk>/', ExpenseUpdateView.as_view(), name='invoice-detail'),
    

       
]



