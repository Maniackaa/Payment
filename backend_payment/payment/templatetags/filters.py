from django import template
register = template.Library()


@register.filter
def get_value_from_dict(dict_data, key):
    if not dict_data:
        return ''
    return dict_data.get(key, '')
