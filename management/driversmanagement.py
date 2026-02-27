import io
import xlsxwriter
from reportlab.pdfgen import canvas

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ordersmanager_paack.models import Driver
from customauth.models import DriverAccess

@csrf_protect
def drivers_management_view(request):
    """
    View para gerenciar acessos de motoristas:
    - Criação de acesso com senha segura
    - Remoção de acesso
    - Exportação XLSX/PDF
    - Listagem de acessos
    """
    if request.method == "POST" and "create_access" in request.POST:
        # Validação básica
        required_fields = ['first_name', 'last_name', 'email', 'password']
        for field in required_fields:
            if not request.POST.get(field):
                messages.error(request, f"O campo {field} é obrigatório.")
                return redirect('drivers_management')

        # Verifica se o email já existe
        if DriverAccess.objects.filter(email=request.POST['email']).exists():
            messages.error(request, "Já existe um acesso com este e-mail.")
            return redirect('drivers_management')

        driver_access = DriverAccess(
            first_name=request.POST['first_name'],
            last_name=request.POST['last_name'],
            email=request.POST['email'],
            phone=request.POST.get('phone', ''),
            nif=request.POST.get('nif', ''),
            driver_id=request.POST.get('driver') or None,
            user=request.user
        )
        driver_access.set_password(request.POST['password'])
        driver_access.save()
        messages.success(request, "Acesso criado com sucesso!")
        return redirect('drivers_management')

    # Remover acesso
    if request.method == "POST" and "delete_access" in request.POST:
        access_id = request.POST.get("access_id")
        DriverAccess.objects.filter(id=access_id).delete()
        messages.success(request, "Acesso removido com sucesso!")
        return redirect('drivers_management')

    # Exportar acessos XLSX
    if request.GET.get("export") == "xlsx":
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Acessos')
        headers = ['Nome', 'Sobrenome', 'Email', 'Telefone', 'NIF', 'Motorista']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header)
        for row_num, access in enumerate(DriverAccess.objects.select_related('driver').all(), start=1):
            worksheet.write(row_num, 0, access.first_name)
            worksheet.write(row_num, 1, access.last_name)
            worksheet.write(row_num, 2, access.email)
            worksheet.write(row_num, 3, access.phone)
            worksheet.write(row_num, 4, access.nif)
            worksheet.write(row_num, 5, access.driver.name if access.driver else '')
        workbook.close()
        output.seek(0)
        response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="acessos_motoristas.xlsx"'
        return response

    # Exportar acessos PDF (simples)
    if request.GET.get("export") == "pdf":
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="acessos_motoristas.pdf"'
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer)
        y = 800
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "Nome")
        p.drawString(140, y, "Sobrenome")
        p.drawString(260, y, "Email")
        p.drawString(400, y, "Telefone")
        p.drawString(500, y, "NIF")
        p.drawString(600, y, "Motorista")
        p.setFont("Helvetica", 10)
        y -= 20
        for access in DriverAccess.objects.select_related('driver').all():
            p.drawString(40, y, access.first_name)
            p.drawString(140, y, access.last_name)
            p.drawString(260, y, access.email)
            p.drawString(400, y, access.phone or '')
            p.drawString(500, y, access.nif or '')
            p.drawString(600, y, access.driver.name if access.driver else '')
            y -= 18
            if y < 40:
                p.showPage()
                y = 800
        p.save()
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response

    # Listagem
    driver_accesses = DriverAccess.objects.select_related('driver').all().order_by('first_name', 'last_name')
    drivers = Driver.objects.all().order_by('name')
    return render(request, 'driversmanagement.html', {
        'driver_accesses': driver_accesses,
        'drivers': drivers,
    })

@csrf_protect
def edit_driver_access(request, access_id):
    """View para editar dados de acesso de motorista."""
    access = get_object_or_404(DriverAccess, id=access_id)
    drivers = Driver.objects.all().order_by('name')
    if request.method == "POST":
        access.first_name = request.POST['first_name']
        access.last_name = request.POST['last_name']
        access.email = request.POST['email']
        access.phone = request.POST['phone']
        access.nif = request.POST.get('nif', '')
        access.driver_id = request.POST.get('driver') or None
        if request.POST.get('password'):
            access.set_password(request.POST['password'])
        access.save()
        messages.success(request, "Acesso atualizado com sucesso!")
        return redirect('drivers_management')
    return render(request, 'edit_driver_access.html', {
        'access': access, 
        'drivers': drivers
    })

@csrf_protect
def change_driver_password(request, access_id):
    """View para alterar a senha de acesso de motorista."""
    access = get_object_or_404(DriverAccess, id=access_id)
    if request.method == "POST":
        access.set_password(request.POST['password'])
        access.save()
        messages.success(request, "Senha alterada com sucesso!")
        return redirect('drivers_management')
    return render(request, 'change_driver_password.html', {'access': access})