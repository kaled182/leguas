"""
Management command to check performance thresholds and create alerts.
Can be scheduled via cron to run multiple times per day.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from analytics.models import DailyMetrics, PerformanceAlert
from core.models import Partner
from fleet_management.models import DriverProfile, Vehicle


class Command(BaseCommand):
    help = 'Check performance thresholds and create alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            type=int,
            help='Check alerts for specific partner ID only'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Check metrics from last N days (default: 1)'
        )
        parser.add_argument(
            '--skip-notifications',
            action='store_true',
            help='Do not send notifications, only create alerts'
        )

    def handle(self, *args, **options):
        days_to_check = options['days']
        skip_notifications = options['skip_notifications']
        
        self.stdout.write(
            f"Checking performance alerts for last {days_to_check} day(s)..."
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
        
        alerts_created = []
        
        for partner in partners:
            self.stdout.write(f"\n🔍 Checking Partner {partner.id} ({partner.name}):")
            
            # Get recent metrics
            since_date = timezone.now().date() - timedelta(days=days_to_check)
            recent_metrics = DailyMetrics.objects.filter(
                partner=partner,
                date__gte=since_date
            ).order_by('-date')
            
            if not recent_metrics.exists():
                self.stdout.write("  ℹ️  No recent metrics available")
                continue
            
            latest = recent_metrics.first()
            
            # Check thresholds
            partner_alerts = []
            
            # 1. Low success rate
            if latest.success_rate < 80:  # Below 80%
                severity = 'CRITICAL' if latest.success_rate < 70 else 'WARNING'
                alert = self._create_alert(
                    partner=partner,
                    alert_type='LOW_SUCCESS',
                    severity=severity,
                    threshold_value=80.0,
                    actual_value=latest.success_rate,
                    metric_date=latest.date,
                    message=f"Success rate dropped to {latest.success_rate:.1f}% "
                            f"on {latest.date} (threshold: 80%)"
                )
                if alert:
                    partner_alerts.append(alert)
            
            # 2. High failures
            if latest.total_orders > 0:
                failure_rate = (latest.failed_orders / latest.total_orders) * 100
                if failure_rate > 15:  # Above 15%
                    severity = 'CRITICAL' if failure_rate > 25 else 'WARNING'
                    alert = self._create_alert(
                        partner=partner,
                        alert_type='HIGH_FAILURES',
                        severity=severity,
                        threshold_value=15.0,
                        actual_value=failure_rate,
                        metric_date=latest.date,
                        message=f"Failure rate reached {failure_rate:.1f}% "
                                f"on {latest.date} ({latest.failed_orders} failures)"
                    )
                    if alert:
                        partner_alerts.append(alert)
            
            # 3. Delayed deliveries (if avg time > threshold)
            if latest.avg_delivery_time_hours and latest.avg_delivery_time_hours > 48:
                severity = 'WARNING' if latest.avg_delivery_time_hours < 72 else 'CRITICAL'
                alert = self._create_alert(
                    partner=partner,
                    alert_type='DELAYED_DELIVERIES',
                    severity=severity,
                    threshold_value=48.0,
                    actual_value=latest.avg_delivery_time_hours,
                    metric_date=latest.date,
                    message=f"Average delivery time reached {latest.avg_delivery_time_hours:.1f}h "
                            f"on {latest.date} (threshold: 48h)"
                )
                if alert:
                    partner_alerts.append(alert)
            
            # 4. Low driver count
            active_drivers = DriverProfile.objects.filter(
                partner=partner,
                is_active=True,
                status='AVAILABLE'
            ).count()
            
            if active_drivers < 5:  # Less than 5 available drivers
                severity = 'CRITICAL' if active_drivers < 2 else 'WARNING'
                alert = self._create_alert(
                    partner=partner,
                    alert_type='LOW_DRIVER_COUNT',
                    severity=severity,
                    threshold_value=5.0,
                    actual_value=float(active_drivers),
                    metric_date=timezone.now().date(),
                    message=f"Only {active_drivers} drivers available (minimum recommended: 5)"
                )
                if alert:
                    partner_alerts.append(alert)
            
            # 5. Volume spike (compared to 7-day average)
            if recent_metrics.count() >= 7:
                avg_volume = sum(m.total_orders for m in recent_metrics[1:8]) / 7
                if latest.total_orders > avg_volume * 1.5:  # 50% increase
                    alert = self._create_alert(
                        partner=partner,
                        alert_type='VOLUME_SPIKE',
                        severity='INFO',
                        threshold_value=avg_volume * 1.5,
                        actual_value=float(latest.total_orders),
                        metric_date=latest.date,
                        message=f"Volume spike detected: {latest.total_orders} orders "
                                f"vs {avg_volume:.0f} 7-day average (+{((latest.total_orders/avg_volume - 1) * 100):.0f}%)"
                    )
                    if alert:
                        partner_alerts.append(alert)
            
            # 6. Revenue drop (compared to 7-day average)
            if recent_metrics.count() >= 7:
                avg_revenue = sum(m.revenue for m in recent_metrics[1:8]) / 7
                if latest.revenue < avg_revenue * 0.7:  # 30% drop
                    severity = 'CRITICAL' if latest.revenue < avg_revenue * 0.5 else 'WARNING'
                    alert = self._create_alert(
                        partner=partner,
                        alert_type='REVENUE_DROP',
                        severity=severity,
                        threshold_value=avg_revenue * 0.7,
                        actual_value=float(latest.revenue),
                        metric_date=latest.date,
                        message=f"Revenue dropped to €{latest.revenue:.2f} "
                                f"vs €{avg_revenue:.2f} 7-day average "
                                f"(-{((1 - latest.revenue/avg_revenue) * 100):.0f}%)"
                    )
                    if alert:
                        partner_alerts.append(alert)
            
            # Show results
            if partner_alerts:
                for alert in partner_alerts:
                    severity_style = {
                        'CRITICAL': self.style.ERROR,
                        'WARNING': self.style.WARNING,
                        'INFO': lambda x: x
                    }.get(alert.severity, lambda x: x)
                    
                    self.stdout.write(
                        severity_style(
                            f"  🔔 {alert.get_severity_display()} - "
                            f"{alert.get_alert_type_display()}: {alert.message}"
                        )
                    )
                
                alerts_created.extend(partner_alerts)
            else:
                self.stdout.write(
                    self.style.SUCCESS("  ✅ All metrics within normal thresholds")
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Alert check completed:"
            )
        )
        self.stdout.write(f"  • Partners checked: {len(partners)}")
        self.stdout.write(f"  • Alerts created: {len(alerts_created)}")
        
        if alerts_created:
            by_severity = {}
            for alert in alerts_created:
                by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
            
            for severity, count in by_severity.items():
                self.stdout.write(f"    - {severity}: {count}")
        
        if skip_notifications:
            self.stdout.write("  ℹ️  Notifications skipped")
        else:
            self.stdout.write("  📧 Notifications would be sent here")
            # TODO: Integrate with notification system

    def _create_alert(self, partner, alert_type, severity, threshold_value, 
                     actual_value, metric_date, message):
        """Create alert if it doesn't already exist (avoid duplicates)"""
        
        # Check if similar alert exists in last 24 hours
        recent_cutoff = timezone.now() - timedelta(hours=24)
        existing = PerformanceAlert.objects.filter(
            partner=partner,
            alert_type=alert_type,
            metric_date=metric_date,
            created_at__gte=recent_cutoff
        ).first()
        
        if existing:
            # Already alerted for this recently
            return None
        
        # Create new alert
        alert = PerformanceAlert.objects.create(
            partner=partner,
            alert_type=alert_type,
            severity=severity,
            threshold_value=threshold_value,
            actual_value=actual_value,
            metric_date=metric_date,
            message=message
        )
        
        return alert
