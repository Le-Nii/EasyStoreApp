from django import forms

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
import datetime #for checking renewal date range.
    
class CustomReportForm(forms.Form):
    min_date = forms.DateField(widget=forms.TextInput(attrs={'required': False, 'class': 'form-control', 'placeholder':'YYYY-MM-DD'}))
    max_date = forms.DateField(widget=forms.TextInput(attrs={'required': False ,'class': 'form-control', 'placeholder':'YYYY-MM-DD'}))

    def clean_renewal_date(self):
        data1 = self.cleaned_data['max_data']
        data2 = self.cleaned_data['min_date']
        
        #Check  min date is greater than max date

        if data1 < data2:
            raise ValidationError(_('Invalid date - min date is greater than max date'))
        data = [data1, data2]
        # Remember to always return the cleaned data.
        return data