from django.contrib import admin

from .models import (
    ApprovalRule, Bill, BillApproval, BillAttachment,
    CostCenter, ExpenseCategory,
)


@admin.register(ApprovalRule)
class ApprovalRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "min_amount", "is_active")
    list_filter = ("is_active",)
    filter_horizontal = ("approvers",)


@admin.register(BillApproval)
class BillApprovalAdmin(admin.ModelAdmin):
    list_display = ("bill", "approver", "decision", "decided_at")
    list_filter = ("decision",)
    readonly_fields = ("decided_at",)


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "cainiao_hub", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("code", "name")


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "nature", "is_active", "sort_order")
    list_filter = ("nature", "is_active")
    search_fields = ("code", "name")


class BillAttachmentInline(admin.TabularInline):
    model = BillAttachment
    extra = 0
    readonly_fields = ("uploaded_at", "uploaded_by")


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "description", "supplier", "category", "cost_center",
        "amount_total", "due_date", "status",
    )
    list_filter = (
        "status", "category", "cost_center", "recurrence",
    )
    search_fields = ("description", "supplier", "invoice_number")
    date_hierarchy = "due_date"
    inlines = [BillAttachmentInline]
    readonly_fields = ("created_at", "updated_at", "created_by")
