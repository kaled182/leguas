"""
Comando de management para geocodificar pedidos em lote.

Uso:
    python manage.py geocode_orders [--partner=Delnext] [--limit=100] [--force]
    
Argumentos:
    --partner: Filtrar pedidos por parceiro (ex: Delnext)
    --limit: Número máximo de pedidos a processar (padrão: 100)
    --force: Re-geocodificar mesmo se já existe cache
"""

import time
from django.core.management.base import BaseCommand
from django.db import models
from orders_manager.models import Order, GeocodedAddress
from orders_manager.geocoding import GeocodingService, AddressNormalizer


class Command(BaseCommand):
    help = 'Geocodifica endereços de pedidos em lote usando Nominatim API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            type=str,
            help='Filtrar pedidos pelo nome do parceiro (ex: Delnext)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Número máximo de pedidos a processar (padrão: 100)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-geocodificar mesmo se já existe cache',
        )

    def handle(self, *args, **options):
        partner_name = options.get('partner')
        limit = options.get('limit', 100)
        force = options.get('force', False)

        # Filtrar pedidos
        orders_qs = Order.objects.all().select_related('partner')
        
        if partner_name:
            orders_qs = orders_qs.filter(partner__name__icontains=partner_name)
            self.stdout.write(f'Filtrando pedidos do parceiro: {partner_name}')
        
        orders_qs = orders_qs.order_by('-created_at')[:limit]
        total = orders_qs.count()

        self.stdout.write(f'Processando {total} pedidos...\n')

        # Estatísticas
        processed = 0
        cached = 0
        geocoded = 0
        failed = 0
        skipped = 0

        for i, order in enumerate(orders_qs, 1):
            try:
                # Verificar se tem endereço
                if not order.recipient_address or not order.postal_code:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'[{i}/{total}] Pulando pedido {order.external_reference} - endereço ou código postal faltando'
                        )
                    )
                    continue

                # Extrair localidade
                locality = order.recipient_address.split()[-1] if order.recipient_address else "Portugal"
                if len(locality) < 3:
                    locality = "Portugal"

                # Normalizar endereço
                normalized = AddressNormalizer.normalize(
                    order.recipient_address,
                    order.postal_code,
                    locality
                )

                # Verificar cache
                if not force:
                    cached_address = GeocodedAddress.objects.filter(
                        normalized_address=normalized
                    ).first()
                    
                    if cached_address:
                        cached += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[{i}/{total}] ✓ Cache: {order.external_reference} '
                                f'({cached_address.geocode_quality})'
                            )
                        )
                        processed += 1
                        continue

                # Geocodificar
                self.stdout.write(
                    f'[{i}/{total}] Geocodificando: {order.external_reference}...'
                )
                
                coords = GeocodingService.geocode(
                    order.recipient_address,
                    order.postal_code,
                    locality
                )

                if coords:
                    # Salvar no cache
                    GeocodedAddress.objects.update_or_create(
                        normalized_address=normalized,
                        defaults={
                            'address': order.recipient_address,
                            'postal_code': order.postal_code,
                            'locality': locality,
                            'latitude': coords[0],
                            'longitude': coords[1],
                            'geocode_quality': 'EXACT',
                            'geocode_source': 'Nominatim'
                        }
                    )
                    
                    geocoded += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{i}/{total}] ✓ Geocodificado: {order.external_reference} '
                            f'({coords[0]:.6f}, {coords[1]:.6f})'
                        )
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'[{i}/{total}] ✗ Falha: {order.external_reference}'
                        )
                    )

                processed += 1

                # Rate limiting (Nominatim permite 1 request/segundo)
                if geocoded % 10 == 0:
                    self.stdout.write(self.style.WARNING('⏸  Pausa de 2s para respeitar rate limit...'))
                    time.sleep(2)
                else:
                    time.sleep(1.1)  # 1.1s para margem de segurança

            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'[{i}/{total}] ✗ Erro ao processar {order.external_reference}: {e}'
                    )
                )

        # Relatório final
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('RELATÓRIO FINAL'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Total processado: {processed}')
        self.stdout.write(self.style.SUCCESS(f'✓ Em cache:       {cached}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Geocodificados: {geocoded}'))
        self.stdout.write(self.style.ERROR(f'✗ Falhados:       {failed}'))
        self.stdout.write(self.style.WARNING(f'⊘ Pulados:        {skipped}'))
        
        success_rate = ((cached + geocoded) / processed * 100) if processed > 0 else 0
        self.stdout.write(f'\nTaxa de sucesso: {success_rate:.1f}%')
        
        # Estatísticas de qualidade
        self.stdout.write('\n' + '-' * 60)
        self.stdout.write('QUALIDADE DA GEOCODIFICAÇÃO:')
        self.stdout.write('-' * 60)
        
        quality_stats = GeocodedAddress.objects.values('geocode_quality').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        for stat in quality_stats:
            quality = stat['geocode_quality'] or 'UNKNOWN'
            count = stat['count']
            self.stdout.write(f'{quality:15s}: {count:4d}')
