"""Access helpers for External Partner scoped visibility."""

from django.db.models import Q

EXTERNAL_PARTNER_ROLE = 'External Partner'


def partner_visible_datasets(user):
    """Datasets an external partner may list and open."""
    from datasets.models import Dataset

    return Dataset.objects.filter(
        Q(projects__in=user.assigned_projects())
        | Q(owner=user)
        | Q(contributors=user)
    ).distinct()


def user_can_access_dataset(user, dataset):
    """Return True if the user may view or download the dataset."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.is_external_partner:
        return True
    if user == dataset.owner:
        return True
    if dataset.contributors.filter(pk=user.pk).exists():
        return True
    return user.assigned_datasets().filter(pk=dataset.pk).exists()


def user_can_invite_project_partner(user, project):
    """Return True if the user may invite external partners to the project."""
    if user.is_superuser:
        return True
    if user == project.owner:
        return True
    if user.role and user.role.is_active and user.role.name == 'Administrator':
        return True
    return False
