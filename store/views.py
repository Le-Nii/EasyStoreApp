import logging
import decimal
from django.shortcuts import render, get_object_or_404
from django.http import (HttpResponse,
                         HttpResponseForbidden,
                         HttpResponseBadRequest)
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Product, Order, Cash, Order_Item, Purchase
from django.views.generic.edit import CreateView, UpdateView
from django.forms import ModelForm
from django.views import generic
from django.urls import reverse
from django.urls import reverse_lazy
from . import helper

def index(request):
    """
    View function for home page of site.
    """
    
    # Render the HTML template index.html with the data in the context variable
    return render(
        request,
        'index.html',
        context={},
    )

def login(request):
    if request.method == "GET":
        context = {
            'error': False,
        }
        return render(request, 'registration/login.html', context=context)

    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(request, username=username, password=password)

    if user is not None:
        auth_login(request, user)
        return redirect(request.GET['next']
                        if request.GET['next'] else 'order')
    else:
        return render(request, 'registration/login.html',
                      context={'error': True})


@login_required
def order(request):
    list = Product.objects.all
    currency = helper.get_currency()

    context = {
        'list': list,
        'currency': currency,
    }
    return render(request, 'store/order.html', context=context)


def _addition_no_stock(request):
    cash, current_order, currency = helper.setup_handling(request)

    total_price = current_order.total_price
    list = Order_Item.objects.filter(order=current_order)
    context = {
        'list': list,
        'total_price': total_price,
        'cash': cash,
        'succesfully_payed': False,
        'payment_error': False,
        'amount_added': 0,
        'currency': currency,
        'stock_error': True,
    }
    return render(request, 'store/addition.html', context=context, status=400)


@login_required
def addition(request):
    cash, current_order, currency = helper.setup_handling(request)

    total_price = current_order.total_price
    list = Order_Item.objects.filter(order=current_order)
    context = {
        'list': list,
        'total_price': total_price,
        'cash': cash,
        'succesfully_payed': False,
        'payment_error': False,
        'amount_added': 0,
        'currency': currency,
        'stock-error': False,
    }
    return render(request, 'store/addition.html', context=context)


def _show_order(request, order_id, should_print):
    currency = helper.get_currency()
    order = get_object_or_404(Order, id=order_id)
    items = Order_Item.objects.filter(order=order)
    company = helper.get_company()

    context = {
        'list': items,
        'order': order,
        'currency': currency,
        'company': company,
        'print': should_print
    }

    return render(request, 'store/view_order.html', context=context)


@login_required
def view_order(request, order_id):
    return _show_order(request, order_id, False)


@login_required
def print_order(request, order_id):
    return _show_order(request, order_id, True)


@login_required
def print_current_order(request):
    # Get the user. This is quite a roundabout, sorry
    usr = User.objects.get_by_natural_key(request.user.username)
    q = Order.objects.filter(user=usr)\
                     .order_by('-last_change')

    # This is an edge case that would pretty much never occur
    if q.count() < 1:
        return HttpResponseBadRequest
    return _show_order(request, q[0].id, True)


@login_required
def order_add_product(request, product_id):
    cash, current_order, _ = helper.setup_handling(request)

    to_add = get_object_or_404(Product, id=product_id)

    # Make sure we can't go under 0 stock
    if to_add.stock_applies:
        if to_add.stock < 1:
            return _addition_no_stock(request)
        else:
            to_add.stock -= 1
            to_add.save()

    Order_Item.objects.create(order=current_order, product=to_add,
                              price=to_add.price, name=to_add.name)
    current_order.total_price = (
        decimal.Decimal(
            to_add.price) +
        current_order.total_price) \
        .quantize(decimal.Decimal('0.01'))
    current_order.save()

    return addition(request)


@login_required
def order_remove_product(request, product_id):
    cash, current_order, _ = helper.setup_handling(request)
    order_item = get_object_or_404(Order_Item, id=product_id)
    order_product = order_item.product

    if order_product.stock_applies:
        order_product.stock += 1
        order_product.save()

    current_order.total_price = (
        current_order.total_price -
        order_item.price).quantize(
            decimal.Decimal('0.01'))

    if current_order.total_price < 0:
        logging.error("prices below 0! "
                      "You might be running in to the "
                      "10 digit total order price limit")
        current_order.total_price = 0

    current_order.save()
    order_item.delete()

    # I only need default values.
    return addition(request)


@login_required
def reset_order(request):
    cash, current_order, _ = helper.setup_handling(request)

    for item in Order_Item.objects.filter(order=current_order):
        if item.product.stock_applies:
            item.product.stock += 1
            item.product.save()
        item.delete()

    current_order.total_price = 0
    current_order.save()

    # I just need default values. Quite useful
    return addition(request)


@login_required
def payment_cash(request):
    succesfully_payed = False
    payment_error = False
    amount_added = 0
    cash, current_order, currency = helper.setup_handling(request)

    for product in helper.product_list_from_order(current_order):
        cash.amount += product.price
        amount_added += product.price
        cash.save()

    current_order.done = True
    current_order.save()
    current_order = Order.objects.create(user=request.user)
    succesfully_payed = True

    total_price = current_order.total_price
    list = Order_Item.objects.filter(order=current_order)
    context = {
        'list': list,
        'total_price': total_price,
        'cash': cash,
        'succesfully_payed': succesfully_payed,
        'payment_error': payment_error,
        'amount_added': amount_added,
        'currency': currency,
    }
    return render(request, 'store/addition.html', context=context)


@login_required
def payment_credit(request):
    succesfully_payed = False
    payment_error = False
    cash, current_order, currency = helper.setup_handling(request)

    for product in helper.product_list_from_order(current_order):
        current_order.done = True
        current_order.save()
        current_order = Order.objects.create(user=request.user)
        succesfully_payed = True

    total_price = current_order.total_price
    list = Order_Item.objects.filter(order=current_order)
    context = {
        'list': list,
        'total_price': total_price,
        'cash': cash,
        'succesfully_payed': succesfully_payed,
        'payment_error': payment_error,
        'amount_added': 0,
        'currency': currency,
    }
    return render(request, 'store/addition.html', context=context)


# We can't use the `@login_required` decorator here because this
# page is never shown to the user and only used in AJAX requests
def cash(request, amount):
    if (request.user.is_authenticated):
        cash, _ = Cash.objects.get_or_create(id=0)
        cash.amount = amount
        cash.save()
        return HttpResponse('')
    else:
        return HttpResponseForbidden('403 Forbidden')


@login_required
def view_stock(request):
    stock_products = Product.objects.filter(stock_applies=True)
    company = helper.get_company()

    context = {
        'list': stock_products,
        'company': company
    }

    return render(request, 'store/stock.html', context=context)

class ProductModelForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProductModelForm, self).__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
    class Meta:
        model = Product
        exclude = ('stock_applies',)

    
class PurchaseModelForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(PurchaseModelForm, self).__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
    class Meta:
        model = Purchase
        fields = '__all__'

class ProductCreate(CreateView):
    model = Product
    fields = ['name']
    success_url = reverse_lazy('purchase_create')
    


class ProductUpdate(UpdateView):
    form_class = ProductModelForm
    model = Product
    success_url = reverse_lazy('view_stock')
    
    


class PurchaseCreate(CreateView):
    model = Purchase
    form_class = PurchaseModelForm
    success_url = reverse_lazy('purchase_create')


class PurchaseUpdate(CreateView):
    model = Purchase
    form_class = PurchaseModelForm

class PurchaseListView(generic.ListView):
    model = Purchase
    paginate_by = 10


class PurchaseDetailView(generic.DetailView):
    model = Purchase


@login_required
def report(request):
    cash, current_order, currency = helper.setup_handling(request)

    # Generate counts of some of the main objects
    num_orders=Order.objects.all().count()
    num_product=Product.objects.all().count()
    num_purchases=Product.objects.all().count()
    num_product_finished =Product.objects.filter(stock__exact=0).count()
    cash_register = Cash.objects.values_list('amount', flat=True).first()
    
    num_orders = int(num_orders) - 1
    
    # Render the HTML template index.html with the data in the context variable.
    return render(
        request,
        'store/report.html',
        context={'num_orders':num_orders,'num_product':num_product,'num_purchases':num_purchases,
        'num_product_finished':num_product_finished,'cash_register':cash_register,},
    ) # num_visits appended