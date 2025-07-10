# productos/utils.py
import requests
from django.conf import settings

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
        "top": "remeras-top",
        "tops": "remeras-top",
        "vestido": "vestidos",
        "vestidos": "vestidos",
        "pollera": "polleras",
        "polleras": "polleras",
        "corset": "corset",
        "corsets": "corset",
    }
    palabras = texto.split()
    for palabra in palabras:
        if palabra in equivalencias:
            return equivalencias[palabra]
    return None

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