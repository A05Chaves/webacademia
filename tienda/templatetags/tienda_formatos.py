from django import template
from django.template.defaultfilters import floatformat as django_floatformat


register = template.Library()


@register.filter(name='floatformat')
def floatformat_agrupado(valor, argumento=-1):
    """Aplica separadores de miles solo en las plantillas de la tienda."""
    argumento = str(argumento)
    if 'g' not in argumento:
        argumento += 'g'
    return django_floatformat(valor, argumento)
