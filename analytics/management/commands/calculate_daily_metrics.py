"""
Management command to calculate daily metrics.
Can be scheduled via cron to run daily at 1 AM.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from analytics.services.metrics_calculator import MetricsCalculator
from core.models import Partner


class Command(BaseCommand):
    help = 'Calculate daily metrics for all partners'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Calculate metrics for specific date (YYYY-MM-DD). Default: yesterday'
        )
        parser.add_argument(
            '--backfill',
            type=int,
            help='Backfill metrics for last N days'
        )
        parser.add_argument(
            '--partner',
            type=int,
            help='Calculate metrics for specific partner ID only'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recalculate even if metrics already exist'
        )

    def handle(self, *args, **options):
        calculator = MetricsCalculator()
        
        # Backfill mode
        if options['backfill']:
            days = options['backfill']
            end_date = timezone.now().date() - timedelta(days=1)
            start_date = end_date - timedelta(days=days-1)
            
            self.stdout.write(
                self.style.WARNING(
                    f"Backfilling metrics from {start_date} to {end_date} ({days} days)..."
                )
            )
            
            results = calculator.backfill_metrics(start_date, end_date)
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Backfill completed:"))
            self.stdout.write(f"  • Created: {results['created']} metrics")
            self.stdout.write(f"  • Updated: {results['updated']} metrics")
            self.stdout.write(f"  • Skipped: {results['skipped']} metrics")
            self.stdout.write(f"  • Errors: {results['errors']} metrics")
            
            if results['details']:
                self.stdout.write("\n📊 Details:")
                for detail in results['details'][:10]:  # Show first 10
                    status_emoji = {
                        'created': '✨',
                        'updated': '🔄',
                        'skipped': '⏭️',
                        'error': '❌'
                    }.get(detail['status'], '•')
                    self.stdout.write(
                        f"  {status_emoji} {detail['date']} - Partner {detail['partner_id']}: "
                        f"{detail['status']}"
                    )
                
                if len(results['details']) > 10:
                    self.stdout.write(f"  ... and {len(results['details']) - 10} more")
            
            return
        
        # Single date mode
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid date format. Use YYYY-MM-DD")
                )
                return
        else:
            # Default: yesterday
            target_date = timezone.now().date() - timedelta(days=1)
        
        self.stdout.write(f"Calculating metrics for {target_date}...")
        
        # Single partner or all partners
        if options['partner']:
            try:
                partner = Partner.objects.get(id=options['partner'])
                partners = [partner]
            except Partner.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Partner {options['partner']} not found")
                )
                return
        else:
            partners = Partner.objects.filter(is_active=True)
        
        total_created = 0
        total_updated = 0
        total_skipped = 0
        
        for partner in partners:
            from analytics.models import DailyMetrics
            
            # Check if already exists
            existing = DailyMetrics.objects.filter(
                partner=partner,
                date=target_date
            ).first()
            
            if existing and not options['force']:
                self.stdout.write(
                    f"  ⏭️  Partner {partner.id} ({partner.name}): Already exists (use --force to recalculate)"
                )
                total_skipped += 1
                continue
            
            # Calculate metrics
            metrics = calculator.calculate_metrics_for_date(partner, target_date)
            
            if metrics:
                if existing:
                    # Update existing
                    for key, value in metrics.items():
                        setattr(existing, key, value)
                    existing.save()
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f"  🔄 Partner {partner.id} ({partner.name}): "
                            f"Updated - {metrics['total_orders']} orders, "
                            f"{metrics['success_rate']:.1f}% success, "
                            f"€{metrics['revenue']:.2f} revenue"
                        )
                    )
                    total_updated += 1
                else:
                    # Create new
                    DailyMetrics.objects.create(
                        partner=partner,
                        date=target_date,
                        **metrics
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ Partner {partner.id} ({partner.name}): "
                            f"Created - {metrics['total_orders']} orders, "
                            f"{metrics['success_rate']:.1f}% success, "
                            f"€{metrics['revenue']:.2f} revenue"
                        )
                    )
                    total_created += 1
            else:
                self.stdout.write(
                    f"  ℹ️  Partner {partner.id} ({partner.name}): No data for this date"
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Calculation completed for {target_date}:"
            )
        )
        self.stdout.write(f"  • Created: {total_created}")
        self.stdout.write(f"  • Updated: {total_updated}")
        self.stdout.write(f"  • Skipped: {total_skipped}")
