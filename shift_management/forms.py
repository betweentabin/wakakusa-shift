from django import forms
from django.contrib.auth.models import User
from .models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail

# 時間選択肢を生成するヘルパー関数
def get_time_choices(interval_minutes=30):
    choices = []
    # 00:00 から 23:59 まで指定された間隔で選択肢を生成
    for hour in range(24):
        for minute in range(0, 60, interval_minutes):
            time_val = f"{hour:02d}:{minute:02d}"
            choices.append((time_val, time_val))
    return choices

TIME_CHOICES = get_time_choices(30) # 30分刻みの選択肢

class StaffForm(forms.ModelForm):
    # ユーザーアカウント作成用フィールド
    create_user_account = forms.BooleanField(
        label='ログインアカウントを作成',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='チェックすると、このスタッフ用のログインアカウントが作成されます'
    )
    username = forms.CharField(
        label='ユーザー名',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ログイン時に使用するユーザー名'}),
        help_text='半角英数字、@/./+/-/_ のみ使用可能'
    )
    password = forms.CharField(
        label='パスワード',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '8文字以上のパスワード'}),
        help_text='8文字以上で設定してください'
    )
    password_confirm = forms.CharField(
        label='パスワード（確認）',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'パスワードを再入力'}),
        help_text='確認のため同じパスワードを入力してください'
    )

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 編集時はユーザー名を初期値として設定
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['create_user_account'].initial = True

    def clean_username(self):
        username = self.cleaned_data.get('username')
        create_user_account = self.cleaned_data.get('create_user_account')
        
        if create_user_account and not username:
            raise forms.ValidationError('ログインアカウントを作成する場合、ユーザー名は必須です。')
        
        if username:
            # 既存ユーザーとの重複チェック（編集時は自分を除く）
            existing_user = User.objects.filter(username=username).first()
            if existing_user:
                if not self.instance.pk or not self.instance.user or existing_user != self.instance.user:
                    raise forms.ValidationError('このユーザー名は既に使用されています。')
        
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        create_user_account = self.cleaned_data.get('create_user_account')
        
        if create_user_account and not password and not self.instance.pk:
            raise forms.ValidationError('ログインアカウントを作成する場合、パスワードは必須です。')
        
        if password and len(password) < 8:
            raise forms.ValidationError('パスワードは8文字以上で設定してください。')
        
        return password

    def clean(self):
        cleaned_data = super().clean()
        create_user_account = cleaned_data.get('create_user_account')
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if create_user_account and password and password != password_confirm:
            raise forms.ValidationError('パスワードが一致しません。')
        
        return cleaned_data

    def save(self, commit=True):
        staff = super().save(commit=False)
        
        if commit:
            staff.save()
            
            # ユーザーアカウント作成処理
            create_user_account = self.cleaned_data.get('create_user_account')
            username = self.cleaned_data.get('username')
            password = self.cleaned_data.get('password')
            
            if create_user_account and username:
                if staff.user:
                    # 既存ユーザーの更新
                    user = staff.user
                    user.username = username
                    if password:
                        user.set_password(password)
                    user.save()
                else:
                    # 新規ユーザー作成
                    if password:
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            email=staff.email or '',
                            first_name=staff.name.split()[0] if staff.name else '',
                            last_name=' '.join(staff.name.split()[1:]) if staff.name and len(staff.name.split()) > 1 else ''
                        )
                        staff.user = user
                        staff.save()
            elif not create_user_account and staff.user:
                # ユーザーアカウントの削除
                user = staff.user
                staff.user = None
                staff.save()
                user.delete()
        
        return staff

class ShiftTypeForm(forms.ModelForm):
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='デフォルト開始時間'
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='デフォルト終了時間'
    )

    class Meta:
        model = ShiftType
        fields = ['name', 'color', 'start_time', 'end_time', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_start_time(self):
        """開始時間のバリデーションと変換"""
        start_time_str = self.cleaned_data.get('start_time')
        if not start_time_str:
            return None
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。')
        return time_obj

    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time_str = self.cleaned_data.get('end_time')
        if not end_time_str:
            return None
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。')
        return time_obj

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        return cleaned_data

class ShiftForm(forms.ModelForm):
    # 明示的にフィールドを定義して必須属性を制御
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    
    class Meta:
        model = Shift
        fields = ['staff', 'shift_type', 'date', 'start_time', 'end_time', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'shift_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shift_type'].required = False

class ShiftReasonForm(forms.ModelForm):
    """事由登録フォーム（公休、有給等）"""
    class Meta:
        model = Shift
        fields = ['staff', 'date', 'deletion_reason', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'deletion_reason': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '備考があれば入力してください'}),
        }
        labels = {
            'staff': 'スタッフ',
            'date': '日付',
            'deletion_reason': '事由',
            'notes': '備考',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deletion_reason'].required = True
        self.fields['deletion_reason'].empty_label = "選択してください"

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # 同じスタッフ・同じ日付の既存シフトを削除
        if commit:
            # 既存の通常シフト（事由なし）を削除
            Shift.objects.filter(
                staff=instance.staff,
                date=instance.date,
                is_deleted_with_reason=False
            ).delete()
            
            # 既存の事由付きシフトも削除（重複防止）
            Shift.objects.filter(
                staff=instance.staff,
                date=instance.date,
                is_deleted_with_reason=True
            ).delete()
        
        # 事由登録の場合は特別な値を設定
        instance.is_deleted_with_reason = True
        instance.shift_type = None  # シフト種別は不要
        instance.start_time = None  # 開始時間は不要
        instance.end_time = None    # 終了時間は不要
        
        if commit:
            instance.save()
        return instance
    
    def clean_start_time(self):
        """開始時間のバリデーションと変換"""
        start_time_str = self.cleaned_data.get('start_time')
        if not start_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', start_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 09:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time_str = self.cleaned_data.get('end_time')
        if not end_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', end_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 17:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        shift_type = cleaned_data.get('shift_type')
        
        # 通常のシフトの場合は時間が必須
        if shift_type and (not start_time or not end_time):
            raise forms.ValidationError('シフト種別が選択されている場合、開始時間と終了時間は必須です。')
        
        # 時間フィールドのバリデーション
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        return cleaned_data

# 複数シフト一括登録フォーム（新規追加）
class BulkShiftForm(forms.Form):
    """複数シフトを一括登録するためのフォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    staff = forms.ModelMultipleChoiceField(
        label='スタッフ（複数選択可）',
        queryset=Staff.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'})
    )
    shift_type = forms.ModelChoiceField(
        label='シフト種別',
        queryset=ShiftType.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    weekdays = forms.MultipleChoiceField(
        label='適用する曜日（複数選択可）',
        choices=[
            (0, '月曜日'),
            (1, '火曜日'),
            (2, '水曜日'),
            (3, '木曜日'),
            (4, '金曜日'),
            (5, '土曜日'),
            (6, '日曜日'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )
    start_time = forms.ChoiceField(
        label='開始時間',
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    end_time = forms.ChoiceField(
        label='終了時間',
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    overwrite = forms.BooleanField(
        label='既存のシフトを上書きする',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean_start_time(self):
        """開始時間のバリデーションと変換"""
        start_time_str = self.cleaned_data.get('start_time')
        if not start_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', start_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 09:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time_str = self.cleaned_data.get('end_time')
        if not end_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', end_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 17:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        weekdays = cleaned_data.get('weekdays')
        
        # 時間フィールドのバリデーション
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        # 日付範囲のバリデーション
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('終了日は開始日より後である必要があります。')
        
        # 曜日が選択されているか確認
        if not weekdays:
            raise forms.ValidationError('少なくとも1つの曜日を選択してください。')
        
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
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
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
        start_time_str = self.cleaned_data.get('start_time')
        if not start_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', start_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 09:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(start_time_str)
        if not time_obj:
            raise forms.ValidationError('無効な時間形式です。「HH:MM」形式で入力してください')
        
        return time_obj
    
    def clean_end_time(self):
        """終了時間のバリデーションと変換"""
        end_time_str = self.cleaned_data.get('end_time')
        if not end_time_str:
            return None
        
        # HH:MM形式のバリデーションはChoiceFieldにより不要に
        # import re
        # if not re.match(r'^\\d{1,2}:\\d{2}$', end_time):
        #     raise forms.ValidationError('時間は「HH:MM」形式で入力してください（例: 17:00）')
        
        # Djangoのtimeフィールド用に変換
        from django.utils.dateparse import parse_time
        time_obj = parse_time(end_time_str)
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

# シフト印刷・エクスポート用フォーム（新規追加）
class ShiftExportForm(forms.Form):
    """シフト表の印刷・エクスポート用フォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    staff = forms.ModelMultipleChoiceField(
        label='スタッフ（複数選択可、未選択の場合は全員）',
        queryset=Staff.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'})
    )
    format_type = forms.ChoiceField(
        label='出力形式',
        choices=[
            ('pdf', 'PDF'),
            ('csv', 'CSV'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # 日付範囲のバリデーション
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('終了日は開始日より後である必要があります。')
        
        return cleaned_data
