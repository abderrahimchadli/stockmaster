from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .utils import rule_matches_product

logger = logging.getLogger(__name__)

def process_out_of_stock_rules(store, product):
    """
    Process rules for an out-of-stock product.
    """
    from apps.rules.models import Rule
    
    logger.info(f"Processing out-of-stock rules for product {product.id} in store {store.id}")
    
    # Get all active rules for this store
    rules = Rule.objects.filter(
        store=store,
        is_active=True,
        trigger_type='out_of_stock'
    ).order_by('priority')
    
    for rule in rules:
        if rule_matches_product(rule, product):
            logger.info(f"Rule {rule.id} matches product {product.id}")
            schedule_rule_application(rule, product)


def schedule_rule_application(rule, product):
    """
    Schedule a rule application.
    """
    from apps.rules.models import RuleApplication
    
    # Check if there's already a pending application for this rule and product
    existing = RuleApplication.objects.filter(
        rule=rule,
        product=product,
        status='pending'
    ).exists()
    
    if existing:
        logger.info(f"Rule {rule.id} already scheduled for product {product.id}")
        return
    
    # Calculate when to apply the rule based on delay
    apply_at = timezone.now()
    if rule.delay_minutes > 0:
        apply_at = apply_at + timezone.timedelta(minutes=rule.delay_minutes)
    
    # Create the rule application
    application = RuleApplication.objects.create(
        rule=rule,
        product=product,
        status='pending',
        scheduled_at=apply_at
    )
    
    logger.info(f"Scheduled rule {rule.id} for product {product.id} at {apply_at}")
    
    # If no delay, apply immediately
    if rule.delay_minutes <= 0:
        apply_rule.delay(application.id)


@shared_task
def apply_rule(rule_application_id):
    """
    Apply a rule to a product.
    """
    from apps.rules.models import RuleApplication
    from apps.notifications.tasks import send_rule_applied_notification
    
    logger.info(f"Applying rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            # Get the rule application
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            # Skip if it's already been applied or cancelled
            if application.status != 'pending':
                logger.info(f"Rule application {rule_application_id} is not pending, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            # Apply the rule logic based on rule type
            rule = application.rule
            product = application.product
            
            if rule.action_type == 'hide_product':
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.save(update_fields=['is_visible', 'hidden_at'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}")
            
            elif rule.action_type == 'schedule_return':
                # Calculate return time based on rule
                return_at = timezone.now() + timezone.timedelta(days=rule.return_days)
                
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.scheduled_return = return_at
                product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}, scheduled return at {return_at}")
                
                # Schedule restoration
                restore_product.apply_async(
                    args=[application.id],
                    eta=return_at
                )
            
            # Mark the application as applied
            application.status = 'applied'
            application.applied_at = timezone.now()
            application.save(update_fields=['status', 'applied_at'])
            
            # Create inventory log
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='rule',
                previous_status='visible' if product.is_visible else 'hidden',
                new_status='hidden',
                notes=f"Rule '{rule.name}' applied"
            )
            
            # Send notification if enabled
            if rule.send_notification:
                send_rule_applied_notification.delay(application.id)
            
            return {
                'status': 'success',
                'rule_id': rule.id,
                'product_id': product.id,
                'action': rule.action_type
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error applying rule: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_scheduled_rules():
    """
    Check for scheduled rules that need to be applied.
    """
    from apps.rules.models import RuleApplication
    
    logger.info("Checking for scheduled rules to apply")
    
    now = timezone.now()
    
    # Find all pending applications that are scheduled for now or earlier
    applications = RuleApplication.objects.filter(
        status='pending',
        scheduled_at__lte=now
    )
    
    if not applications.exists():
        logger.info("No scheduled rules to apply")
        return {'status': 'success', 'count': 0}
    
    logger.info(f"Found {applications.count()} scheduled rules to apply")
    
    # Apply each rule
    count = 0
    for application in applications:
        apply_rule.delay(application.id)
        count += 1
    
    return {'status': 'success', 'count': count}


@shared_task
def restore_product(rule_application_id):
    """
    Restore a product after a rule has been applied.
    """
    from apps.rules.models import RuleApplication
    
    logger.info(f"Restoring product for rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            # Get the rule application
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            # Skip if it wasn't applied
            if application.status != 'applied':
                logger.info(f"Rule application {rule_application_id} was not applied, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            product = application.product
            
            # Make the product visible again
            product.is_visible = True
            product.hidden_at = None
            product.scheduled_return = None
            product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
            
            # Create inventory log
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='schedule',
                previous_status='hidden',
                new_status='visible',
                notes=f"Product restored after rule '{application.rule.name}'"
            )
            
            # Mark the application as restored
            application.status = 'restored'
            application.restored_at = timezone.now()
            application.save(update_fields=['status', 'restored_at'])
            
            logger.info(f"Product {product.id} restored after rule {application.rule.id}")
            
            return {
                'status': 'success',
                'rule_id': application.rule.id,
                'product_id': product.id
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error restoring product: {str(e)}")
        return {'status': 'error', 'message': str(e)} 
from django.utils import timezone
from django.db import transaction
import logging

from .utils import rule_matches_product

logger = logging.getLogger(__name__)

def process_out_of_stock_rules(store, product):
    """
    Process rules for an out-of-stock product.
    """
    from apps.rules.models import Rule
    
    logger.info(f"Processing out-of-stock rules for product {product.id} in store {store.id}")
    
    # Get all active rules for this store
    rules = Rule.objects.filter(
        store=store,
        is_active=True,
        trigger_type='out_of_stock'
    ).order_by('priority')
    
    for rule in rules:
        if rule_matches_product(rule, product):
            logger.info(f"Rule {rule.id} matches product {product.id}")
            schedule_rule_application(rule, product)


def schedule_rule_application(rule, product):
    """
    Schedule a rule application.
    """
    from apps.rules.models import RuleApplication
    
    # Check if there's already a pending application for this rule and product
    existing = RuleApplication.objects.filter(
        rule=rule,
        product=product,
        status='pending'
    ).exists()
    
    if existing:
        logger.info(f"Rule {rule.id} already scheduled for product {product.id}")
        return
    
    # Calculate when to apply the rule based on delay
    apply_at = timezone.now()
    if rule.delay_minutes > 0:
        apply_at = apply_at + timezone.timedelta(minutes=rule.delay_minutes)
    
    # Create the rule application
    application = RuleApplication.objects.create(
        rule=rule,
        product=product,
        status='pending',
        scheduled_at=apply_at
    )
    
    logger.info(f"Scheduled rule {rule.id} for product {product.id} at {apply_at}")
    
    # If no delay, apply immediately
    if rule.delay_minutes <= 0:
        apply_rule.delay(application.id)


@shared_task
def apply_rule(rule_application_id):
    """
    Apply a rule to a product.
    """
    from apps.rules.models import RuleApplication
    from apps.notifications.tasks import send_rule_applied_notification
    
    logger.info(f"Applying rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            # Get the rule application
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            # Skip if it's already been applied or cancelled
            if application.status != 'pending':
                logger.info(f"Rule application {rule_application_id} is not pending, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            # Apply the rule logic based on rule type
            rule = application.rule
            product = application.product
            
            if rule.action_type == 'hide_product':
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.save(update_fields=['is_visible', 'hidden_at'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}")
            
            elif rule.action_type == 'schedule_return':
                # Calculate return time based on rule
                return_at = timezone.now() + timezone.timedelta(days=rule.return_days)
                
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.scheduled_return = return_at
                product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}, scheduled return at {return_at}")
                
                # Schedule restoration
                restore_product.apply_async(
                    args=[application.id],
                    eta=return_at
                )
            
            # Mark the application as applied
            application.status = 'applied'
            application.applied_at = timezone.now()
            application.save(update_fields=['status', 'applied_at'])
            
            # Create inventory log
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='rule',
                previous_status='visible' if product.is_visible else 'hidden',
                new_status='hidden',
                notes=f"Rule '{rule.name}' applied"
            )
            
            # Send notification if enabled
            if rule.send_notification:
                send_rule_applied_notification.delay(application.id)
            
            return {
                'status': 'success',
                'rule_id': rule.id,
                'product_id': product.id,
                'action': rule.action_type
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error applying rule: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_scheduled_rules():
    """
    Check for scheduled rules that need to be applied.
    """
    from apps.rules.models import RuleApplication
    
    logger.info("Checking for scheduled rules to apply")
    
    now = timezone.now()
    
    # Find all pending applications that are scheduled for now or earlier
    applications = RuleApplication.objects.filter(
        status='pending',
        scheduled_at__lte=now
    )
    
    if not applications.exists():
        logger.info("No scheduled rules to apply")
        return {'status': 'success', 'count': 0}
    
    logger.info(f"Found {applications.count()} scheduled rules to apply")
    
    # Apply each rule
    count = 0
    for application in applications:
        apply_rule.delay(application.id)
        count += 1
    
    return {'status': 'success', 'count': count}


@shared_task
def restore_product(rule_application_id):
    """
    Restore a product after a rule has been applied.
    """
    from apps.rules.models import RuleApplication
    
    logger.info(f"Restoring product for rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            # Get the rule application
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            # Skip if it wasn't applied
            if application.status != 'applied':
                logger.info(f"Rule application {rule_application_id} was not applied, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            product = application.product
            
            # Make the product visible again
            product.is_visible = True
            product.hidden_at = None
            product.scheduled_return = None
            product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
            
            # Create inventory log
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='schedule',
                previous_status='hidden',
                new_status='visible',
                notes=f"Product restored after rule '{application.rule.name}'"
            )
            
            # Mark the application as restored
            application.status = 'restored'
            application.restored_at = timezone.now()
            application.save(update_fields=['status', 'restored_at'])
            
            logger.info(f"Product {product.id} restored after rule {application.rule.id}")
            
            return {
                'status': 'success',
                'rule_id': application.rule.id,
                'product_id': product.id
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error restoring product: {str(e)}")
        return {'status': 'error', 'message': str(e)} 