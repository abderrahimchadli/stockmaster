from django.views import View
from django.shortcuts import render
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q

from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product, InventoryLevel, InventoryLog
from apps.rules.models import Rule, RuleApplication
from apps.notifications.models import Notification
from apps.analytics.models import DailySummary


class DashboardView(View):
    """Main dashboard view showing summary of inventory and app status."""
    
    def get(self, request):
        """Main dashboard view."""
        # Get the current shop from session
        shop = request.session.get('shop')
        
        if not shop:
            return render(request, 'dashboard/error.html', {'error': 'No shop selected', 'base_template': 'base.html'})
            
        try:
            store = ShopifyStore.objects.get(shop_url=shop, is_active=True)
            
            # Update last access timestamp
            store.update_last_access()
            
            # Get inventory summary
            total_products = Product.objects.filter(store=store).count()
            
            out_of_stock_products = Product.objects.filter(
                store=store,
                variants__inventory_levels__available__lte=0
            ).distinct().count()
            
            hidden_products = Product.objects.filter(
                store=store,
                is_visible=False
            ).count()
            
            # Get rule summary
            active_rules = Rule.objects.filter(
                store=store,
                is_active=True
            ).count()
            
            rule_applications_pending = RuleApplication.objects.filter(
                rule__store=store,
                status='pending'
            ).count()
            
            rule_applications_last_24h = RuleApplication.objects.filter(
                rule__store=store,
                applied_at__gte=timezone.now() - timezone.timedelta(days=1)
            ).count()
            
            # Get recent inventory logs
            recent_logs = InventoryLog.objects.filter(
                store=store
            ).order_by('-created_at')[:10]
            
            # Get recent notifications
            recent_notifications = Notification.objects.filter(
                store=store
            ).order_by('-created_at')[:5]
            
            # Check subscription status
            is_trial = store.is_trial
            trial_days_left = store.trial_days_left if is_trial else 0
            
            # Inventory graph data (last 14 days)
            start_date = timezone.now().date() - timezone.timedelta(days=13)
            
            daily_summaries = DailySummary.objects.filter(
                store=store,
                date__gte=start_date
            ).order_by('date')
            
            graph_labels = []
            out_of_stock_data = []
            hidden_products_data = []
            
            current_date = start_date
            end_date = timezone.now().date()
            
            # Create a dictionary for quick lookup
            summary_dict = {summary.date: summary for summary in daily_summaries}
            
            while current_date <= end_date:
                graph_labels.append(current_date.strftime('%b %d'))
                
                if current_date in summary_dict:
                    summary = summary_dict[current_date]
                    out_of_stock_data.append(summary.out_of_stock_products)
                    hidden_products_data.append(summary.hidden_products)
                else:
                    # No data for this date
                    out_of_stock_data.append(0)
                    hidden_products_data.append(0)
                
                current_date += timezone.timedelta(days=1)
            
            context = {
                'store': store,
                'sync_status': store.sync_status,
                'last_sync_at': store.last_sync_at,
                'total_products': total_products,
                'out_of_stock_products': out_of_stock_products,
                'hidden_products': hidden_products,
                'active_rules': active_rules,
                'rule_applications_pending': rule_applications_pending,
                'rule_applications_last_24h': rule_applications_last_24h,
                'recent_logs': recent_logs,
                'recent_notifications': recent_notifications,
                'is_trial': is_trial,
                'trial_days_left': trial_days_left,
                'graph_labels': graph_labels,
                'out_of_stock_data': out_of_stock_data,
                'hidden_products_data': hidden_products_data,
                'base_template': 'base.html'
            }
            
            return render(request, 'dashboard/index.html', context)
            
        except ShopifyStore.DoesNotExist:
            messages.error(request, f"Store {shop} not found")
            # Render the error using the determined base template
            return render(request, 'dashboard/error.html', {
                'error': f"Store {shop} not found", 
                'base_template': 'base.html'
            }) 