from django import template
from bs4 import BeautifulSoup
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def remove_lead_image(html):
    if not html:
        return html
    soup = BeautifulSoup(html, 'html.parser')
    first_img = soup.find('img')
    if first_img:
        fig = first_img.find_parent('figure')
        (fig or first_img).decompose()
    return mark_safe(str(soup))
