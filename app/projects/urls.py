from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Project views
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_edit'),
    path('<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    path('<int:pk>/transfer-ownership/', views.ProjectTransferOwnershipView.as_view(), name='project_transfer_ownership'),
    path('<int:pk>/invite-partner/', views.invite_project_partner, name='project_invite_partner'),
]
