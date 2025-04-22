from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication

schema_view = get_schema_view(
   openapi.Info(
      title="Library API",
      default_version='v1',
      description="Документация для API библиотеки",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   authentication_classes=(JWTAuthentication,),
)



from django.urls import path, re_path

urlpatterns = [
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]
