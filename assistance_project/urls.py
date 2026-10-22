from django.contrib import admin
from django.urls import path

from assistance import views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("api/auth/login/", views.login_api, name="login"),
    path("api/auth/register/", views.register_api, name="register"),
    path("api/auth/logout/", views.logout_api, name="logout"),
    path("api/requests/", views.requests_api, name="requests"),
    path("api/requests/create/", views.create_request_api, name="create_request"),
    path("api/requests/update/", views.update_request_api, name="update_request"),
    path("api/requests/delete/", views.delete_request_api, name="delete_request"),
    path("api/volunteers/", views.volunteers_api, name="volunteers"),
    path("api/volunteers/create/", views.create_volunteer_api, name="create_volunteer"),
    path("api/volunteers/update/", views.update_volunteer_api, name="update_volunteer"),
    path("api/volunteers/delete/", views.delete_volunteer_api, name="delete_volunteer"),
    path("api/admin/dashboard/", views.dashboard_api, name="dashboard"),
]
