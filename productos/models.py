from django.db import models

# Create your models here.
class Prenda(models.Model):
    CATEGORIAS = [
        ('campera-camisaco', 'Campera / Camisaco'),
        ('camisas', 'Camisas'),
        ('pantalon-jeans', 'Pantalón / Jeans'),
        ('remeras-top', 'Remeras / Top'),
        ('vestidos', 'Vestidos'),
        ('polleras', 'Polleras'),
        ('corset', 'Corset'),
    ]
    id_prenda = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    tela = models.CharField(max_length=100)
    talle = models.TextField()
    color = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    mostrar_en_carrusel = models.BooleanField(default=False)
    es_hotsale = models.BooleanField(default=False)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS)

    class Meta:
        db_table = 'prenda'
        
class Imagen_prenda(models.Model):
    id_img = models.AutoField(primary_key=True)
    prenda = models.ForeignKey(Prenda, on_delete=models.CASCADE, db_column='prenda_id', related_name='imagenes')
    img_url = models.TextField()
    orden = models.IntegerField(default=1)

    class Meta:
        db_table = 'imagenes_prenda'
        ordering = ['orden']