from django.shortcuts import render, redirect
from .models import Prenda, Imagen_prenda
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from .forms import PrendaForm, ImagenPrendaFormSet
from supabase import create_client, Client
import requests
import uuid
import os
from django.http import JsonResponse
from .utils import lematizar, corregir_nombre
from .decorators import admin_required
from decimal import Decimal
from urllib.parse import quote_plus

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def inicio(request):
    inicio_res = supabase.table("prenda").select("*, imagenes_prenda(*)") \
        .eq("mostrar_en_inicio", True).execute()
    
    hotsale_res = supabase.table("prenda").select("*, imagenes_prenda(*)") \
        .eq("es_hotsale", True).execute()
    
    return render(request,"productos/inicio.html",{
        "prendas": inicio_res.data,
        "hotsale": hotsale_res.data
    })

def favoritos_api(request):
    page = int(request.GET.get("page", 1))
    size = 6  # Cantidad de prendas por carga

    start = (page - 1) * size
    end = start + size - 1

    favoritos_res = supabase.table("prenda") \
        .select("*, imagenes_prenda(*)") \
        .eq("mostrar_en_inicio", True) \
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
        response_categorias = query.eq("categoria", q_lem)
        prendas = response_categorias.execute().data
        if not prendas:
            query = supabase.table("prenda").select("*, imagenes_prenda(*)")  # Reiniciar query
            response_nombre = query.ilike("nombre", f"%{q_lem}%").execute()
            prendas = response_nombre.data
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    if minimo:
        query = query.gte("precio", float(minimo))
    if maximo:
        query = query.lte("precio", float(maximo))
    
    if not q or (q and prendas):
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
    
    try:
        cantidad = int(request.POST.get('cantidad', 1))
        if cantidad < 1:
            cantidad = 1
    except Exception:
        cantidad = 1
        
    prenda_id_str = str(prenda_id)
    
    if prenda_id_str in carrito:
        carrito[prenda_id_str] += cantidad
    else:
        carrito[prenda_id_str] = cantidad
    
    request.session['carrito'] = carrito
    request.session.modified = True
    print("Cantidad recibida del formulario:", request.POST.get('cantidad'))
    messages.success(request, f'Se agregaron {cantidad} unidad(es) al carrito.')
    return redirect('detalle_prenda', prenda_id=prenda_id)

def eliminar_del_carrito(request):
    if request.method == 'POST':
        prenda_id = str(request.POST.get('prenda_id'))
        carrito = request.session.get('carrito', {})
        
        if prenda_id in carrito:
            del carrito[prenda_id]
            request.session['carrito'] = carrito
            messages.success(request, "Prenda eliminada del carrito.")
    return redirect('carrito')

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
        
        unidades = []
        for i in range(cantidad):
            unidades.append({
                "numero": i + 1,
                "precio": prenda["precio"]
            })
        items.append({
            'prenda': prenda,
            'cantidad': cantidad,
            'subtotal': subtotal,
            'unidades': unidades
        })
    
    return render(request, 'productos/carrito.html', {'items': items, 'total': total})

def confirmar_pedido(request):
    user_session = request.session.get('user')
    if not user_session:
        messages.error(request, "Debes iniciar sesion para poder hacer el pedido.")
        return redirect('/registro/')
    
    if request.method == "POST":
        carrito = request.session.get('carrito',{})
        ids = list(map(int, carrito.keys()))
        try:
            response = supabase.table("prenda").select("*, imagenes_prenda(*)").in_("id_prenda", ids).execute()
            prendas = response.data
        except Exception as e:
            messages.error(request, "No se pudieron cargar los productos del carrito.")
            return redirect('carrito')
        
        items = []
        total = 0
        nombre = user_session.get("nombre", "")
        apellido = user_session.get("apellido", "")
        email = user_session.get("email", "")
        
        mensaje_whatsapp = f"Hola, soy {nombre} {apellido}. Voy a realizar el pedido de:\n\n"
        mensaje_email = "Buenas!, hiciste un pedido en Enei de:\n\n"
        
        for prenda in prendas:
            prenda_id = prenda["id_prenda"]
            cantidad = carrito.get(str(prenda_id), 0)
            subtotal = prenda["precio"] * cantidad
            total += subtotal
            
            talles = []
            colores = []
            for i in range(cantidad):
                talle = request.POST.get(f"talle_{prenda_id}_{i}", "No especificado")
                talles.append(talle)
                color = request.POST.get(f"color_{prenda_id}_{i}", "No especificado")
                colores.append(color)
        
            items.append({
                'prenda': prenda,
                'cantidad': cantidad,
                'subtotal': subtotal,
                'talle': talle
            })
            
            for i, (talle, color) in enumerate(zip(talles, colores), start = 1):
                precio_formateado = f"{prenda['precio']:,.0f}".replace(",", ".")
                mensaje_linea = f"- {prenda['nombre']} (Unidad {i}, Talle elegido: {talle}, Talles disponibles: {prenda.get('talle','N/D')}, Color elegido: {color}, Colores disponibles: {prenda.get('color', 'N/D')}), Precio: ${precio_formateado}\n"
                mensaje_whatsapp += mensaje_linea
                mensaje_email += mensaje_linea
        total_formateado = f"{total:,.0f}".replace(",", ".")
        mensaje_whatsapp += f"\nTotal del pedido: ${total_formateado}\nMuchas gracias!"
        mensaje_email += f"\nCosto total: ${total_formateado}\n\nEste es solo un mensaje de confirmación. ¡Que tengas un buen día!"
        
        #Envio de correo
        if email:
            send_mail(
                subject = 'Confirmacion de pedido - Enei',
                message = mensaje_email,
                from_email = settings.EMAIL_HOST_USER,
                recipient_list = [email],
                fail_silently = False
            )
        #Limpiar el carrito
        request.session['carrito'] = {}
        
        #Redireccionar a WhatsApp con mensaje
        numero_whatsapp = os.getenv("NUM")
        mensaje_codificado = mensaje_whatsapp
        return redirect(f"/solicitar_pedido/?num={numero_whatsapp}&msg={mensaje_codificado}")
    return redirect('carrito')

def solicitar_pedido(request):
    numero_whatsapp = request.GET.get("num")
    mensaje_codificado = request.GET.get("msg")
    
    if not numero_whatsapp or not mensaje_codificado:
        return redirect('inicio')  # Redirige si faltan datos

    return render(request, "productos/solicitud.html", {
        "numero_whatsapp": numero_whatsapp,
        "mensaje_codificado": mensaje_codificado,
    })

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

def recuperar_contrasena(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            messages.error(request, 'Por favor ingresa tu correo electrónico.')
            return redirect('recuperar_contrasena')

        try:
            supabase.auth.reset_password_for_email(email, {
                "redirect_to": "https://webenei.up.railway.app/nueva-contrasena/"
            })
            messages.success(request, 'Te hemos enviado un enlace para restablecer tu contraseña.')
        except Exception as e:
            print(e)
            messages.error(request, 'Ocurrió un error al intentar enviar el correo.')
    
    return render(request, 'productos/recuperar_contrasena.html')

def nueva_contrasena(request):
    access_token = request.GET.get('access_token') or request.POST.get('access_token')
    if not access_token:
        return HttpResponse("Hubo un error con el 'token de acceso'. Por favor, vuelve a solicitar el enlace.", status=401)
    
    if request.method == 'POST':
        nueva = request.POST.get('password')
        confirmar = request.POST.get('confirm_password')

        if not nueva or not confirmar:
            messages.error(request, 'Por favor completa ambos campos.')
            return redirect(f"{reverse('nueva_contrasena')}?access_token={access_token}")

        if nueva != confirmar:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect(f"{reverse('nueva_contrasena')}?access_token={access_token}")

        try:
            supabase.auth.set_session(access_token, "")
            supabase.auth.update_user({'password': nueva})
            messages.success(request, 'Tu contraseña fue actualizada exitosamente! Puedes iniciar sesion!.')
            return redirect('inicio_sesion')
        except Exception as e:
            print(e)
            messages.error(request, 'No se pudo cambiar la contraseña. Intenta de nuevo.')
    
    return render(request, 'productos/nueva_contrasena.html', {"access_token": access_token})

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

def confirmacion_email(request):
    return render(request, 'productos/confirmacion_email.html')

def cerrar_sesion(request):
    request.session.flush()
    return redirect('inicio')

def productos_por_categoria(request, categoria_slug): 
    try:
        response = supabase.table("prenda").select("*,imagenes_prenda(*)").eq("categoria",categoria_slug).execute()
        prendas = response.data
    except Exception as e:
        messages.error(request, 'No se pudieron cargar las prendas.')
        prendas = []
        
    return render(request, 'productos/productos_categoria.html', {
        'categoria': categoria_slug,
        'prendas': prendas
    })

@admin_required
def panel_admin(request):
    return render(request, 'productos/panel_admin.html')

@admin_required
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
                    if extension not in ['jpg', 'jpeg', 'png', 'webp'] or \
                        image_file.content_type not in ['image/jpeg', 'image/png']:
                        messages.error(request, f"Archivo no permitido: {image_file.name}")
                        continue
                    unique_name = f"{uuid.uuid4()}.{extension}"
                    safe_folder = corregir_nombre(prenda["nombre"])
                    path = f"{safe_folder}/{unique_name}"
                    
                    # Subir a Supabase
                    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{path}"
                    headers = {
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/octet-stream"
                    }

                    response = requests.put(upload_url, headers=headers, data=image_file.read())

                    if response.status_code in [200, 201]:
                        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
                        Imagen_prenda.objects.create(
                            prenda=prenda,
                            img_url=public_url,
                            orden=orden or (i + 1)
                        )
                    else:
                        messages.error(request, f"Error al subir una imagen: '{response.text}'\n Vuelve a intentar subir la imagen. ")
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
def buscar_eliminar_prendas(request):
    q = request.GET.get("q","")
    tela = request.GET.get("tela","")
    minimo = request.GET.get("precio_min","")
    maximo = request.GET.get("precio_max","")
    
    query = supabase.table("prenda").select("*, imagenes_prenda(*)")
    
    if q:
        q_lem = lematizar(q)
        response_categorias = query.eq("categoria", q_lem)
        prendas = response_categorias.execute().data
        if not prendas:
            query = supabase.table("prenda").select("*, imagenes_prenda(*)")  # Reinicio del query
            response_nombre = query.ilike("nombre", f"%{q_lem}%").execute()
            prendas = response_nombre.data
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    if minimo:
        query = query.gte("precio", float(minimo))
    if maximo:
        query = query.lte("precio", float(maximo))
    
    if not q or (q and prendas):
        response = query.execute()
        prendas = response.data
        
    return render(request, "productos/buscar_eliminar_prendas.html", {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "precio_min": minimo,
        "precio_max": maximo,
    })
    
@admin_required    
def confirmar_eliminacion_prendas(request):
    if request.method == "POST":
        ids = request.POST.getlist("prendas_seleccionadas")
        if ids:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            bucket = "imagenes-prendas"
            errores = []
            
            response = supabase.table("imagenes_prenda").select("*").in_("prenda_id", ids).execute()
            imagenes = response.data
            
            for imagen in imagenes:
                relative_path = imagen["img_url"].split(f"/storage/v1/object/public/{bucket}/")[-1]
                delete_url = f"{supabase_url}/storage/v1/object/{bucket}"
                headers = {
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json"
                }
                response = requests.delete(delete_url, headers=headers, json={"prefixes": [relative_path]})
                if response.status_code not in [200, 204]:
                    errores.append(f"No se pudo borrar la imagen '{relative_path}' de Supabase.")

            supabase.table("imagenes_prenda").delete().in_("prenda_id", ids).execute()
            supabase.table("prenda").delete().in_("id_prenda", ids).execute()

            if errores:
                messages.warning(request, f"Se eliminaron {len(ids)} prenda(s), pero hubo errores al eliminar algunas imágenes:\n" + "\n".join(errores))
            else:
                messages.success(request, f"Se eliminaron {len(ids)} prenda(s) y todas sus imágenes correctamente.")
        else:
            messages.warning(request, "No se seleccionaron prendas para eliminar.")
    return redirect('buscar_eliminar_prendas')

@admin_required
def buscar_modificar_prendas(request):
    q = request.GET.get("q","")
    tela = request.GET.get("tela","")
    
    query = supabase.table("prenda").select("*, imagenes_prenda(*)")
    
    if q:
        q_lem = lematizar(q)
        response_categorias = query.eq("categoria", q_lem)
        prendas = response_categorias.execute().data
        if not prendas:
            query = supabase.table("prenda").select("*, imagenes_prenda(*)")  # Reiniciar query
            response_nombre = query.ilike("nombre", f"%{q_lem}%").execute()
            prendas = response_nombre.data
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    
    if not q or (q and prendas):
        response = query.execute()
        prendas = response.data
        
    return render(request, "productos/buscar_modificar_prendas.html", {"prendas": prendas})

@admin_required
def modificar_prenda(request, prenda_id):
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = "imagenes-prendas"

    response = supabase.table("prenda").select("*").eq("id_prenda", prenda_id).single().execute()
    if not response.data:
        raise Http404("Prenda no encontrada")
    
    prenda = response.data
    imagenes_response = supabase.table("imagenes_prenda").select("*").eq("prenda_id", prenda_id).execute()
    imagenes = imagenes_response.data if imagenes_response.data else []
    
    if request.method == 'POST':
        form = PrendaForm(request.POST, initial=prenda)
        formset = ImagenPrendaFormSet(request.POST, request.FILES, prefix="form")

        if form.is_valid() and formset.is_valid():
            datos_actualizados = form.cleaned_data
            for k, v in datos_actualizados.items():
                if isinstance(v, Decimal):
                    datos_actualizados[k] = float(v)
            
            supabase.table("prenda").update(datos_actualizados).eq("id_prenda", prenda_id).execute()

            for subform in formset:
                # Eliminar imagen si está marcada para eliminación
                if subform.cleaned_data.get("DELETE") and subform.cleaned_data.get("id_img"):
                    img = subform.cleaned_data
                    relative_path = imagen['img_url'].split(f"/storage/v1/object/public/{bucket}/")[-1]
                    delete_url = f"{supabase_url}/storage/v1/object/{bucket}"
                    headers = {
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "application/json"
                    }
                    requests.delete(delete_url, headers=headers, json={"prefixes": [relative_path]})
                    supabase.table("imagenes_prenda").delete().eq("id_img", img["id_img"]).execute()
                    
                else:
                    image_file = subform.cleaned_data.get("img_url")
                    orden = subform.cleaned_data.get("orden")

                    if image_file and isinstance(image_file, InMemoryUploadedFile):
                        # Subir imagen nueva
                        extension = image_file.name.split('.')[-1]
                        if extension not in ['jpg', 'jpeg', 'png', 'webp'] or \
                            image_file.content_type not in ['image/jpeg', 'image/png']:
                            messages.error(request, f"Archivo no permitido: {image_file.name}")
                            continue
                        unique_name = f"{uuid.uuid4()}.{extension}"
                        safe_folder = corregir_nombre(prenda["nombre"])
                        path = f"{safe_folder}/{unique_name}"

                        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{path}"
                        headers = {
                            "Authorization": f"Bearer {supabase_key}",
                            "Content-Type": "application/octet-stream"
                        }

                        response = requests.post(upload_url, headers=headers, data=image_file.read())

                        if response.status_code in [200, 201]:
                            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
                            id_img = subform.cleaned_data.get("id_img")
                            
                            if id_img:
                                # Actualizar imagen existente
                                supabase.table("imagenes_prenda").update({
                                    "img_url": public_url,
                                    "orden": orden
                                }).eq("id_img", id_img).execute()
                            else:
                                supabase.table("imagenes_prenda").insert({
                                    "prenda_id": prenda_id,
                                    "img_url": public_url,
                                    "orden": orden
                                }).execute()
                        else:
                            messages.error(request, f"No se pudo subir una imagen: '{response.text}'\n Vuelve a intentar subir la imagen.")

            messages.success(request, "Prenda modificada correctamente.")
            return redirect('buscar_modificar_prendas')
        else:
            messages.error(request, "Revisá los datos, hubo errores al guardar.")
    else:
        form = PrendaForm(initial=prenda)
        formset = ImagenPrendaFormSet(initial=imagenes, prefix="form")

    return render(request, 'productos/modificar_prenda.html', {
        'form': form,
        'formset': formset,
        'prenda': prenda
    })

@admin_required
def admin_inicio_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    en_inicio = request.GET.get("en_inicio", "")
    
    query = supabase.table("prenda").select("*, imagenes_prenda(*)")

    if q:
        q_lem = lematizar(q)
        query = query.eq("categoria", q_lem)
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    if en_inicio == "si":
        query = query.eq("mostrar_en_inicio", True)
    elif en_inicio == "no":
        query = query.eq("mostrar_en_inicio", False)
    
    prendas = query.execute().data

    if request.method == "POST":
        mostrar_ids = request.POST.getlist("mostrar_en_inicio")
        
        mostrar_ids = [int(x) for x in mostrar_ids]
        errores = []
        for prenda in prendas:
            try:
                id_actual = prenda["id_prenda"]
                mostrar = id_actual in mostrar_ids
                response = supabase.table("prenda").update({
                    "mostrar_en_inicio": mostrar
                }).eq("id_prenda", id_actual).execute()
            except Exception as e:
                errores.append(f"Error al actualizar prenda {prenda['id_prenda']}: {e}") 
        if errores:
            messages.warning(request, "Hubo algunos errores: \n" + "\n".join(errores))
        else:
            messages.success(request, "Lista de favoritos actualizada correctamente.")
        return redirect("admin_inicio_prendas")
    
        messages.success(request, "Lista de favoritos actualizada correctamente.")
        return redirect('admin_inicio_prendas')

    context = {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "en_inicio": en_inicio,
    }
    return render(request, "productos/admin_inicio.html", context)

@admin_required
def admin_hotsale_prendas(request):
    q = request.GET.get("q", "")
    tela = request.GET.get("tela", "")
    en_hotsale = request.GET.get("en_hotsale", "")

    query = supabase.table("prenda").select("*, imagenes_prenda(*)")

    if q:
        q_lem = lematizar(q)
        query = query.eq("categoria", q_lem)
    if tela:
        query = query.ilike("tela", f"%{tela}%")
    if en_hotsale == "si":
        query = query.eq("es_hotsale", True)
    elif en_hotsale == "no":
        query = query.eq("es_hotsale", False)
    
    try: 
        prendas = query.execute().data
    except Exception as e:
        logging.exception("Error consultando prendas")
        prendas = []
        messages.error(request, "No se pudieron cargar las prendas.")

    if request.method == "POST":
        hotsale_ids = request.POST.getlist("es_hotsale")
        hotsale_ids = [int(x) for x in hotsale_ids]
        
        try: 
            errores = []
            
            for prenda in prendas:
                id_actual = prenda['id_prenda']
                mostrar = id_actual in hotsale_ids
                
                try:
                    supabase.table("prenda").update({
                        "es_hotsale": mostrar
                    }).eq("id_prenda", id_actual).execute()
                except Exception as e:
                    errores.append(f"Error al actualizar prenda {id_actual}: {e}")
            
            if errores:
                messages.warning(request, "Hubo algunos errores:\n" + "\n".join(errores))
            else: 
                messages.success(request, "Hotsale actualizado correctamente.")
            return redirect("admin_hotsale_prendas")
        except Exception as e:
            messages.error(request, "Error al actualizar el estado Hotsale.")
            logging.exception("Error al actualizar es_hotsale")

    context = {
        "prendas": prendas,
        "q": q,
        "tela": tela,
        "en_hotsale": en_hotsale,
    }
    return render(request, "productos/admin_hotsale.html", context)
