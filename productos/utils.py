# productos/utils.py
import requests
from django.conf import settings
import os
import stanza

# Descargar el modelo español (solo una vez, por ejemplo en setup o local)
# stanza.download('es')

# Cargar pipeline con lematización

MODEL_DIR = os.path.expanduser('~/stanza_resources/es')

if not os.path.exists(MODEL_DIR):
    stanza.download('es')
    
nlp = stanza.Pipeline(lang='es', processors='tokenize,mwt,pos,lemma')

def lematizar(texto):
    doc = nlp(texto)
    lemas = []
    for sentence in doc.sentences:
        for word in sentence.words:
            lemas.append(word.lemma)
    return ' '.join(lemas)


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