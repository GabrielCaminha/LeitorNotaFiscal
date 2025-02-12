from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cnpj = models.CharField(max_length=14, unique=True)

    def __str__(self):
        return self.user.username

# Novo modelo para os arquivos XML
class XMLFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='xml_files')
    xml_file = models.FileField(upload_to='xml_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"XML de {self.user.username} enviado em {self.uploaded_at}"

# Sinais para criar/atualizar o Profile automaticamente quando um User é criado
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:  # Cria o perfil apenas se o usuário for novo
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):  # Verifica se o perfil já existe
        instance.profile.save()
