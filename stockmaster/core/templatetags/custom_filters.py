from django import template
from decimal import Decimal, InvalidOperation
import json

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return None


@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return None


@register.filter
def add(value, arg):
    """Add the argument to the value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return None


@register.filter
def percentage(value, arg):
    """Calculate percentage: (value / arg) * 100"""
    try:
        return (float(value) / float(arg)) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return None


@register.filter
def to_json(value):
    """Convert a value to JSON string"""
    return json.dumps(value)


@register.filter
def currency(value, precision=2):
    """Format value as currency with specified precision"""
    try:
        decimal_value = Decimal(str(value)).quantize(Decimal(10) ** -int(precision))
        return f"{decimal_value:,.{precision}f}"
    except (ValueError, TypeError, InvalidOperation):
        return value 