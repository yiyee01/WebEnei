def usuario_desde_sesion(request):
    return {
        'user': request.session.get('user')
    }