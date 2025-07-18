from django import forms
from django.forms.models import inlineformset_factory
from django.forms import formset_factory
from .models import Prenda, Imagen_prenda

class PrendaForm(forms.ModelForm):
    class Meta:
        model = Prenda
        fields = ['nombre', 'tela', 'precio', 'talle', 'color', 'mostrar_en_inicio', 'es_hotsale', 'categoria']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'}),
            'tela': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'}),
            'precio': forms.NumberInput(attrs={'class': 'w-full p-2 border rounded'}),
            'talle': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'}),
            'color': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'}),
            'mostrar_en_inicio': forms.CheckboxInput(attrs={'class': 'mr-2'}),
            'es_hotsale': forms.CheckboxInput(attrs={'class': 'mr-2'}),
            'categoria': forms.Select(attrs={'class': 'border rounded px-2 py-1'}),
            }
class ImagenPrendaForm(forms.ModelForm):
    img_url = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'w-full p-2 border rounded', 'accept': 'image/jpeg, image/png, image/jpg'}),
        required=True,
        label="Imagen JPG"
    )
    
    class Meta:
        model = Imagen_prenda
        fields = ['img_url', 'orden']
        widgets = {
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border rounded'}),
            }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['img_url'].required = False
        self.fields['orden'].required = False

# Crear el formset
ImagenPrendaFormSet = formset_factory(ImagenPrendaForm, extra=1, can_delete=True)
