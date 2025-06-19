 
from django.contrib import admin
from django.urls import path
from django.urls import path, include

 
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static
 
from django.conf import settings
 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('company/', include('company.urls')),
    path('finance/', include('finance.urls')),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += staticfiles_urlpatterns()