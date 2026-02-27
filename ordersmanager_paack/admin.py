from django.contrib import admin
from import_export import resources
from import_export.admin import ExportMixin
from .models import Order, Driver, Dispatch, DeliveryAttempt, OrderStatusHistory

# Resources para exportação
class OrderResource(resources.ModelResource):
    class Meta:
        model = Order
        fields = ('order_id', 'retailer', 'status', 'simplified_order_status', 'intended_delivery_date', 
                  'actual_delivery_date', 'packages_count', 'client_address', 'client_phone', 'client_email')
        export_order = ('order_id', 'retailer', 'status')

class DriverResource(resources.ModelResource):
    class Meta:
        model = Driver
        fields = ('driver_id', 'name', 'vehicle', 'vehicle_norm', 'is_active')

class DispatchResource(resources.ModelResource):
    class Meta:
        model = Dispatch
        fields = ('order__order_id', 'driver__name', 'fleet', 'dc', 'driver_route_stop', 'dispatch_time')

class DeliveryAttemptResource(resources.ModelResource):
    class Meta:
        model = DeliveryAttempt
        fields = ('order__order_id', 'attempt_number', 'success', 'failure_reason', 'time')

class OrderStatusHistoryResource(resources.ModelResource):
    class Meta:
        model = OrderStatusHistory
        fields = ('order__order_id', 'status', 'previous_status', 'timestamp', 'changed_by')

# Register your models here.
@admin.register(Order)
class OrderAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = OrderResource
    list_display = ('order_id', 'retailer', 'status', 'intended_delivery_date', 'actual_delivery_date', 'simplified_order_status')
    list_filter = ('status', 'simplified_order_status', 'retailer', 'intended_delivery_date')
    search_fields = ('order_id', 'retailer_order_number', 'client_address', 'client_phone', 'client_email')
    date_hierarchy = 'intended_delivery_date'
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Driver)
class DriverAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = DriverResource
    list_display = ('driver_id', 'name', 'vehicle', 'is_active')
    list_filter = ('is_active', 'vehicle_norm')
    search_fields = ('driver_id', 'name')

@admin.register(Dispatch)
class DispatchAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = DispatchResource
    list_display = ('order', 'driver', 'fleet', 'dc', 'driver_route_stop', 'dispatch_time')
    list_filter = ('fleet', 'dc', 'recovered')
    search_fields = ('order__order_id', 'driver__name', 'driver__driver_id')
    raw_id_fields = ('order', 'driver')
    date_hierarchy = 'dispatch_time'

@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = DeliveryAttemptResource
    list_display = ('order', 'attempt_number', 'success', 'time')
    list_filter = ('success',)
    search_fields = ('order__order_id', 'failure_reason')
    raw_id_fields = ('order',)
    date_hierarchy = 'time'

@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = OrderStatusHistoryResource
    list_display = ('order', 'status', 'previous_status', 'timestamp', 'changed_by')
    list_filter = ('status', 'previous_status')
    search_fields = ('order__order_id', 'notes')
    raw_id_fields = ('order',)
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)
