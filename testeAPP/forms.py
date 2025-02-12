from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    cnpj = forms.CharField(max_length=14, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'cnpj', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()  # O sinal post_save criará o perfil automaticamente
        return user