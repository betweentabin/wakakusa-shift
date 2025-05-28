from django import forms
from .models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail

class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['name', 'phone', 'email', 'position', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ShiftTypeForm(forms.ModelForm):
    class Meta:
        model = ShiftType
        fields = ['name', 'color', 'start_time', 'end_time', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'start_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09:00'}),
            'end_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '17:00'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ShiftForm(forms.ModelForm):
    # 明示的にフィールドを定義して必須属性を制御
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    start_time = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09:00'})
    )
    end_time = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '17:00'})
    )
    
    class Meta:
        model = Shift
        fields = ['staff', 'shift_type', 'date', 'start_time', 'end_time', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'shift_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_start_time(self):
        """開始時間のバリデーションと変換"""
        start_time = self.cleaned_data.get('start_time')
        if not start_time:
            return None
        
        # HH:MM形式のバリデーション
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', start_time):
            raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 09:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time = self.cleaned_data.get('end_time')
        if not end_time:
            return None
        
        # HH:MM形式のバリデーション
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', end_time):
            raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 17:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        # 時間フィールドのバリデーション
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        return cleaned_data

class ShiftTemplateForm(forms.ModelForm):
    class Meta:
        model = ShiftTemplate
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ShiftTemplateDetailForm(forms.ModelForm):
    # 明示的にフィールドを定義して必須属性を制御
    start_time = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09:00'})
    )
    end_time = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '17:00'})
    )
    
    class Meta:
        model = ShiftTemplateDetail
        fields = ['staff', 'shift_type', 'weekday', 'start_time', 'end_time']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'shift_type': forms.Select(attrs={'class': 'form-select'}),
            'weekday': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_start_time(self):
        """開始時間のバリデーションと変換"""
        start_time = self.cleaned_data.get('start_time')
        if not start_time:
            return None
        
        # HH:MM形式のバリデーション
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', start_time):
            raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 09:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time = self.cleaned_data.get('end_time')
        if not end_time:
            return None
        
        # HH:MM形式のバリデーション
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', end_time):
            raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 17:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        # 時間フィールドのバリデーション
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        return cleaned_data

class DateRangeForm(forms.Form):
    """シフトカレンダーの表示期間を選択するフォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

class TemplateApplyForm(forms.Form):
    """テンプレートを適用する期間を選択するフォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    overwrite = forms.BooleanField(
        label='既存のシフトを上書きする',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    ) 