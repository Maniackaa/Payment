from rest_framework import permissions


class PaymentOwnerOrStaff(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        if not user.is_authenticated:
            return False
        if user.is_authenticated and not user.role == 'merchant':
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if obj.merchant.owner == request.user or request.user.is_staff:
            return True


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        print('request', request)
        print('request', request.method)
        if request.method in ['GET']:
            print('if request.method in [GET]:')
            return True
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in ['GET']:
            print('if request.method in [GET]:')
            return True
        return request.user.is_staff


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.method in permissions.SAFE_METHODS
            or request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user or request.user.role == "admin"