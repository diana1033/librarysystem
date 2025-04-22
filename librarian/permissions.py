from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsLibrarian(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'librarian'

class IsReader(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'reader'

class IsOwnerOrLibrarian(BasePermission):

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == 'librarian' or
            obj.reader == request.user  # для моделей, где есть поле reader
        )
