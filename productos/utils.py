# productos/utils.py

import spacy
import requests
from django.conf import settings

# Cargamos el modelo español solo una vez al importar
nlp = spacy.load("es_core_news_sm")

def lematizar(texto):
    doc = nlp(texto)
    return " ".join([token.lemma_ for token in doc])


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