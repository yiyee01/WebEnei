from django.urls import path
from . import views

urlpatterns = [
    path('',views.inicio, name='inicio'),
    path('prenda/<int:prenda_id>/', views.detalle_prenda, name='detalle_prenda'),
    path("buscar/", views.buscar_prendas, name="buscar_prendas"),
    path('añadir-al-carrito/<int:prenda_id>/', views.añadir_al_carrito, name='añadir_al_carrito'),
    path("carrito/", views.carrito, name="carrito"),
    path('inicio_sesion/', views.inicio_sesion, name='inicio_sesion'),
    path('registro/', views.registro, name='registro'),
    path('cerrar_sesion/', views.cerrar_sesion, name='cerrar_sesion'),
    path("confirmar_pedido/", views.confirmar_pedido, name="confirmar_pedido"),
    path('panel_admin/', views.panel_admin, name='panel_admin'),
    path('admin/prenda/agregar/', views.agregar_prenda, name='agregar_prenda'),
    path("admin/eliminar/", views.buscar_eliminar_prendas, name="buscar_eliminar_prendas"),
    path('admin/eliminar/confirmar/', views.confirmar_eliminacion_prendas, name='confirmar_eliminacion_prendas'),
    path('admin/modificar/', views.buscar_modificar_prendas, name='buscar_modificar_prendas'),
    path('admin/modificar/<int:prenda_id>/', views.modificar_prenda, name='modificar_prenda'),
    path('admin/carrusel/', views.admin_carrusel_prendas, name='admin_carrusel_prendas'),
    path('admin/hotsale/', views.admin_hotsale_prendas, name='admin_hotsale_prendas'),
    path('categoria/<str:categoria_slug>/', views.productos_por_categoria, name='productos_por_categoria'),
]