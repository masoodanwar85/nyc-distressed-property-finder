from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from leads import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.lead_list, name="lead_list"),
    path("export.csv", views.lead_export, name="lead_export"),
    path("building/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("runs/", views.run_list, name="run_list"),
]
