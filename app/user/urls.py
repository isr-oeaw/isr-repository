from django.urls import path, include

from user.views import (
    AccountDeleteView, SettingsView, SignupPageView,
    UsersUpdateView, UsersListView, UserCreateView, RoleListView, RoleCreateView,
    RoleUpdateView, RoleDeleteView, user_management_view, data_export_view,
    PendingUsersView, approve_user, reject_user, UserProfileView, resend_email_verification,
    UserSetPasswordView, disable_user_notifications,
)


urlpatterns = [
    # User Management
    path('delete/', AccountDeleteView.as_view(), name='user-delete'),
    path('settings/', SettingsView, name='user-settings'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/<int:user_id>/', UserProfileView.as_view(), name='user-profile-detail'),
    path('data-export/', data_export_view, name='data-export'),
    path("signup/", SignupPageView.as_view(), name="user-signup"),
    path('list/', UsersListView.as_view(), name='user-list'),
    path('create/', UserCreateView.as_view(), name='user-create'),
    path('edit/<int:user_id>/', UsersUpdateView.as_view(), name='user-edit'),
    path('edit/<int:user_id>/password/', UserSetPasswordView.as_view(), name='user-set-password'),
    path('edit/<int:user_id>/disable-notifications/', disable_user_notifications, name='user-disable-notifications'),
    
    # User Approval
    path('pending/', PendingUsersView.as_view(), name='pending-users'),
    path('approve/<int:user_id>/', approve_user, name='approve-user'),
    path('reject/<int:user_id>/', reject_user, name='reject-user'),
    
    # Role Management
    path('roles/', RoleListView.as_view(), name='role-list'),
    path('roles/create/', RoleCreateView.as_view(), name='role-create'),
    path('roles/<int:pk>/edit/', RoleUpdateView.as_view(), name='role-edit'),
    path('roles/<int:pk>/delete/', RoleDeleteView.as_view(), name='role-delete'),
    
    # User Management Dashboard
    path('management/', user_management_view, name='user-management'),
    
    # Email Verification
    path('resend-verification/', resend_email_verification, name='resend-email-verification'),
    
    # Allauth URLs
    path("", include("allauth.account.urls")),
]