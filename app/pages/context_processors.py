def group_memberships(request):
    """Context processor to provide user data to all templates"""
    context = {
        'user_group_memberships': [],
        'user_locals': [],
        'user_councils': [],
        'user_group_admin_groups': [],
        'next_session': None
    }
    
    if request.user.is_authenticated:
        # For ISR Repository, we don't have group memberships yet
        # This context processor is kept for future extensibility
        # and to avoid template errors
        pass
    
    return context
