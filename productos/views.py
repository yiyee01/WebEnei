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
from supabase import create_client, Client
import requests
import uuid
import os
from django.http import JsonResponse
from .utils import lematizar
from .decorators import admin_required

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def inicio(request):
    carrusel_res = supabase.table("prenda").select("*, imagenes_prenda(*)") \
        .eq("mostrar_en_carrusel", True).execute()
    
    hotsale_res = supabase.table("prenda").select("*, imagenes_prenda(*)") \
        .eq("es_hotsale", True).execute()
    
    return render(request,"productos/inicio.html",{
        "prendas": carrusel_res.data,
        "hotsale": hotsale_res.data
    })

def favoritos_api(request):
    page = int(request.GET.get("page", 1))
    size = 6  # Cantidad de prendas por carga

    start = (page - 1) * size
    end = start + size - 1

    favoritos_res = supabase.table("prenda") \
        .select("*, imagenes_prenda(*)") \
        .eq("mostrar_en_carrusel", True) \
        .range(start, end) \
        .execute()

    return JsonResponse(favoritos_res.data, safe=False)

def detalle_prenda(request, prenda_id):
   response = supabase.table("prenda").select("*, imagenes_prenda(*)").eq("id_prenda", prenda_id).execute()
   prendas = response.data
   if prendas:
       prenda = prendas[0]
   else:
       return HttpResponseNotFound("Prenda no encontrada")
   return render(request, 'productos/detalle_prenda.html', {'prenda': prenda})

def buscar_prendas(request):
    q = request.GET.get("q","")
    tela = request.GET.get("tela","")
    minimo = request.GET.get("precio_min","")
    maximo = request.GET.get("precio_max","")
    
    query = supabase.table("prenda").select("*, imagenes_prenda(*)")
    
    if q:
        q_lem = lematizar(q)
        query = query.ilike("nombre", f"%{q_lem}%")
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    if minimo:
        query = query.gte("precio", float(minimo))
    if maximo:
        query = query.lte("precio", float(maximo))
    
    response = query.execute()
    prendas = response.data
    
    return render(request, "productos/resultados_busqueda.html", {"prendas": prendas})

def añadir_al_carrito(request, prenda_id):
    response = supabase.table("prenda").select("*, imagenes_prenda(*)").eq("id_prenda", prenda_id).limit(1).execute()
    
    if not response.data:
        messages.error(request, "La prenda no existe")
        return redirect("inicio")
    
    prenda = response.data[0]
    
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
    
    if not carrito:
        return render(request, 'productos/carrito.html', {'items': [], 'total': 0})
    
    ids = list(map(int, carrito.keys()))
    response = supabase.table("prenda").select("*, imagenes_prenda(*)").in_("id_prenda", ids).execute()
    prendas_data = response.data
    items = []
    total = 0
    for prenda in prendas_data:
        prenda_id = prenda["id_prenda"]
        cantidad = carrito.get(str(prenda_id), 0)
        subtotal = prenda["precio"] * cantidad
        total += subtotal
        
        items.append({
            'prenda': prenda,
            'cantidad': cantidad,
            'subtotal': subtotal
        })
    
    return render(request, 'productos/carrito.html', {'items': items, 'total': total})

def inicio_sesion(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            messages.error(request, 'Por favor completa ambos campos.')
            return render(request, 'productos/inicio_sesion.html')
        
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_metadata = result.user.user_metadata
        is_admin = user_metadata.get("is_admin", False)
        
        if result.user:
            request.session['user'] = {
                "id": result.user.id,
                "email": result.user.email,
                "nombre": result.user.user_metadata.get('first_name', ''),
                "apellido": result.user.user_metadata.get('last_name', ''),
                "is_admin": is_admin,
            }
            request.session['access_token'] = result.session.access_token
            request.session['refresh_token'] = result.session.refresh_token
            return redirect('inicio')
        else:
            messages.error(request,'Email o contraseña incorrectos.')
    return render(request, 'productos/inicio_sesion.html')

def registro(request):
    next_url = request.GET.get("next", "inicio")
    if request.GET.get("next"):
        messages.info(request, "Necesitás registrarte o iniciar sesión para poder realizar la compra.")
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
    
        if password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'productos/registro.html')
        
        try:
            result = supabase.auth.sign_up({
                "email": email,
                "password": password1,
                "options":{
                    "data": {
                        "first_name": first_name,
                        "last_name": last_name
                    }
                }
            })
            
            if result.user and not result.session:
                request.session['pending_email'] = email
                messages.success(request, 'Te enviamos un correo para verificar tu cuenta.')
                return redirect('verificacion_email')
            
            if result.session:
                request.session['user'] = {
                    "id": result.user.id,
                    "email": result.user.email,
                    "nombre": first_name,
                    "apellido": last_name,
                }
                request.session['access_token'] = result.session.access_token
                request.session['refresh_token'] = result.session.refresh_token

                messages.success(request, 'Usted se registró con exito!')
                return redirect(next_url)
        except Exception as e:
            messages.error(request, 'Hubo un error al registrar el usuario.')
            print(f"-----------------Error de Supabase: {e}---------------------")
    return render(request, 'productos/registro.html')

def verificacion_email(request):
    email = request.session.get('pending_email')
    if not email:
        return redirect('registro')

    if request.method == 'POST':
        try:
            supabase.auth.resend({
                "type": "signup",
                "email": email
            })
            messages.success(request, "Se reenvió el correo de verificación.")
        except Exception as e:
            messages.error(request, "No se pudo reenviar el correo.")
            print(f"------Error al reenviar verificación: {e}-----")

    return render(request, 'productos/verificacion_email.html', {"email": email})

def cerrar_sesion(request):
    request.session.flush()
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

@admin_required
@staff_member_required
def panel_admin(request):
    return render(request, 'productos/panel_admin.html')

@admin_required
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

@admin_required
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
    
@admin_required    
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

@admin_required
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

@admin_required
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

@admin_required
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

@admin_required
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
