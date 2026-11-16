from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from .forms import PostForm
from .models import Category, Post


class PostFormSunDocumentTests(TestCase):
    def setUp(self):
        self.sun, _ = Category.objects.get_or_create(
            slug='sol',
            defaults={
                'name': 'Sol',
                'description': 'Documentos educativos.',
                'order': 0,
            },
        )
        self.venus, _ = Category.objects.get_or_create(
            slug='venus',
            defaults={
                'name': 'Venus',
                'description': 'Contenido educativo.',
                'order': 1,
            },
        )

    def form_data(self, category, **extra):
        return {
            'title': 'Guía de aprendizaje',
            'summary': 'Una guía educativa con actividades para el aula.',
            'content': 'Contenido de aprendizaje para apoyar las actividades en el aula.',
            'category': str(category.pk),
            'status': 'draft',
            **extra,
        }

    def test_sun_accepts_document_files(self):
        for extension in ('pdf', 'docx', 'pptx'):
            with self.subTest(extension=extension):
                document = SimpleUploadedFile(f'guia.{extension}', b'document content')
                form = PostForm(self.form_data(self.sun), files={'attachment': document})
                self.assertTrue(form.is_valid(), form.errors)

    def test_sun_requires_a_document(self):
        form = PostForm(self.form_data(self.sun))

        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

    def test_sun_rejects_images_as_attachments(self):
        image = SimpleUploadedFile('foto.png', b'image content', content_type='image/png')
        form = PostForm(self.form_data(self.sun), files={'attachment': image})

        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)

    def test_sun_rejects_cover_images_and_videos(self):
        document = SimpleUploadedFile('guia.docx', b'DOCX content')
        cover = SimpleUploadedFile('portada.png', b'image content', content_type='image/png')
        form = PostForm(
            self.form_data(self.sun, video_url='https://example.com/video'),
            files={'attachment': document, 'cover_image': cover},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('cover_image', form.errors)
        self.assertIn('video_url', form.errors)

    def test_other_categories_still_allow_text_posts(self):
        form = PostForm(self.form_data(self.venus))

        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_sun_post_keeps_existing_document_path(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            post = Post.objects.create(
                title='Guía existente',
                slug='guia-existente',
                summary='Una guía educativa que ya se encuentra almacenada.',
                content='Contenido de aprendizaje asociado a un documento ya guardado.',
                category=self.sun,
                author=get_user_model().objects.create_user(username='sun-editor'),
                status=Post.DRAFT,
            )
            post.attachment.save('guia-existente.pdf', ContentFile(b'PDF content'), save=True)
            existing_name = post.attachment.name

            form = PostForm(self.form_data(self.sun), instance=post)

            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['attachment'].name, existing_name)


@override_settings(
    DEBUG=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class SunDocumentsForGuestsTests(TestCase):
    def setUp(self):
        self.sun, _ = Category.objects.get_or_create(
            slug='sol',
            defaults={
                'name': 'Sol',
                'description': 'Documentos educativos.',
                'order': 0,
            },
        )
        self.author = get_user_model().objects.create_user(username='sun-author', password='test-password')
        self.document = Post.objects.create(
            title='Guía para invitados',
            slug='guia-para-invitados',
            summary='Una guía educativa disponible para visitantes.',
            content='Contenido educativo para leer junto con el documento descargable.',
            category=self.sun,
            author=self.author,
            attachment='attachments/guia-invitados.pdf',
            status=Post.PUBLISHED,
        )
        Post.objects.create(
            title='Borrador privado',
            slug='borrador-privado-sol',
            summary='Este documento todavía no está publicado.',
            content='El contenido en borrador no debe mostrarse a los visitantes.',
            category=self.sun,
            author=self.author,
            attachment='attachments/borrador.pdf',
            status=Post.DRAFT,
        )
        Post.objects.create(
            title='Contenido antiguo no documental',
            slug='contenido-antiguo-no-documental',
            summary='Este contenido antiguo tiene un video no permitido en Sol.',
            content='Sol debe mostrar solamente documentos a las personas invitadas.',
            category=self.sun,
            author=self.author,
            attachment='attachments/antiguo.pdf',
            video_url='https://example.com/video',
            status=Post.PUBLISHED,
        )

    def test_guest_homepage_shows_only_published_sun_documents(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        sun_data = next(category for category in response.context['category_data'] if category['slug'] == 'sol')
        self.assertEqual([post['title'] for post in sun_data['posts']], ['Guía para invitados'])
        self.assertEqual(sun_data['posts'][0]['attachment'], '/media/attachments/guia-invitados.pdf')

    def test_guest_can_open_published_sun_document(self):
        response = self.client.get(reverse('post_detail', args=[self.document.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Descargar documento')

    def test_guest_cannot_open_unpublished_sun_document(self):
        response = self.client.get(reverse('post_detail', args=['borrador-privado-sol']))

        self.assertEqual(response.status_code, 404)

    def test_sun_category_hides_non_document_posts_from_guests(self):
        response = self.client.get(reverse('category_detail', args=['sol']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Guía para invitados')
        self.assertNotContains(response, 'Contenido antiguo no documental')
