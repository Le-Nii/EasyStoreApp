from django.conf.urls import url
from django.views.generic import RedirectView
from . import views
from django.urls import path

urlpatterns = [
    path('', views.index, name='index'),
    path('resert/', views.resert, name='resert'),
    path('addition/', views.addition, name='addition'),
    path('order/reset/', views.reset_order, name='reset_order'),
    path('order/', views.order, name='order'),
    path('pay/cash/', views.payment_cash, name='payment_cash'),
    path('view-order/<order_id>', views.view_order, name='view_order'),
    path('print-order/<order_id>/', views.print_order, name='print_order'),
    path('print-current-order/', views.print_current_order, name='print_current_order'),
    path('stock/', views.view_stock, name='view_stock'),
    path('pay/credit/', views.payment_credit, name='payment_credit'),
    path('purchases/', views.PurchaseListView.as_view(), name='purchases'),
    # path('purchase/<int:pk>', views.PurchaseDetailView.as_view(), name='purchase-detail'),
    path('purchase/create/', views.PurchaseCreate.as_view(), name='purchase_create'),
    path('purchase/<int:pk>/update/', views.PurchaseUpdate.as_view(), name='purchase_update'),
    path('otherpurchases/', views.OtherPurchaseListView.as_view(), name='otherpurchases'),
    # path('purchase/<int:pk>', views.PurchaseDetailView.as_view(), name='purchase-detail'),
    path('otherpurchase/create/', views.OtherPurchaseCreate.as_view(), name='otherpurchase_create'),
    path('otherpurchase/<int:pk>/update/', views.OtherPurchaseUpdate.as_view(), name='otherpurchase_update'),
    path('product/create/', views.ProductCreate.as_view(), name='product_create'),
    path('product/<int:pk>/update/', views.ProductUpdate.as_view(), name='product_update'),
    path('report/', views.report, name='report'),
    path('customreport/', views.custom_report, name='custom_report'),
]

urlpatterns += [
    url(r'^order/add/(?P<product_id>[0-9]*/?$)', views.order_add_product, name='order_add_product'),
    url(r'^order/remove/(?P<product_id>[0-9]*)/?$', views.order_remove_product, name="order_remove_product"),
    url(r'^cash/(?P<amount>[0-9\.]*)/?$', views.cash, name='cash'),
]