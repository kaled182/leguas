from datetime import datetime
from django.utils import timezone
import pytz
import logging

logger = logging.getLogger(__name__)

def parse_api_date(date_string):
    """
    Converte string de data da API para objeto date do Django.
    Baseado no ordersmanager funcional.
    """
    if not date_string or date_string.strip() == '':
        return None
    
    formats = ['%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt).date()
        except ValueError:
            continue
    
    logger.warning(f"⚠️ Formato de data não reconhecido: {date_string}")
    return None

def parse_api_datetime(datetime_string):
    """
    Converte string de datetime da API para objeto datetime timezone-aware do Django.
    Resolve o problema de RuntimeWarning sobre naive datetimes.
    """
    if not datetime_string or datetime_string.strip() == '':
        return None
    
    formats = [
        '%m/%d/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f'
    ]
    
    for fmt in formats:
        try:
            # Parse do datetime como naive
            naive_dt = datetime.strptime(datetime_string.strip(), fmt)
            
            # Converter para timezone-aware usando o timezone do Django
            aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            
            return aware_dt
        except ValueError:
            continue
    
    logger.warning(f"⚠️ Formato de datetime não reconhecido: {datetime_string}")
    return None