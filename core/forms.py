import os

from django import forms
from django.core.exceptions import ValidationError
from django.db.models.fields.files import FieldFile

from .models import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    Category,
    Post,
    sanitize_upload_name,
)


def validate_upload(value, allowed_extensions):
    if not value:
        return

    is_existing_file = isinstance(value, FieldFile)
    extension = os.path.splitext(value.name)[1].lower().lstrip('.')
    if extension not in allowed_extensions:
        allowed = ', '.join(sorted(allowed_extensions)).upper()
        raise ValidationError(f'Formato no permitido. Usa: {allowed}.')

    if not is_existing_file and value.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f'El archivo supera el tamaño máximo permitido ({MAX_UPLOAD_SIZE // (1024 * 1024)} MB).')

    basename = os.path.basename(value.name)
    if not is_existing_file and (basename != value.name or basename in {'', '.', '..'}):
        raise ValidationError('El nombre del archivo no es válido.')


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'accent_color', 'orbit_color', 'order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
            'orbit_color': forms.TextInput(attrs={'type': 'text'}),
        }


class PostForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True).order_by('order', 'name'),
        label='Planeta',
        help_text='Selecciona el planeta al que pertenece la publicación.'
    )

    class Meta:
        model = Post
        fields = [
            'title',
            'summary',
            'content',
            'category',
            'cover_image',
            'attachment',
            'video_url',
            'status',
        ]
        labels = {
            'title': 'Título de la publicación',
            'summary': 'Resumen',
            'content': 'Contenido',
            'cover_image': 'Imagen de portada',
            'attachment': 'Archivo adjunto (PDF, DOCX, PPTX)',
            'video_url': 'Enlace a video',
            'status': 'Estado',
        }
        help_texts = {
            'status': 'Elige si la publicación será visible para visitantes o si quedará como borrador.',
        }
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 8}),
            'video_url': forms.URLInput(attrs={'placeholder': 'https://www.youtube.com/watch?v=...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sun_category = Category.objects.filter(slug='sol').first()
        if sun_category:
            self.fields['category'].widget.attrs['data-sun-category'] = str(sun_category.pk)
            self.fields['attachment'].help_text = 'Para Sol, adjunta un archivo PDF, DOCX o PPTX.'

    def clean_cover_image(self):
        value = self.cleaned_data.get('cover_image')
        validate_upload(value, ALLOWED_IMAGE_EXTENSIONS)
        if value and not isinstance(value, FieldFile):
            value.name = sanitize_upload_name(value.name)
        return value

    def clean_attachment(self):
        value = self.cleaned_data.get('attachment')
        validate_upload(value, ALLOWED_ATTACHMENT_EXTENSIONS)
        if value and not isinstance(value, FieldFile):
            value.name = sanitize_upload_name(value.name)
        return value

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        if category and category.slug == 'sol':
            attachment = cleaned_data.get('attachment')
            cover_image = cleaned_data.get('cover_image')
            video_url = cleaned_data.get('video_url', '').strip()

            if not attachment:
                self.add_error('attachment', 'Para publicar en Sol debes adjuntar un documento.')
            else:
                extension = os.path.splitext(attachment.name)[1].lower().lstrip('.')
                if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
                    self.add_error('attachment', 'Sol solo acepta documentos PDF, DOCX o PPTX.')

            if cover_image:
                self.add_error('cover_image', 'Sol es exclusivamente para documentos, no imágenes.')
            if video_url:
                self.add_error('video_url', 'Sol es exclusivamente para documentos, no videos.')

        return cleaned_data

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if len(title) < 5:
            raise ValidationError('El título debe tener al menos 5 caracteres.')
        return title

    def clean_summary(self):
        summary = self.cleaned_data.get('summary', '').strip()
        if len(summary) < 20:
            raise ValidationError('El resumen debe tener al menos 20 caracteres.')
        return summary

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if len(content) < 30:
            raise ValidationError('El contenido debe tener al menos 30 caracteres.')
        return content
