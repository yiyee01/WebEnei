# productos/utils.py
import requests
from django.conf import settings
import re
import unicodedata

def lematizar(texto):
    texto = texto.lower()
    equivalencias = {
        "campera": "campera-camisaco",
        "camperas": "campera-camisaco",
        "camisaco": "campera-camisaco",
        "camisas": "camisas",
        "camisa": "camisas",
        "pantalon": "pantalon-jeans",
        "pantalón": "pantalon-jeans",
        "pantalones": "pantalon-jeans",
        "jean": "pantalon-jeans",
        "jeans": "pantalon-jeans",
        "remera": "remeras-top",
        "remeras": "remeras-top",
        "remerones": "remeras-top",
        "remeron": "remeras-top",
        "top": "remeras-top",
        "tops": "remeras-top",
        "vestido": "vestidos",
        "vestidos": "vestidos",
        "pollera": "polleras",
        "polleras": "polleras",
        "buzos": "buzo",
        "buzo": "buzo",
        "corset": "corset",
        "corsets": "corset",
        "conjuntos": "conjunto",
        "conjunto": "conjunto",
        "tapados": "tapado",
        "tapado": "tapado",
    }
    palabras = texto.split()
    for palabra in palabras:
        if palabra in equivalencias:
            return equivalencias[palabra]
    return texto

def get_user_by_email(email):
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users?email={email}"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]  # debería ser uno solo
    return None


def corregir_nombre(nombre):
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')  # Pantalón → Pantalon
    nombre = nombre.lower().strip()
    nombre = re.sub(r'\s+', '-', nombre)  # espacios → guiones
    nombre = re.sub(r'[^a-zA-Z0-9_\-]', '', nombre)  # solo letras, números, guiones y guiones bajos
    return nombre