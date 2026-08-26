from django import template

register = template.Library()

@register.simple_tag
def get_elided_page_range(page_obj):
    if not page_obj:
        return []
    return page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
