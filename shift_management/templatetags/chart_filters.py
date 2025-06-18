from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """数値を掛け算するフィルター"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """数値を足し算するフィルター"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def lookup(dictionary, key):
    """辞書のキーで値を取得するフィルター"""
    try:
        return dictionary.get(key, [])
    except (AttributeError, TypeError):
        return [] 