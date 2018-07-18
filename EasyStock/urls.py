"""EasyStock URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
# Use include() to add paths from the catalog application 
from django.conf.urls import include
from django.conf import settings
from django.conf.urls.static import static
#Add URL maps to redirect the base URL to our application
from django.views.generic import RedirectView


admin.site.site_header = "EasyStore Admin"
admin.site.site_title = "E.S. Portal"
admin.site.index_title = "Welcome to Easy Store Administration Portal"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('store/', include('store.urls')),
    path('', RedirectView.as_view(url='/store', permanent=True)),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [path('accounts/', include('django.contrib.auth.urls')),]