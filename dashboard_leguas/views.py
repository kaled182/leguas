from django.shortcuts import render

# Create your views here.
def DashboardV2(request):

    return render(request, 'dashboard_leguas/index.html')