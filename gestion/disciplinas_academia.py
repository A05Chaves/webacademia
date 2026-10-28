from django import forms
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from clases.models import DisciplinaAcademia, ClaseProgramada
from .decorators import administrador_required


class DisciplinaAcademiaForm(forms.ModelForm):
    class Meta:
        model = DisciplinaAcademia
        fields = ['nombre', 'activa']
        widgets = {'nombre': forms.TextInput(attrs={'class': 'form-control'}), 'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'})}

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if DisciplinaAcademia.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe una disciplina con ese nombre.')
        return nombre


@administrador_required
def configurar(request, disciplina_id=None):
    disciplina = get_object_or_404(DisciplinaAcademia, pk=disciplina_id) if disciplina_id else None
    form = DisciplinaAcademiaForm(request.POST or None, instance=disciplina) if disciplina else None
    if request.method == 'POST' and form and form.is_valid():
        form.save()
        messages.success(request, 'Disciplina actualizada. Las clases y asistencias conservan sus registros.')
        return redirect('gestion:configurar_disciplinas')
    cantidades = dict(ClaseProgramada.objects.values('disciplina').annotate(total=Count('pk')).values_list('disciplina', 'total'))
    disciplinas = list(DisciplinaAcademia.objects.all())
    for item in disciplinas:
        item.total_clases = cantidades.get(item.codigo, 0)
    return render(request, 'gestion/configurar_disciplinas.html', {'disciplinas': disciplinas, 'form': form, 'disciplina_editando': disciplina})
