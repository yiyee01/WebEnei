from django.shortcuts import render, get_object_or_404, redirect
from .models import Prenda, Imagen_prenda
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import logout, get_user_model, authenticate, login as auth_login
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import quote
from django.contrib.admin.views.decorators import staff_member_required
from .forms import PrendaForm, ImagenPrendaFormSet
import requests
import uuid
import os

def inicio(request):
    prendas = Prenda.objects.prefetch_related('imagenes').filter(mostrar_en_carrusel=True)[:8]
    hotsale = Prenda.objects.prefetch_related('imagenes').filter(es_hotsale=True)[:8]
    return render(request,'productos/inicio.html',{'prendas': prendas, 'hotsale': hotsale})

def detalle_prenda(request, prenda_id):
   prenda = get_object_or_404(Prenda.objects.prefetch_related('imagenes'), id_prenda = prenda_id)
   return render(request, 'productos/detalle_prenda.html', {'prenda': prenda})

def buscar_prendas(request):
    q = request.GET.get("q","")
    tela = request.GET.get("tela","")
    minimo = request.GET.get("precio_min","")
    maximo = request.GET.get("precio_max","")
    
    prendas = Prenda.objects.all()
    
    if q:
        prendas = prendas.filter(nombre__icontains=q)
    if tela:
        prendas = prendas.filter(tela__icontains=tela)
    if minimo:
        prendas = prendas.filter(precio__gte=minimo)
    if maximo:
        prendas = prendas.filter(precio__lte=maximo)
    
    return render(request, "productos/resultados_busqueda.html", {"prendas": prendas})

def añadir_al_carrito(request, prenda_id):
    prenda = get_object_or_404(Prenda, id_prenda=prenda_id)
    carrito = request.session.get('carrito', {})
    
    if str(prenda_id) in carrito:
        carrito[str(prenda_id)] += 1
    else:
        carrito[str(prenda_id)] = 1
    
    request.session['carrito'] = carrito
    messages.success(request, 'Producto agregado con éxito.')
    return redirect('detalle_prenda', prenda_id=prenda_id)

def carrito(request):
    carrito = request.session.get('carrito', {})
    prendas = Prenda.objects.filter(id_prenda__in=carrito.keys())
    items = []
    for prenda in prendas:
        cantidad = carrito.get(str(prenda.id_prenda), 0)
        items.append({
        'prenda': prenda,
        'cantidad': cantidad,
        'subtotal': prenda.precio * cantidad
        })
    total = sum(item['subtotal'] for item in items)
    return render(request, 'productos/carrito.html', {'items': items, 'total': total})

def inicio_sesion(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        if not email or not password:
            messages.error(request, 'Por favor completa ambos campos.')
            return render(request, 'productos/inicio_sesion.html')
        User = get_user_model()
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('inicio')
            else:
                messages.error(request, 'Contraseña incorrecta.')
        except User.DoesNotExist:
            messages.error(request, 'No existe un usuario con ese email.')
    return render(request, 'productos/inicio_sesion.html')

def registro(request):
    User = get_user_model()
    next_url = request.GET.get("next", "inicio")
    if request.GET.get("next"):
        messages.info(request, "Necesitás registrarte o iniciar sesión para poder realizar la compra.")
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Validaciones
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'productos/registro.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso.')
            return render(request, 'productos/registro.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe un usuario con ese correo electrónico.')
            return render(request, 'productos/registro.html')

        # Crear usuario
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=make_password(password1)
        )
        login(request, user)
        
        messages.success(request, 'Usuario registrado con éxito. Ahora puedes iniciar sesión.')
        return redirect(next_url)

    return render(request, 'productos/registro.html')

def cerrar_sesion(request):
    logout(request)
    return redirect('inicio')

def productos_por_categoria(request, categoria_slug):
    prendas = Prenda.objects.filter(categoria=categoria_slug).prefetch_related('imagenes')
    return render(request, 'productos/productos_categoria.html', {
        'categoria': categoria_slug,
        'prendas': prendas
    })

@login_required(login_url='/registro/')
@csrf_exempt
def confirmar_pedido(request):
    if request.method == "POST":
        carrito = request.session.get('carrito',{})
        prendas = Prenda.objects.filter(id_prenda__in=carrito.keys())
        items = []
        total = 0
        mensaje_whatsapp = f"Hola, soy {request.user.first_name} {request.user.last_name}. Voy a realizar el pedido de:\n\n"
        mensaje_email = "Buenas!, hiciste un pedido en Enei de:\n\n"
        for prenda in prendas:
            cantidad = carrito.get(str(prenda.id_prenda), 0)
            subtotal = prenda.precio * cantidad
            total += subtotal
            print(request.POST)
            talle = request.POST.get(f"talle_{prenda.id_prenda}", "No especificado")
        
            items.append({
                'prenda': prenda,
                'cantidad': cantidad,
                'subtotal': subtotal,
                'talle': talle
            })
            mensaje_linea = f"- {prenda.nombre} (Talle: {talle}, Talles disponibles: {prenda.talle}) x {cantidad}, Precio: ${subtotal}\n"
            mensaje_whatsapp += mensaje_linea
            mensaje_email += mensaje_linea
        mensaje_whatsapp += f"\nTotal del pedido: ${total}\nMuchas gracias!"
        mensaje_email += f"\nCosto total: ${total}\n\nEste es solo un mensaje de confirmación. ¡Que tengas un buen día!"
        
        #Envio de correo
        if request.user.email:
            send_mail(
                subject = 'Confirmacion de pedido - Enei',
                message = mensaje_email,
                from_email = settings.EMAIL_HOST_USER,
                recipient_list = [request.user.email],
                fail_silently = False
            )
        #Limpiar el carrito
        request.session['carrito'] = {}
        
        #Redireccionar a WhatsApp con mensaje
        numero_whatsapp = os.getenv("NUM")
        mensaje_codificado = quote(mensaje_whatsapp)
        return redirect(f"https://wa.me/{numero_whatsapp}?text={mensaje_codificado}")
    return redirect('carrito')

@staff_member_required
def panel_admin(request):
    return render(request, 'productos/panel_admin.html')

@staff_member_required
def agregar_prenda(request):
    if request.method == 'POST':
        
        form = PrendaForm(request.POST)
        formset = ImagenPrendaFormSet(request.POST, request.FILES, prefix="form")
        
        if form.is_valid() and formset.is_valid():
            prenda = form.save()
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Requiere permisos de escritura
            bucket = "imagenes-prendas"
            
            for i, subform in enumerate(formset):
                image_file = subform.cleaned_data.get("img_url")
                orden = subform.cleaned_data.get("orden")

                if image_file and isinstance(image_file, InMemoryUploadedFile):
                    extension = image_file.name.split('.')[-1]
                    unique_name = f"{uuid.uuid4()}.{extension}"
                    path = f"{prenda.nombre}/{unique_name}"

                    # Subir a Supabase
                    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{path}"
                    headers = {
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/octet-stream"
                    }

                    response = requests.post(upload_url, headers=headers, data=image_file.read())

                    if response.status_code in [200, 201]:
                        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
                        Imagen_prenda.objects.create(
                            prenda=prenda,
                            img_url=public_url,
                            orden=orden or (i + 1)
                        )
                    else:
                        messages.error(request, f"Error al subir una imagen: {response.text}")
            messages.success(request, "Prenda y fotos agregadas con éxito.")
            return redirect('panel_admin')
        else:
            messages.error(request, "Hubo un error con los datos del formulario.")
    else:
        form = PrendaForm()
        formset = ImagenPrendaFormSet(prefix="form")

    return render(request, 'productos/agregar_prenda.html', {
        'form': form,
        'formset': formset
    })

@staff_member_required
def buscar_eliminar_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    minimo = request.GET.get("precio_min", "")
    maximo = request.GET.get("precio_max", "")

    prendas = Prenda.objects.all()

    if q:
        prendas = prendas.filter(nombre__icontains=q)
    if tela:
        prendas = prendas.filter(tela__icontains=tela)
    if minimo:
        prendas = prendas.filter(precio__gte=minimo)
    if maximo:
        prendas = prendas.filter(precio__lte=maximo)
        
    return render(request, "productos/buscar_eliminar_prendas.html", {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "precio_min": minimo,
        "precio_max": maximo,
    })
    
@staff_member_required
def confirmar_eliminacion_prendas(request):
    if request.method == "POST":
        ids = request.POST.getlist("prendas_seleccionadas")
        if ids:
            prendas = Prenda.objects.filter(id_prenda__in=ids)
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            bucket = "imagenes-prendas"
            errores = []
            for prenda in prendas:
                for imagen in prenda.imagenes.all():
                    relative_path = imagen.img_url.split(f"/storage/v1/object/public/{bucket}/")[-1]
                    delete_url = f"{supabase_url}/storage/v1/object/{bucket}"
                    headers = {
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json"
                    }
                    response = requests.delete(delete_url, headers=headers, json={"prefixes": [relative_path]})
                    if response.status_code not in [200, 204]:
                        errores.append(f"No se pudo borrar la imagen '{relative_path}' de Supabase.")

            cantidad = prendas.count()
            prendas.delete()

            if errores:
                messages.warning(request, f"Se eliminaron {cantidad} prenda(s), pero hubo errores al eliminar algunas imágenes:\n" + "\n".join(errores))
            else:
                messages.success(request, f"Se eliminaron {cantidad} prenda(s) y todas sus imágenes correctamente.")
        else:
            messages.warning(request, "No se seleccionaron prendas para eliminar.")
    return redirect('buscar_eliminar_prendas')

@staff_member_required
def buscar_modificar_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    prendas = Prenda.objects.all()
    if q:
        prendas = prendas.filter(nombre__icontains=q)
    if tela:
        prendas = prendas.filter(tela__icontains=tela)
    return render(request, "productos/buscar_modificar_prendas.html", {"prendas": prendas})

@staff_member_required
def modificar_prenda(request, prenda_id):
    prenda = get_object_or_404(Prenda, id_prenda=prenda_id)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = "imagenes-prendas"

    if request.method == 'POST':
        form = PrendaForm(request.POST, instance=prenda)
        formset = ImagenPrendaFormSet(request.POST, request.FILES, instance=prenda, prefix="form")

        if form.is_valid() and formset.is_valid():
            form.save()

            for subform in formset:
                # Eliminar imagen si está marcada para eliminación
                if subform.cleaned_data.get("DELETE") and subform.instance.pk:
                    imagen = subform.instance
                    relative_path = imagen.img_url.split(f"/storage/v1/object/public/{bucket}/")[-1]
                    delete_url = f"{supabase_url}/storage/v1/object/{bucket}"
                    headers = {
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json"
                    }
                    requests.delete(delete_url, headers=headers, json={"prefixes": [relative_path]})
                    imagen.delete()

                else:
                    image_file = subform.cleaned_data.get("img_url")
                    orden = subform.cleaned_data.get("orden")

                    if image_file and isinstance(image_file, InMemoryUploadedFile):
                        # Subir imagen nueva
                        extension = image_file.name.split('.')[-1]
                        unique_name = f"{uuid.uuid4()}.{extension}"
                        path = f"{prenda.nombre}/{unique_name}"

                        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{path}"
                        headers = {
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/octet-stream"
                        }

                        response = requests.post(upload_url, headers=headers, data=image_file.read())

                        if response.status_code in [200, 201]:
                            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"

                            if subform.instance.pk:
                                subform.instance.img_url = public_url
                                subform.instance.orden = orden
                                subform.instance.save()
                            else:
                                Imagen_prenda.objects.create(
                                    prenda=prenda,
                                    img_url=public_url,
                                    orden=orden
                                )
                        else:
                            messages.error(request, f"No se pudo subir una imagen: {response.text}")

            messages.success(request, "Prenda modificada correctamente.")
            return redirect('buscar_modificar_prendas')
        else:
            print("Errores del form:", form.errors)
            for subform in formset:
                if subform.errors:
                    print("Errores en subform:", subform.errors)
            messages.error(request, "Revisá los datos, hubo errores al guardar.")
    else:
        form = PrendaForm(instance=prenda)
        formset = ImagenPrendaFormSet(instance=prenda, prefix="form")

    return render(request, 'productos/modificar_prenda.html', {
        'form': form,
        'formset': formset,
        'prenda': prenda
    })

@staff_member_required
def admin_carrusel_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    en_carrusel = request.GET.get("en_carrusel", "")
    
    prendas = Prenda.objects.all()

    if q:
        prendas = prendas.filter(nombre__icontains=q)
    if tela:
        prendas = prendas.filter(tela__icontains=tela)
    if en_carrusel == "si":
        prendas = prendas.filter(mostrar_en_carrusel=True)
    elif en_carrusel == "no":
        prendas = prendas.filter(mostrar_en_carrusel=False)

    if request.method == "POST":
        mostrar_ids = request.POST.getlist("mostrar_en_carrusel")
        for prenda in Prenda.objects.all():
            prenda.mostrar_en_carrusel = str(prenda.id_prenda) in mostrar_ids
            prenda.save()
        messages.success(request, "Carrusel actualizado correctamente.")
        return redirect('admin_carrusel_prendas')

    context = {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "en_carrusel": en_carrusel,
    }
    return render(request, "productos/admin_carrusel.html", context)

@staff_member_required
def admin_hotsale_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    en_hotsale = request.GET.get("en_hotsale", "")

    prendas = Prenda.objects.all()

    if q:
        prendas = prendas.filter(nombre__icontains=q)
    if tela:
        prendas = prendas.filter(tela__icontains=tela)
    if en_hotsale == "si":
        prendas = prendas.filter(es_hotsale=True)
    elif en_hotsale == "no":
        prendas = prendas.filter(es_hotsale=False)

    if request.method == "POST":
        hotsale_ids = request.POST.getlist("es_hotsale")
        for prenda in Prenda.objects.all():
            prenda.es_hotsale = str(prenda.id_prenda) in hotsale_ids
            prenda.save()
        messages.success(request, "Hotsale actualizado correctamente.")
        return redirect("admin_hotsale_prendas")

    context = {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "en_hotsale": en_hotsale,
    }
    return render(request, "productos/admin_hotsale.html", context)
