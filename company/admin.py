from django.contrib import admin
from .models import *


admin.site.register(Users)

admin.site.register(Building)
admin.site.register(DocumentType)

admin.site.register(Units)
admin.site.register(UnitDocumentType)

admin.site.register(UnitType)
admin.site.register(MasterDocumentType)
admin.site.register(IDType)
admin.site.register(ChargeCode)
admin.site.register(Charges)

admin.site.register(Currency)

admin.site.register(Tenant)
admin.site.register(TenantDocumentType)

admin.site.register(Tenancy)
admin.site.register(PaymentSchedule)
admin.site.register(AdditionalCharge)