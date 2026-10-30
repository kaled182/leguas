from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Create your views here.
@login_required
def DashboardV2(request):

    return render(request, 'dashboard_leguas/index.html')