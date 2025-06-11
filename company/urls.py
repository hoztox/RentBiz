
from django.urls import path
from  .views import *

urlpatterns = [
    
    
    # company login
    path('company-login/', CompanyLoginView.as_view(), name='company-login'),
    
    # user management
    path('users/create/', UserCreateAPIView.as_view(), name='user-create'),
    path('users/company/<int:company_id>/', UserListByCompanyAPIView.as_view(), name='user-list-by-company'),
    path('users/<int:user_id>/', UserDetailAPIView.as_view(), name='user-detail'),
    path('user/<int:user_id>/details/', UserDetailView.as_view(), name='user-detail'),
    

    # Building Properties                                                                           
    path('buildings/create/', BuildingCreateView.as_view(), name='building-create'),
    path('buildings/<int:pk>/', BuildingDetailView.as_view(), name='building-detail'),
    path('buildings/company/<int:company_id>/', BuildingByCompanyView.as_view(), name='building-by-company'),
    path('buildings/vacant/<int:company_id>/', BuildingsWithVacantUnitsView.as_view(), name='buildings-with-vacant-units'),
    path('buildings/occupied/<int:company_id>/', BuildingsWithOccupiedUnitsView.as_view(), name='buildings-with-vacant-units'),
    
    
    # unit Properties
    path('units/create/', UnitCreateView.as_view(), name='unit-create'),
    path('units/<int:pk>/', UnitDetailView.as_view(), name='unit-detail'),
    path('units/<int:id>/edit/', UnitEditAPIView.as_view(), name='unit-edit'),
    path('units/company/<int:company_id>/', UnitsByCompanyView.as_view(), name='units-by-company'),
    path('units/<int:building_id>/vacant-units/', VacantUnitsByBuildingView.as_view(), name='vacant-units-by-building'),
    path('units/<int:building_id>/occupied-units/', OccupiedUnitsByBuildingView.as_view(), name='vacant-units-by-building'),
   
    
    # unit type in masters
    path('unit-types/create/', UnitTypeListCreateAPIView.as_view(), name='unit-type-list-create'),
    path('unit-types/<int:id>/', UnitTypeDetailAPIView.as_view(), name='unit-type-detail'),
    path('unit-types/company/<int:company_id>/', UnitTypeByCompanyAPIView.as_view(), name='unit-type-by-company'),
    
     # document type in masters
    path('doc_type/create/', MasterDocumentListCreateAPIView.as_view(), name='unit-type-list-create'),
    path('doc_type/<int:id>/', MasterDocumentDetailAPIView.as_view(), name='unit-type-detail'),
    path('doc_type/company/<int:company_id>/', MasterDocumentByCompanyAPIView.as_view(), name='unit-type-by-company'),

    # ID type in masters
    path('id_type/create/',IDListCreateAPIView.as_view(), name='unit-type-list-create'),
    path('id_type/<int:id>/', IDDetailAPIView.as_view(), name='unit-type-detail'),
    path('id_type/company/<int:company_id>/', IDByCompanyAPIView.as_view(), name='unit-type-by-company'),
    
    # Currency in masters
    path('currency/create/',CurrencyListCreateView.as_view(), name='unit-type-list-create'),
    path('currencies/<int:pk>/', CurrencyDetailView.as_view(), name='currency-detail'),
    path('currency/company/<int:company_id>/', CurrencyByCompanyAPIView.as_view(), name='unit-type-by-company'),
    
    
    # Tenant 
    path('tenant/create/', TenantCreateView.as_view(), name='building-create'),
    path('tenant/<int:pk>/', TenantDetailView.as_view(), name='building-detail'),
    path('tenant/company/<int:company_id>/', TenantByCompanyView.as_view(), name='building-by-company'),
    
    
    # Chanrge code in masters
    path('charge_code/create/',ChargecodeListCreateAPIView.as_view(), name='unit-type-list-create'),
    path('charge_code/<int:id>/', ChargecodeDetailAPIView.as_view(), name='unit-type-detail'),
    path('charge_code/company/<int:company_id>/', ChargecodeByCompanyAPIView.as_view(), name='unit-type-by-company'),
    
    # Charges in masters
    path('charges/create/',ChargesListCreateAPIView.as_view(), name='unit-type-list-create'),
    path('charges/<int:id>/', ChargesDetailAPIView.as_view(), name='unit-type-detail'),
    path('charges/company/<int:company_id>/', ChargesByCompanyAPIView.as_view(), name='unit-type-by-company'),
    
    # Tenancy
    path('tenancies/preview-payment-schedule/', PaymentSchedulePreviewView.as_view(), name='payment-schedule-preview'),
    path('tenancies/preview-additional-charge-tax/', AdditionalChargeTaxPreviewView.as_view(), name='preview-additional-charge-tax'),
    path('tenancies/create/', TenancyCreateView.as_view(), name='tenancy-create'),
    path('tenancies/<int:pk>/', TenancyDetailView.as_view(), name='tenancy-detail'),
    path('tenancies/company/<int:company_id>/', TenancyByCompanyAPIView.as_view(), name='tenancies-by-company'),
    path('tenancies/pending/<int:company_id>/', PendingTenanciesByCompanyAPIView.as_view(), name='pending-tenancies-by-company'),
    path('tenancies/occupied/<int:company_id>/', ActiveTenanciesByCompanyAPIView.as_view(), name='pending-tenancies-by-company'),
    path('tenancies/termination/<int:company_id>/', TerminatiionTenanciesByCompanyAPIView.as_view(), name='pending-tenancies-by-company'),
    path('tenancies/close/<int:company_id>/', CloseTenanciesByCompanyAPIView.as_view(), name='pending-tenancies-by-company'),
    path('tenancy/<int:pk>/confirm/', ConfirmTenancyView.as_view(), name='confirm-tenancy'),
    path('tenancy/<int:tenancy_id>/renew/', TenancyRenewalView.as_view(), name='tenancy-renew'),
    path('tenancy/<int:tenancy_id>/download-pdf/', TenancyHTMLPDFView.as_view(), name='tenancy-download-pdf'),
    
    
    #Taxes
    path('taxes/<int:company_id>/<int:tax_id>/', TaxesAPIView.as_view(), name='taxes'),
    path('taxes/<int:company_id>/', TaxesAPIView.as_view(), name='taxes'),
    
]




