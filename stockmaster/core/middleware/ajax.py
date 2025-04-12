import logging
from django.template.response import TemplateResponse
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.template import loader
import re

logger = logging.getLogger(__name__)

class AjaxTemplateResponseMiddleware(MiddlewareMixin):
    """
    Middleware that handles AJAX requests and returns only the content block
    instead of the entire page when ajax=1 parameter is present.
    
    This middleware works with TemplateResponse objects and changes the template
    to a content-only version (ajax_content.html) that doesn't include the layout.
    """
    
    def process_template_response(self, request, response):
        """
        If this is an AJAX request (indicated by ajax=1 query parameter),
        change the template to a content-only version.
        """
        # Skip if not a template response or not an AJAX request
        if not hasattr(response, 'template_name'):
            return response
            
        is_ajax = request.GET.get('ajax') == '1'
        if not is_ajax:
            return response
            
        logger.debug(f"[AjaxTemplateResponseMiddleware] AJAX request detected for {request.path}")
        
        # Skip admin and other paths that don't use our base template
        skip_paths = ['/admin/', '/__debug__/', '/static/']
        for path in skip_paths:
            if request.path.startswith(path):
                logger.debug(f"[AjaxTemplateResponseMiddleware] Skipping path: {request.path}")
                return response
        
        # For TemplateResponse objects, we want to only render the content block
        if isinstance(response, TemplateResponse):
            try:
                # Keep track of the original template for debugging
                original_template = response.template_name
                
                # Add the 'is_ajax' flag to the context
                if hasattr(response, 'context_data') and response.context_data is not None:
                    response.context_data['is_ajax'] = True
                
                # Change the template to our AJAX wrapper
                response.template_name = 'ajax_content.html'
                
                # Add a header to indicate this is an AJAX response
                response['X-AJAX-Response'] = '1'
                
                logger.debug(f"[AjaxTemplateResponseMiddleware] Changed template from {original_template} to {response.template_name}")
                
            except Exception as e:
                logger.error(f"[AjaxTemplateResponseMiddleware] Error processing AJAX template response: {e}")
                
        return response 

class AjaxTemplateMiddleware(MiddlewareMixin):
    """
    Middleware to handle AJAX requests by extracting only the content block.
    When a request has ajax=1 in the parameters, this middleware will extract
    only the content block from the rendered HTML response, avoiding duplicate
    layout elements.
    
    This is a fallback for responses that are not TemplateResponse objects.
    """
    
    def process_response(self, request, response):
        # Skip if not an HTML response or not an AJAX request
        if not hasattr(request, 'GET') or request.GET.get('ajax') != '1':
            return response
        
        # Skip if this response has already been processed by AjaxTemplateResponseMiddleware
        if response.get('X-AJAX-Response') == '1':
            logger.debug(f"[AjaxTemplateMiddleware] Skipping already processed response")
            return response
        
        # Log that we're processing an AJAX request
        logger.debug(f"[AjaxTemplateMiddleware] Processing AJAX request for {request.path}")
        
        if not response.get('Content-Type', '').startswith('text/html'):
            logger.debug(f"[AjaxTemplateMiddleware] Skipping non-HTML response: {response.get('Content-Type')}")
            return response
        
        # Skip admin and other paths that don't use our base template
        skip_paths = ['/admin/', '/__debug__/', '/static/']
        for path in skip_paths:
            if request.path.startswith(path):
                logger.debug(f"[AjaxTemplateMiddleware] Skipping path: {request.path}")
                return response
        
        # Get the content
        content = response.content.decode('utf-8')
        
        # Extract content between the content block tags
        # This assumes all our templates use {% block content %}...{% endblock %}
        try:
            # Match content with proper block handling, handling nested blocks
            # Try different pattern variations to match the block content
            patterns = [
                r'{%\s*block\s+content\s*%}([\s\S]*?){%\s*endblock\s*%}',
                r'{%\s*block\s+content\s*%}([\s\S]*?){%\s*endblock\s+content\s*%}',
                r'{%\s*block\s+content\s*%}([\s\S]*?){%\s*endblock(?:\s+content)?\s*%}'
            ]
            
            content_only = None
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    content_only = match.group(1)
                    logger.debug(f"[AjaxTemplateMiddleware] Found match with pattern: {pattern}")
                    break
            
            if content_only:
                logger.debug(f"[AjaxTemplateMiddleware] Successfully extracted content block ({len(content_only)} bytes)")
                
                # Add some debugging info to help identify content issues
                logger.debug(f"[AjaxTemplateMiddleware] Content preview: {content_only[:100]}...")
                
                # Replace the response content with just the content block
                response.content = content_only.encode('utf-8')
                
                # Add a header to indicate this is an AJAX response
                response['X-AJAX-Response'] = '1'
                
                return response
            else:
                logger.warning(f"[AjaxTemplateMiddleware] Could not find content block in response for {request.path}")
                logger.debug(f"[AjaxTemplateMiddleware] Content preview: {content[:300]}...")
                logger.debug(f"[AjaxTemplateMiddleware] End of content preview: {content[-300:]}")
        except Exception as e:
            # If there's an error, just return the original response
            logger.error(f"[AjaxTemplateMiddleware] Error: {e}")
            
        return response 