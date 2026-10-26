"""Preenche a data prevista de pagamento da PF ao gravar."""
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender="settlements.DriverPreInvoice")
def set_expected_payment_date(sender, instance, **kwargs):
    if instance.data_prevista_pagamento or not instance.driver_id:
        return
    from .services_payments import expected_for_pf

    instance.data_prevista_pagamento = expected_for_pf(instance)
