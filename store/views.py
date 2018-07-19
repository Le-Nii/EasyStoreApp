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
from .models import Product, Order, Cash, Order_Item, Purchase, OtherPurchase
from django.views.generic.edit import CreateView, UpdateView
from django.forms import ModelForm
from django.views import generic
from django.urls import reverse
from django.urls import reverse_lazy
import datetime
from django.utils import timezone
from . import helper
from .forms import CustomReportForm

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

def resert(request):
    """
    View function for resertCah page of site.
    """
    
    # Render the HTML template index.html with the data in the context variable
    return render(
        request,
        'store/resert.html',
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
    # if to_add.stock_applies:
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

    # calculating profit
    profit = decimal.Decimal(to_add.price) - decimal.Decimal(to_add.cost_price)
    current_order.profit =(
        profit + current_order.profit) \
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

class OtherPurchaseModelForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(OtherPurchaseModelForm, self).__init__(*args, **kwargs)
        for field in iter(self.fields):
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })
    class Meta:
        model = OtherPurchase
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

class OtherPurchaseCreate(CreateView):
    model = OtherPurchase
    form_class = OtherPurchaseModelForm
    success_url = reverse_lazy('otherpurchase_create')


class OtherPurchaseUpdate(CreateView):
    model = OtherPurchase
    form_class = OtherPurchaseModelForm
    success_url = reverse_lazy('otherpurchases')

class OtherPurchaseListView(generic.ListView):
    model = OtherPurchase
    paginate_by = 10


def num_ordered(num_orders):
    num_orders = int(num_orders) - 1
    if num_orders ==-1:
        num_orders =0
    return num_orders

def profit(prof):
    total_profit =0.00
    for i in prof:
        total_profit = total_profit + float(i)
    return total_profit

def sales(orders_sales):
    total_sales =0.00
    for i in orders_sales:
        total_sales = total_sales + float(i)
    return total_sales

def purchases(purchase_cost):
    t_purchases =0.00
    for i in purchase_cost:
        t_purchases = t_purchases + float(i)
    return t_purchases

def other_purchases(other_purchases_cost):
    t_other_purchases =0.00
    for i in other_purchases_cost :
        t_other_purchases = t_other_purchases + float(i)
    return t_other_purchases


@login_required
def report(request):
    cash, current_order, currency = helper.setup_handling(request)

    # Generate counts of some of the main objects
    num_orders = Order.objects.all().count()
    orders_sales = Order.objects.values_list('total_price', flat=True).all()
    profit_on_sales = Order.objects.values_list('profit', flat=True).all()
    num_product = Product.objects.all().count()
    num_purchases= Purchase.objects.all().count()
    purchase_cost= Purchase.objects.values_list('cost_price', flat=True).all()
    num_other_purchases = OtherPurchase.objects.all().count()
    other_purchases_cost = OtherPurchase.objects.values_list('cost_price', flat=True).all()
    num_product_finished = Product.objects.filter(stock__exact=0).count()
    cash_register = Cash.objects.values_list('amount', flat=True).first()
    cash_register = "{:0.2f}\n".format(cash_register)


    # Generate Report
    total_num_purchases = int(num_purchases) + int(num_other_purchases)
    num_orders = num_ordered(num_orders)

    t_sales = sales(orders_sales)
    t_purchases = purchases(purchase_cost)
    t_other_purchases = other_purchases(other_purchases_cost)

    total_purchases_amount = t_other_purchases + t_purchases
        
    total_returns = t_sales - total_purchases_amount

    # Daily Report
    today_min = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    today_max = datetime.datetime.combine(datetime.date.today(), datetime.time.max)
    num_daily_orders = Order.objects.filter(last_change__range=(today_min, today_max)).count()
    num_daily_purchases= Purchase.objects.filter(timestamp__range=(today_min, today_max)).count()
    num_daily_other_purchases = OtherPurchase.objects.filter(timestamp__range=(today_min, today_max)).count()
    daily_other_purchases_cost = OtherPurchase.objects.values_list('cost_price', flat=True).filter(timestamp__range=(today_min, today_max)) 
    daily_purchase_cost = Purchase.objects.values_list('cost_price', flat=True).filter(timestamp__range=(today_min, today_max)) 
    daily_orders_sales = Order.objects.values_list('total_price', flat=True).filter(last_change__range=(today_min, today_max)) 
    daily_profit_on_sales = Order.objects.values_list('profit', flat=True).filter(last_change__range=(today_min, today_max)) 
    

    daily_total_sales = sales(daily_orders_sales)
    daily_total_purchases = purchases(daily_purchase_cost)
    daily_total_other_purchases = other_purchases(daily_other_purchases_cost)

    dtotal_purchases_amount = daily_total_other_purchases + daily_total_purchases        
    daily_total_returns = daily_total_sales - dtotal_purchases_amount
    daily_total_purchases_amount = daily_total_other_purchases + daily_total_purchases
    num_daily_orders = num_ordered(num_daily_orders)

    #Weakly Report
    year = today_min.year
    week=today_min.isocalendar()[1]

    num_weekly_orders = Order.objects.filter(last_change__week = week,last_change__year = year).count()
    num_weekly_purchases= Purchase.objects.filter(timestamp__week = week,timestamp__year = year).count()
    num_weekly_other_purchases = OtherPurchase.objects.filter(timestamp__week = week,timestamp__year = year).count()
    weekly_other_purchases_cost = OtherPurchase.objects.values_list('cost_price', flat=True).filter(timestamp__week = week,timestamp__year = year)
    weekly_purchase_cost = Purchase.objects.values_list('cost_price', flat=True).filter(timestamp__week = week,timestamp__year = year)
    weekly_orders_sales = Order.objects.values_list('total_price', flat=True).filter(last_change__week = week,last_change__year = year)
    weekly_profit_on_sales = Order.objects.values_list('profit', flat=True).filter(last_change__week = week,last_change__year = year)

    weekly_total_sales = sales(weekly_orders_sales)
    weekly_total_purchases = purchases(weekly_purchase_cost)
    weekly_total_other_purchases = other_purchases(weekly_other_purchases_cost)

    wtotal_purchases_amount = weekly_total_other_purchases + weekly_total_purchases        
    weekly_total_returns = weekly_total_sales - wtotal_purchases_amount
    weekly_total_purchases_amount = weekly_total_other_purchases + weekly_total_purchases
    num_weekly_orders = num_ordered(num_weekly_orders)
    

    #Monthly Report
    month=today_min.month

    num_monthly_orders = Order.objects.filter(last_change__month = month,last_change__year = year).count()
    num_monthly_purchases= Purchase.objects.filter(timestamp__month = month,timestamp__year = year).count()
    num_monthly_other_purchases = OtherPurchase.objects.filter(timestamp__month = month,timestamp__year = year).count()
    monthly_other_purchases_cost = OtherPurchase.objects.values_list('cost_price', flat=True).filter(timestamp__month = month,timestamp__year = year)
    monthly_purchase_cost = Purchase.objects.values_list('cost_price', flat=True).filter(timestamp__month = month,timestamp__year = year)
    monthly_orders_sales = Order.objects.values_list('total_price', flat=True).filter(last_change__month = month,last_change__year = year)
    monthly_profit_on_sales = Order.objects.values_list('total_price', flat=True).filter(last_change__month = month,last_change__year = year)

    monthly_total_sales = sales(monthly_orders_sales)
    monthly_total_purchases = purchases(monthly_purchase_cost)
    monthly_total_other_purchases = other_purchases(monthly_other_purchases_cost)

    mtotal_purchases_amount = monthly_total_other_purchases + monthly_total_purchases        
    monthly_total_returns = monthly_total_sales - mtotal_purchases_amount
    monthly_total_purchases_amount = monthly_total_other_purchases + monthly_total_purchases
    num_monthly_orders = num_ordered(num_monthly_orders)

    # profit
    profit_on_sales = profit(profit_on_sales)
    daily_profit_on_sales = profit(daily_profit_on_sales)
    weekly_profit_on_sales = profit(weekly_profit_on_sales)
    monthly_profit_on_sales = profit(monthly_profit_on_sales)
    
    
    # Render the HTML template report.html with the data in the context variable.
    return render(
        request,
        'store/report.html',
        context={'num_orders':num_orders,'num_product':num_product,'num_purchases':num_purchases,
        'num_product_finished':num_product_finished,'cash_register':cash_register, 'total_returns':total_returns,
        'currency':currency, 't_sales':t_sales, 't_purchases':t_purchases, 't_other_purchases':t_other_purchases,
        'total_purchases_amount':total_purchases_amount, 'dtotal_purchases_amount':dtotal_purchases_amount,
        'num_other_purchases':num_other_purchases,'total_num_purchases':total_num_purchases,'t_sales':t_sales,
        'daily_total_sales':daily_total_sales, 'daily_total_purchases':daily_total_purchases, 
        'daily_total_other_purchases':daily_total_other_purchases,
        'daily_total_returns':daily_total_returns,'num_daily_orders':num_daily_orders, 'num_daily_purchases':num_daily_purchases, 
        'num_daily_other_purchases':num_daily_other_purchases, 'daily_total_purchases_amount':daily_total_purchases_amount,
        'weekly_total_sales':weekly_total_sales, 'weekly_total_purchases':weekly_total_purchases, 
        'weekly_total_other_purchases':weekly_total_other_purchases,
        'weekly_total_returns':weekly_total_returns,'num_weekly_orders':num_weekly_orders, 'num_weekly_purchases':num_weekly_purchases, 
        'num_weekly_other_purchases':num_weekly_other_purchases, 'weekly_total_purchases_amount':weekly_total_purchases_amount,
        'wtotal_purchases_amount':wtotal_purchases_amount,
        'monthly_total_sales':monthly_total_sales, 'monthly_total_sales':monthly_total_sales, 'monthly_total_purchases':monthly_total_purchases, 
        'monthly_total_other_purchases':monthly_total_other_purchases,
        'monthly_total_returns':monthly_total_returns,'num_monthly_orders':num_monthly_orders, 'num_monthly_purchases':num_monthly_purchases, 
        'num_monthly_other_purchases':num_monthly_other_purchases, 'monthly_total_purchases_amount':monthly_total_purchases_amount,
        'mtotal_purchases_amount':mtotal_purchases_amount, 'profit_on_sales':profit_on_sales, 'daily_profit_on_sales':daily_profit_on_sales,
        'weekly_profit_on_sales':weekly_profit_on_sales, 'monthly_profit_on_sales':monthly_profit_on_sales,
        },
    ) # num_visits appended

def custom_report(request):
    """
    View function for Custom Report
    """

    # If this is a POST request then process the Form data
    if request.method == 'POST':

        # Create a form instance and populate it with data from the request (binding):
        form = CustomReportForm(request.POST)

        # Check if the form is valid:
        if form.is_valid():
            # process the data in form.cleaned_data
            min_date = form.cleaned_data['min_date']
            max_date = form.cleaned_data['max_date']

            today_min = datetime.datetime.combine(min_date, datetime.time.min)
            today_max = datetime.datetime.combine(max_date, datetime.time.max)

            num_orders = Order.objects.filter(last_change__range=(today_min, today_max)).count()
            num_purchases= Purchase.objects.filter(timestamp__range=(today_min, today_max)).count()
            num_other_purchases = OtherPurchase.objects.filter(timestamp__range=(today_min, today_max)).count()
            other_purchases_cost = OtherPurchase.objects.values_list('cost_price', flat=True).filter(timestamp__range=(today_min, today_max)) 
            purchase_cost = Purchase.objects.values_list('cost_price', flat=True).filter(timestamp__range=(today_min, today_max)) 
            orders_sales = Order.objects.values_list('total_price', flat=True).filter(last_change__range=(today_min, today_max))
            profit_on_sales = Order.objects.values_list('profit', flat=True).filter(last_change__range=(today_min, today_max))

            total_sales = sales(orders_sales)
            total_purchases = purchases(purchase_cost)
            total_other_purchases = other_purchases(other_purchases_cost)

            total_purchases_amount = total_other_purchases + total_purchases        
            total_returns = total_sales - total_purchases_amount
            total_purchases_amount = total_other_purchases + total_purchases
            num_orders = num_ordered(num_orders)

            profit_on_sales = profit(profit_on_sales)

            message1 = "Report between {0} and {1}".format(max_date, min_date)

            return render(
            request, 'store/custom_report.html',
            context={
                'total_sales':total_sales, 'total_purchases':total_purchases, 
                'total_other_purchases':total_other_purchases,
                'total_returns':total_returns,'num_orders':num_orders, 'num_purchases':num_purchases, 
                'num_other_purchases':num_other_purchases, 'total_purchases_amount':total_purchases_amount,
                'total_purchases_amount':total_purchases_amount, 'message1':message1, 'profit_on_sales':profit_on_sales,
            })

    # If this is a GET (or any other method) create the default form.
    else:
        initial_min = datetime.date.today() - datetime.timedelta(weeks=4)
        initial_max = datetime.date.today()
        form = CustomReportForm(initial={'min_date':initial_min, 'max_date': initial_max})

    return render(request, 'store/custom_report.html', {'form': form})