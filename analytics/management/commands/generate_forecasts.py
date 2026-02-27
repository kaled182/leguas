"""
Management command to generate volume forecasts.
Can be scheduled via cron to run daily.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from analytics.services.forecaster import VolumeForecaster
from analytics.models import VolumeForecast
from core.models import Partner


class Command(BaseCommand):
    help = 'Generate volume forecasts for all partners'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to forecast (default: 7)'
        )
        parser.add_argument(
            '--method',
            type=str,
            choices=['MA7', 'MA30', 'EMA', 'TREND', 'SEASONAL', 'ALL'],
            default='ALL',
            help='Forecasting method to use (default: ALL)'
        )
        parser.add_argument(
            '--partner',
            type=int,
            help='Generate forecasts for specific partner ID only'
        )
        parser.add_argument(
            '--best-only',
            action='store_true',
            help='Only keep forecast with highest confidence for each date'
        )

    def handle(self, *args, **options):
        forecaster = VolumeForecaster()
        
        days = options['days']
        method = options['method']
        best_only = options['best_only']
        
        if days < 1 or days > 30:
            self.stdout.write(
                self.style.ERROR("Days must be between 1 and 30")
            )
            return
        
        self.stdout.write(
            f"Generating {days}-day forecasts using {method} method(s)..."
        )
        
        # Get partners
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
        
        # Methods to use
        if method == 'ALL':
            methods = ['MA7', 'MA30', 'EMA', 'TREND', 'SEASONAL']
        else:
            methods = [method]
        
        total_created = 0
        total_updated = 0
        total_errors = 0
        
        for partner in partners:
            self.stdout.write(f"\n📊 Partner {partner.id} ({partner.name}):")
            
            partner_created = 0
            partner_updated = 0
            
            for forecast_method in methods:
                try:
                    # Generate forecasts
                    forecasts = forecaster.forecast_next_days(
                        partner=partner,
                        days=days,
                        method=forecast_method
                    )
                    
                    if not forecasts:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⚠️  {forecast_method}: Not enough historical data"
                            )
                        )
                        continue
                    
                    # Save forecasts
                    for forecast_data in forecasts:
                        forecast_date = forecast_data['forecast_date']
                        
                        # Check if exists
                        existing = VolumeForecast.objects.filter(
                            partner=partner,
                            forecast_date=forecast_date,
                            method=forecast_method
                        ).first()
                        
                        if existing:
                            # Update
                            existing.predicted_volume = forecast_data['predicted_volume']
                            existing.confidence_level = forecast_data['confidence_level']
                            existing.lower_bound = forecast_data['lower_bound']
                            existing.upper_bound = forecast_data['upper_bound']
                            existing.created_at = timezone.now()
                            existing.save()
                            partner_updated += 1
                        else:
                            # Create
                            VolumeForecast.objects.create(
                                partner=partner,
                                forecast_date=forecast_date,
                                method=forecast_method,
                                predicted_volume=forecast_data['predicted_volume'],
                                confidence_level=forecast_data['confidence_level'],
                                lower_bound=forecast_data['lower_bound'],
                                upper_bound=forecast_data['upper_bound']
                            )
                            partner_created += 1
                    
                    # Show summary for this method
                    avg_confidence = sum(f['confidence_level'] for f in forecasts) / len(forecasts)
                    avg_volume = sum(f['predicted_volume'] for f in forecasts) / len(forecasts)
                    
                    confidence_color = (
                        self.style.SUCCESS if avg_confidence >= 0.8
                        else self.style.WARNING if avg_confidence >= 0.6
                        else self.style.ERROR
                    )
                    
                    self.stdout.write(
                        f"  ✅ {forecast_method}: {len(forecasts)} forecasts, "
                        f"avg volume {avg_volume:.0f}, "
                        f"confidence " + confidence_color(f"{avg_confidence:.1%}")
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ❌ {forecast_method}: {str(e)}"
                        )
                    )
                    total_errors += 1
            
            # Keep only best if requested
            if best_only and methods != [method]:  # Only if using multiple methods
                future_dates = [
                    timezone.now().date() + timedelta(days=i)
                    for i in range(1, days + 1)
                ]
                
                for forecast_date in future_dates:
                    # Get all forecasts for this date
                    date_forecasts = VolumeForecast.objects.filter(
                        partner=partner,
                        forecast_date=forecast_date
                    ).order_by('-confidence_level')
                    
                    if date_forecasts.count() > 1:
                        # Keep only the best (highest confidence)
                        best = date_forecasts.first()
                        others = date_forecasts.exclude(id=best.id)
                        deleted_count = others.count()
                        others.delete()
                        
                        if deleted_count > 0:
                            self.stdout.write(
                                f"  🗑️  {forecast_date}: Kept {best.method} "
                                f"(confidence {best.confidence_level:.1%}), "
                                f"deleted {deleted_count} others"
                            )
            
            total_created += partner_created
            total_updated += partner_updated
            
            self.stdout.write(
                f"  📈 Total: {partner_created} created, {partner_updated} updated"
            )
        
        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Forecast generation completed:"
            )
        )
        self.stdout.write(f"  • Partners: {len(partners)}")
        self.stdout.write(f"  • Methods: {', '.join(methods)}")
        self.stdout.write(f"  • Days ahead: {days}")
        self.stdout.write(f"  • Created: {total_created}")
        self.stdout.write(f"  • Updated: {total_updated}")
        self.stdout.write(f"  • Errors: {total_errors}")
        
        if best_only:
            self.stdout.write(f"  • Mode: Best forecasts only")
