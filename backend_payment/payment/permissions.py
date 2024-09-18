from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import AccessMixin
from django.contrib import messages
from django.shortcuts import redirect
User = get_user_model()


class AuthorRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_authenticated:
            if request.user != self.get_object().owner or request.user.is_staff:
                # messages.info(request, 'Доступно только автору')
                return redirect('payment:menu')
        return super().dispatch(request, *args, **kwargs)


class SuperuserOnlyPerm(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('payment:menu')
        else:
            if not request.user.is_superuser:
                # return self.handle_no_permission()
                return redirect('payment:menu')
        return super().dispatch(request, *args, **kwargs)


class StaffOnlyPerm(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('payment:menu')
        else:
            if not request.user.is_staff:
                # return self.handle_no_permission()
                return redirect('payment:menu')

        # if request.user.is_authenticated:
        #     if request.user != self.get_object().owner or request.user.is_staff:
        #         # messages.info(request, 'Доступно только автору')
        #         return redirect('payment:menu')
        return super().dispatch(request, *args, **kwargs)


class MerchantOnlyPerm(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.role == 'merchant':
            return redirect('payment:menu')
        return super().dispatch(request, *args, **kwargs)


class MerchantOrViewPerm(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        role = request.user.role
        print(role)
        if role in (User.MERCHVIEWER, User.MERCHANT):
            return super().dispatch(request, *args, **kwargs)
        return redirect('payment:menu')


class SupportOrSuperuserPerm(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role == 'support' or request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        else:
            return redirect('payment:menu')

