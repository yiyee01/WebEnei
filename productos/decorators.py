from django.shortcuts import redirect
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.session.get("user")
        if not user or not user.get("is_admin"):
            return redirect("inicio")  # Redirigir a inicio o página de acceso denegado
        return view_func(request, *args, **kwargs)
    return wrapper
