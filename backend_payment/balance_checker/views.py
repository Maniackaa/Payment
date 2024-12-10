import structlog
from django.conf import settings
from django.shortcuts import render
from django.views.generic import ListView

from balance_checker.models import Wallet
from payment.permissions import StaffOnlyPerm
logger = structlog.get_logger(__name__)

class WalletListView(StaffOnlyPerm, ListView):
    """Спиок выводов"""
    template_name = 'balance_checker/wallet_list.html'
    model = Wallet

    def get_context_data(self, **kwargs):
        logger.info('xxxxxxxxxxxxxxxxxxxxxx')
        context = super().get_context_data(**kwargs)
        return context
