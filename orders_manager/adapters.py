"""
Adapters de parceiros para o orders_manager (hoje: Delnext, por web scraping).
"""

import logging
import os
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


# ============================================================================
# DELNEXT ADAPTER
# ============================================================================


class DelnextAdapter:
    """
    Adapter para importar pedidos do Delnext via web scraping.
    
    Utiliza Playwright para fazer scraping autenticado na plataforma Delnext
    e importa os dados de previsão de entregas (Outbound).
    
    Uso:
        adapter = DelnextAdapter()
        orders_data = adapter.fetch_outbound_data(
            date="2026-02-27",
            zone="VianaCastelo"
        )
        adapter.import_to_orders(orders_data)
    """

    # Mapeamento de status Delnext → Order
    STATUS_MAP = {
        "Enviada": "IN_TRANSIT",
        "Entregue": "DELIVERED",
        "Pendente": "PENDING",
        "A processar": "PENDING",
        "Devolvida": "RETURNED",
        "Cancelada": "CANCELLED",
    }

    def __init__(self, username=None, password=None):
        """
        Inicializa adapter Delnext.
        
        Args:
            username: Usuário Delnext (default: VianaCastelo)
            password: Senha Delnext (default: HelloViana23432)
        """
        self.username = username or os.environ.get("DELNEXT_ADMIN_NAME", "VianaCastelo")
        self.password = password or os.environ.get("DELNEXT_ADMIN_PASS", "HelloViana23432")
        _origin = os.environ.get("DELNEXT_ORIGIN_URL", "https://www.delnext.com")
        self.base_url = f"{_origin.rstrip('/')}/admind"

    def fetch_outbound_data(self, date=None, zone=None):
        """
        Busca dados de Outbound (previsão de entregas) do Delnext.
        
        Args:
            date: Data no formato YYYY-MM-DD (default: última sexta-feira)
            zone: Zona para filtrar (default: VianaCastelo)
        
        Returns:
            list: Lista de dicionários com dados de entregas
        """
        from playwright.sync_api import sync_playwright
        from datetime import datetime, timedelta
        import json
        import urllib.parse
        import time
        import random

        # Default: última sexta-feira
        if not date:
            today = datetime.now()
            if today.weekday() == 5:  # Sábado
                last_friday = today - timedelta(days=1)
            elif today.weekday() == 6:  # Domingo
                last_friday = today - timedelta(days=2)
            else:
                last_friday = today
            date = last_friday.strftime("%Y-%m-%d")

        # Default: VianaCastelo
        zone = zone or "VianaCastelo"

        logger.info(f"[DELNEXT] Buscando dados - Data: {date}, Zona: {zone}")

        with sync_playwright() as p:
            # Configuração anti-detecção + Docker-friendly
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='pt-PT',
                timezone_id='Europe/Lisbon'
            )
            
            # Remover flag webdriver
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            page = context.new_page()

            try:
                # Login
                logger.info("[DELNEXT] Fazendo login...")
                page.goto(f"{self.base_url}/index.php", timeout=90000)
                time.sleep(8)  # Cloudflare

                # Preencher credenciais
                page.fill("input[type='text']", self.username)
                time.sleep(random.uniform(0.5, 1.5))
                page.fill("input[type='password']", self.password)
                time.sleep(random.uniform(0.5, 1.5))
                
                # Submit
                page.click("input[type='submit']")
                time.sleep(5)

                # Construir URL com filtros
                date_range = {"start": date, "end": date}
                date_range_encoded = urllib.parse.quote(json.dumps(date_range))
                url = f"{self.base_url}/outbound_consult.php?date_range={date_range_encoded}&zone={zone}"

                logger.info(f"[DELNEXT] Acessando Outbound: {url}")
                page.goto(url, timeout=30000)
                time.sleep(3)

                # Extrair dados da tabela
                # Usar evaluate para processar a tabela em JavaScript (muito mais eficiente)
                data = page.evaluate("""
                    () => {
                        const rows = Array.from(document.querySelectorAll('table tr'));
                        const data = [];
                        const uiTexts = ['customer:', 'order id:', 'status', 'search:', 'copy', 'csv', 'excel', 'pdf', 'print', 'all orders'];
                        
                        for (let i = 1; i < rows.length; i++) {  // Skip first row (header)
                            const cells = Array.from(rows[i].querySelectorAll('td'));
                            if (cells.length < 8) continue;
                            
                            const cellData = cells.map(cell => cell.textContent.trim());
                            const productId = cellData[0] || '';
                            
                            // Filter UI elements
                            const rowText = cellData.join(' ').toLowerCase();
                            const isUi = uiTexts.some(uiText => rowText.includes(uiText));
                            
                            if (productId && /^\\d+$/.test(productId) && !isUi) {
                                data.push({
                                    product_id: productId,
                                    destination_zone: cellData[1] || '',
                                    customer_name: cellData[2] || '',
                                    address: cellData[3] || '',
                                    postal_code: cellData[4] || '',
                                    city: cellData[5] || '',
                                    date: cellData[6] || '',
                                    status: cellData[7] || '',
                                    admin: cellData[8] || '',
                                    inbound_date: cellData[9] || '',
                                    inbound_by: cellData[10] || ''
                                });
                            }
                        }
                        
                        return data;
                    }
                """)

                logger.info(f"[DELNEXT] Extraídos {len(data)} pedidos")
                return data

            finally:
                browser.close()

    def import_to_orders(self, delnext_data, partner_name="Delnext"):
        """
        Importa dados do Delnext para Order model.
        
        Args:
            delnext_data: Lista de dicionários com dados Delnext
            partner_name: Nome do parceiro (default: Delnext)
        
        Returns:
            dict: Estatísticas de importação
        """
        from core.models import Partner
        from orders_manager.models import Order
        from datetime import datetime
        import re

        # Obter ou criar Partner Delnext
        partner, created = Partner.objects.get_or_create(
            name=partner_name,
            defaults={
                "nif": "999999999",  # TODO: NIF real do Delnext
                "contact_email": "operacoes@delnext.com",
                "contact_phone": "",
                "is_active": True,
            }
        )

        if created:
            logger.info(f"[DELNEXT] Partner '{partner_name}' criado")

        stats = {
            "total": len(delnext_data),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        for item in delnext_data:
            try:
                # Normalizar código postal (XXXX-XXX)
                postal_code = item.get("postal_code", "")
                # Remove tudo exceto dígitos e hífen
                postal_code = re.sub(r'[^\d-]', '', postal_code)
                
                # Adicionar hífen se necessário
                if '-' not in postal_code and len(postal_code) >= 7:
                    postal_code = f"{postal_code[:4]}-{postal_code[4:7]}"
                
                # Validar formato XXXX-XXX
                if not re.match(r'^\d{4}-\d{3}$', postal_code):
                    # Se não for válido, usar default
                    postal_code = "0000-000"

                # Parse data de entrega
                scheduled_delivery = None
                date_str = item.get("date", "")
                if date_str:
                    try:
                        scheduled_delivery = datetime.strptime(
                            date_str, "%Y-%m-%d"
                        ).date()
                    except (ValueError, TypeError):
                        pass

                # Mapear status
                status_delnext = item.get("status", "Pendente")
                current_status = self.STATUS_MAP.get(status_delnext, "PENDING")

                # Montar endereço completo
                address_parts = [
                    item.get("address", ""),
                    item.get("city", ""),
                ]
                recipient_address = ", ".join(filter(None, address_parts))
                if not recipient_address:
                    recipient_address = "Endereço não informado"

                # Criar/Atualizar Order
                order, created = Order.objects.update_or_create(
                    partner=partner,
                    external_reference=item["product_id"],
                    defaults={
                        "recipient_name": item.get("customer_name", "Cliente")[:200],
                        "recipient_address": recipient_address[:500],  # Limitar tamanho
                        "postal_code": postal_code,
                        "scheduled_delivery": scheduled_delivery,
                        "current_status": current_status,
                        "notes": f"Zona: {item.get('destination_zone', '')}",
                    }
                )

                if created:
                    stats["created"] += 1
                    logger.debug(f"[DELNEXT] Criado: {item['product_id']}")
                else:
                    stats["updated"] += 1
                    logger.debug(f"[DELNEXT] Atualizado: {item['product_id']}")

            except Exception as e:
                logger.error(
                    f"[DELNEXT] Erro ao importar {item.get('product_id')}: {e}"
                )
                stats["errors"] += 1
                # Continuar com próximo item
                continue

        logger.info(
            f"[DELNEXT] Importação concluída - "
            f"Criados: {stats['created']}, "
            f"Atualizados: {stats['updated']}, "
            f"Erros: {stats['errors']}"
        )

        return stats


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_delnext_adapter(username=None, password=None):
    """Factory function para obter adapter Delnext"""
    return DelnextAdapter(username, password)
