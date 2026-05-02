from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def qr_generator_view(request):
    return render(request, "management/tools/qr_generator.html")
