from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
import requests
import json

from core.utils.logger import logger
from apps.accounts.models import ShopifyStore
from apps.rules.models import Rule
from apps.inventory.models import Product
from .models import NotificationChannel, NotificationPreference, Notification


@shared_task
def send_rule_applied_notification(store_id, rule_id, product_id):
    """
    Send notifications when a rule is applied to a product.
    
    Args:
        store_id (int): The store ID
        rule_id (int): The rule ID
        product_id (int): The product ID
        
    Returns:
        dict: Summary of operations performed
    """
    try:
        store = ShopifyStore.objects.get(id=store_id)
        rule = Rule.objects.get(id=rule_id)
        product = Product.objects.get(id=product_id)
        
        # Find notification preferences for rule applied events
        preferences = NotificationPreference.objects.filter(
            store=store,
            event_type='rule_applied',
            is_active=True
        )
        
        sent_count = 0
        for preference in preferences:
            # Check if product matches preference filters
            if not preference_matches_product(preference, product):
                continue
                
            # Get the channel
            channel = preference.channel
            if not channel.is_active:
                continue
                
            # Create notification record
            notification = Notification.objects.create(
                store=store,
                channel=channel,
                event_type='rule_applied',
                title=f"Rule Applied: {rule.name}",
                message=f"The rule '{rule.name}' has been applied to product '{product.title}'.",
                object_type='rule_application',
                object_id=str(rule.id),
                status='pending'
            )
            
            # Send the notification through the appropriate channel
            success = send_notification(notification, {
                'rule': rule,
                'product': product,
                'store': store,
                'action_type': rule.get_action_type_display(),
                'trigger_type': rule.get_trigger_type_display(),
            })
            
            if success:
                sent_count += 1
        
        return {
            'status': 'success',
            'sent_count': sent_count,
            'total_preferences': preferences.count()
        }
        
    except ShopifyStore.DoesNotExist:
        logger.error(f"Store with ID {store_id} not found")
        return {'status': 'error', 'message': f"Store with ID {store_id} not found"}
        
    except Rule.DoesNotExist:
        logger.error(f"Rule with ID {rule_id} not found")
        return {'status': 'error', 'message': f"Rule with ID {rule_id} not found"}
        
    except Product.DoesNotExist:
        logger.error(f"Product with ID {product_id} not found")
        return {'status': 'error', 'message': f"Product with ID {product_id} not found"}
        
    except Exception as e:
        logger.exception(f"Error sending rule applied notification: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_out_of_stock_notification(store_id, product_id):
    """
    Send notifications when a product goes out of stock.
    
    Args:
        store_id (int): The store ID
        product_id (int): The product ID
        
    Returns:
        dict: Summary of operations performed
    """
    try:
        store = ShopifyStore.objects.get(id=store_id)
        product = Product.objects.get(id=product_id)
        
        # Find notification preferences for out of stock events
        preferences = NotificationPreference.objects.filter(
            store=store,
            event_type='out_of_stock',
            is_active=True
        )
        
        sent_count = 0
        for preference in preferences:
            # Check if product matches preference filters
            if not preference_matches_product(preference, product):
                continue
                
            # Get the channel
            channel = preference.channel
            if not channel.is_active:
                continue
                
            # Create notification record
            notification = Notification.objects.create(
                store=store,
                channel=channel,
                event_type='out_of_stock',
                title=f"Product Out of Stock: {product.title}",
                message=f"The product '{product.title}' is now out of stock.",
                object_type='product',
                object_id=str(product.id),
                status='pending'
            )
            
            # Send the notification through the appropriate channel
            success = send_notification(notification, {
                'product': product,
                'store': store,
                'shopify_admin_url': product.shopify_admin_url,
            })
            
            if success:
                sent_count += 1
        
        return {
            'status': 'success',
            'sent_count': sent_count,
            'total_preferences': preferences.count()
        }
        
    except ShopifyStore.DoesNotExist:
        logger.error(f"Store with ID {store_id} not found")
        return {'status': 'error', 'message': f"Store with ID {store_id} not found"}
        
    except Product.DoesNotExist:
        logger.error(f"Product with ID {product_id} not found")
        return {'status': 'error', 'message': f"Product with ID {product_id} not found"}
        
    except Exception as e:
        logger.exception(f"Error sending out of stock notification: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def preference_matches_product(preference, product):
    """
    Check if a notification preference matches a product based on filters.
    
    Args:
        preference (NotificationPreference): The preference to check
        product (Product): The product to check against
        
    Returns:
        bool: True if the preference matches the product, False otherwise
    """
    # Check product type filter
    if preference.product_type_filter and preference.product_type_filter != product.product_type:
        return False
    
    # Check vendor filter
    if preference.vendor_filter and preference.vendor_filter != product.vendor:
        return False
    
    # TODO: Implement tag filter when available
    
    return True


def send_notification(notification, context):
    """
    Send a notification through the appropriate channel.
    
    Args:
        notification (Notification): The notification to send
        context (dict): Additional context for the notification
        
    Returns:
        bool: True if the notification was sent successfully, False otherwise
    """
    channel = notification.channel
    channel_type = channel.channel_type
    
    try:
        if channel_type == 'email':
            success = send_email_notification(notification, channel, context)
        elif channel_type == 'slack':
            success = send_slack_notification(notification, channel, context)
        elif channel_type == 'webhook':
            success = send_webhook_notification(notification, channel, context)
        elif channel_type == 'in_app':
            # In-app notifications are handled differently (they're already created)
            success = True
            notification.mark_as_sent()
        else:
            logger.error(f"Unsupported channel type: {channel_type}")
            notification.mark_as_failed(f"Unsupported channel type: {channel_type}")
            return False
        
        if success:
            logger.info(f"Notification sent: {notification.title}")
            return True
        else:
            logger.error(f"Failed to send notification: {notification.title}")
            return False
            
    except Exception as e:
        error_message = str(e)
        logger.exception(f"Error sending notification: {error_message}")
        notification.mark_as_failed(error_message)
        return False


def send_email_notification(notification, channel, context):
    """Send a notification via email."""
    if not channel.email_recipients:
        notification.mark_as_failed("No email recipients specified")
        return False
    
    subject = notification.title
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email.strip() for email in channel.email_recipients.split(',')]
    
    # Prepare the email content
    context.update({
        'notification': notification,
        'channel': channel,
        'store': notification.store,
        'app_url': settings.APP_URL,
    })
    
    html_message = render_to_string('notifications/email/notification.html', context)
    plain_message = render_to_string('notifications/email/notification.txt', context)
    
    try:
        # Send the email
        sent = send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        
        if sent:
            notification.mark_as_sent()
            return True
        else:
            notification.mark_as_failed("Failed to send email")
            return False
            
    except Exception as e:
        notification.mark_as_failed(str(e))
        return False


def send_slack_notification(notification, channel, context):
    """Send a notification via Slack webhook."""
    if not channel.slack_webhook_url:
        notification.mark_as_failed("No Slack webhook URL specified")
        return False
    
    # Prepare the Slack message
    message = {
        "text": notification.title,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": notification.title
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": notification.message
                }
            }
        ]
    }
    
    # Add additional blocks based on the notification type
    if notification.event_type == 'rule_applied' and 'product' in context and 'rule' in context:
        product = context['product']
        rule = context['rule']
        
        message["blocks"].append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Product:*\n{product.title}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Rule:*\n{rule.name}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Action:*\n{context.get('action_type', rule.action_type)}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Trigger:*\n{context.get('trigger_type', rule.trigger_type)}"
                }
            ]
        })
        
        message["blocks"].append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in Shopify"
                    },
                    "url": product.shopify_admin_url
                }
            ]
        })
    
    elif notification.event_type == 'out_of_stock' and 'product' in context:
        product = context['product']
        
        message["blocks"].append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Product:*\n{product.title}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\nOut of Stock"
                }
            ]
        })
        
        message["blocks"].append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in Shopify"
                    },
                    "url": product.shopify_admin_url
                }
            ]
        })
    
    try:
        # Send the message to Slack
        response = requests.post(
            channel.slack_webhook_url,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            notification.mark_as_sent()
            return True
        else:
            notification.mark_as_failed(f"Slack returned error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        notification.mark_as_failed(str(e))
        return False


def send_webhook_notification(notification, channel, context):
    """Send a notification via webhook."""
    if not channel.webhook_url:
        notification.mark_as_failed("No webhook URL specified")
        return False
    
    # Prepare the webhook payload
    payload = {
        "notification_id": notification.id,
        "event_type": notification.event_type,
        "title": notification.title,
        "message": notification.message,
        "timestamp": timezone.now().isoformat(),
        "store": notification.store.shop_url,
    }
    
    # Add specific data based on notification type
    if notification.object_type and notification.object_id:
        payload["object_type"] = notification.object_type
        payload["object_id"] = notification.object_id
    
    # Add context-specific data
    if notification.event_type == 'rule_applied' and 'rule' in context and 'product' in context:
        payload["rule"] = {
            "id": context['rule'].id,
            "name": context['rule'].name,
            "action_type": context['rule'].action_type,
            "trigger_type": context['rule'].trigger_type
        }
        payload["product"] = {
            "id": context['product'].id,
            "title": context['product'].title,
            "shopify_id": context['product'].shopify_id,
            "shopify_admin_url": context['product'].shopify_admin_url
        }
    
    elif notification.event_type == 'out_of_stock' and 'product' in context:
        payload["product"] = {
            "id": context['product'].id,
            "title": context['product'].title,
            "shopify_id": context['product'].shopify_id,
            "shopify_admin_url": context['product'].shopify_admin_url
        }
    
    # Add webhook signature if a secret is provided
    headers = {'Content-Type': 'application/json'}
    if channel.webhook_secret:
        # Create a signature (implementation would depend on your security requirements)
        # For example, you might use HMAC-SHA256 to sign the payload
        # This is a simplified example:
        import hmac
        import hashlib
        
        payload_str = json.dumps(payload)
        signature = hmac.new(
            channel.webhook_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers['X-StockMaster-Signature'] = signature
    
    try:
        # Send the webhook
        response = requests.post(
            channel.webhook_url,
            data=json.dumps(payload),
            headers=headers
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            notification.mark_as_sent()
            return True
        else:
            notification.mark_as_failed(f"Webhook returned error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        notification.mark_as_failed(str(e))
        return False 