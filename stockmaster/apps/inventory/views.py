from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    """
    Inventory dashboard view - renders full page or just content block for AJAX.
    """
    # Determine the base template based on the request type
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        base_template = 'ajax_base.html'
    else:
        base_template = 'base.html'
    
    context = {
        'title': 'Inventory Management',
        'active_tab': 'inventory',
        'base_template': base_template # Pass the template name to the context
    }
    return render(request, 'inventory/index.html', context) 