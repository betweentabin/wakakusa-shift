from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    Staff, Shift, ShiftType, Organization, ShiftTemplate, ShiftTemplateDetail,
    LeaveRequest, ShiftProposal, StaffCompatibility, Holiday, Event, EventParticipant,
    Item, Inventory, Transaction, Order, Invoice, InvoiceItem, DeliveryNote, DeliveryNoteItem
)

# 時間選択のための選択肢を生成（10分刻み）
TIME_CHOICES = []
for hour in range(24):
    for minute in range(0, 60, 10):  # 10分刻み
        time_str = f"{hour:02d}:{minute:02d}"
        TIME_CHOICES.append((time_str, time_str))

class StaffRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        
        # Organization フィールドを追加
        self.fields['organization'] = forms.ModelChoiceField(
            queryset=Organization.objects.all(),
            label='所属組織',
            required=True,
            widget=forms.Select(attrs={'class': 'form-control'})
        )
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Staff オブジェクトの作成
            organization = self.cleaned_data.get('organization')
            Staff.objects.create(
                user=user,
                email=user.email,
                organization=organization
            )
        return user

class StaffLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ユーザー名'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'パスワード'})
    )

class ShiftForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='日付'
    )
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='開始時間'
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='終了時間'
    )
    
    class Meta:
        model = Shift
        fields = ['staff', 'shift_type', 'date', 'start_time', 'end_time', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'shift_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'staff': 'スタッフ',
            'shift_type': 'シフト種別',
            'notes': '備考',
        }
    
    def __init__(self, *args, **kwargs):
        # 組織情報を受け取る
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に基づいてスタッフをフィルタリング
        if organization:
            self.fields['staff'].queryset = Staff.objects.filter(
                organization=organization,
                approval_status='approved',
                is_active=True
            ).order_by('name')
        else:
            # 組織が指定されていない場合は承認済みのアクティブなスタッフのみ
            self.fields['staff'].queryset = Staff.objects.filter(
                approval_status='approved',
                is_active=True
            ).order_by('name')

class StaffShiftForm(forms.ModelForm):
    """スタッフ用のシフト申請フォーム"""
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='日付'
    )
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='開始時間'
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label='終了時間'
    )
    
    class Meta:
        model = Shift
        fields = ['shift_type', 'date', 'start_time', 'end_time', 'notes']
        widgets = {
            'shift_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'shift_type': 'シフト種別',
            'notes': '備考',
        }

class BulkShiftForm(forms.Form):
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    staff = forms.ModelMultipleChoiceField(
        label='スタッフ（複数選択可）',
        queryset=Staff.objects.none(),  # 初期化時は空、__init__で設定
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, *args, **kwargs):
        # 組織情報を受け取る
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に基づいてスタッフをフィルタリング
        if organization:
            self.fields['staff'].queryset = Staff.objects.filter(
                organization=organization,
                approval_status='approved',
                is_active=True
            ).order_by('name')
        else:
            # 組織が指定されていない場合は承認済みのアクティブなスタッフのみ
            self.fields['staff'].queryset = Staff.objects.filter(
                approval_status='approved',
                is_active=True
            ).order_by('name')
    shift_type = forms.ModelChoiceField(
        label='シフト種別',
        queryset=ShiftType.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'shift-type-select'
        }),
        required=False
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
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input weekday-checkbox'
        }),
        initial=[0, 1, 2, 3, 4]  # 平日をデフォルトで選択
    )
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'start-time-select'
        }),
        required=False,
        label='開始時間'
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'end-time-select'
        }),
        required=False,
        label='終了時間'
    )
    overwrite = forms.BooleanField(
        label='既存のシフトを上書きする',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

class AdvancedBulkShiftForm(forms.Form):
    """日ごとに異なる時間帯を設定できる高度な一括登録フォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'advanced-start-date'
        })
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'advanced-end-date'
        })
    )
    staff = forms.ModelMultipleChoiceField(
        label='スタッフ（複数選択可）',
        queryset=Staff.objects.filter(approval_status='approved'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    shift_type = forms.ModelChoiceField(
        label='シフト種別（デフォルト）',
        queryset=ShiftType.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'default-shift-type'
        }),
        required=False
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
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input weekday-checkbox'
        }),
        initial=[0, 1, 2, 3, 4]  # 平日をデフォルトで選択
    )
    time_settings = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    overwrite = forms.BooleanField(
        label='既存のシフトを上書きする',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'address', 'contact_phone', 'contact_email', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'name': '組織名',
            'address': '住所',
            'contact_phone': '電話番号',
            'contact_email': 'メールアドレス',
            'description': '説明',
        }

class OrganizationSelectForm(forms.Form):
    organization = forms.ModelChoiceField(
        label='組織を選択',
        queryset=Organization.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        empty_label='-- 組織を選択してください --'
    )

class OrganizationAdminLoginForm(forms.Form):
    organization_code = forms.CharField(
        label='組織コード',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '組織コードを入力'
        })
    )
    password = forms.CharField(
        label='パスワード',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'パスワードを入力'
        })
    )

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
        fields = ['name', 'phone', 'email', 'position', 'role_type', 'organization', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'role_type': forms.Select(attrs={'class': 'form-select'}),
            'organization': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 編集時はユーザー名を初期値として設定
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['create_user_account'].initial = True
        
        # role_typeフィールドを必須にし、デフォルト値を設定
        self.fields['role_type'].required = True
        if not self.instance.pk:  # 新規作成時のみ
            self.fields['role_type'].initial = 'user'

    def clean_username(self):
        username = self.cleaned_data.get('username')
        create_user_account = self.cleaned_data.get('create_user_account')
        
        if create_user_account and not username:
            raise forms.ValidationError('ログインアカウントを作成する場合、ユーザー名は必須です。')
        
        if username:
            # 既存ユーザーとの重複チェック（編集時は自分を除く）
            from django.contrib.auth.models import User
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
                from django.contrib.auth.models import User
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
        queryset=Staff.objects.filter(is_active=True, approval_status='approved'),
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

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        if organization:
            self.fields['staff'].queryset = Staff.objects.filter(
                organization=organization,
                is_active=True,
                approval_status='approved'
            )
            self.fields['shift_type'].queryset = ShiftType.objects.filter(
                organization=organization
            )

class CalendarBulkShiftForm(forms.Form):
    """カレンダー上での一括シフト登録フォーム"""
    selected_dates = forms.CharField(
        widget=forms.HiddenInput(),
        label='選択日'
    )
    staff = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='スタッフ選択'
    )
    shift_type = forms.ModelChoiceField(
        queryset=ShiftType.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='シフト種別',
        empty_label='シフト種別を選択'
    )
    time_input_type = forms.ChoiceField(
        label='時間入力方法',
        choices=[
            ('preset', '定型選択（10分刻み）'),
            ('custom', '自由記述')
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='preset'
    )
    start_time = forms.ChoiceField(
        label='開始時間（定型選択）',
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    end_time = forms.ChoiceField(
        label='終了時間（定型選択）',
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    custom_start_time = forms.CharField(
        label='開始時間（自由記述）',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 09:15, 14:45'
        }),
        required=False,
        help_text='HH:MM形式で入力してください'
    )
    custom_end_time = forms.CharField(
        label='終了時間（自由記述）',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '例: 17:30, 22:15'
        }),
        required=False,
        help_text='HH:MM形式で入力してください'
    )
    overwrite = forms.BooleanField(
        label='既存のシフトを上書きする',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    individual_times = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        label='個別時間データ'
    )


    def clean_selected_dates(self):
        """選択された日付文字列をパースして日付リストに変換"""
        import json
        from datetime import datetime
        
        selected_dates_str = self.cleaned_data.get('selected_dates', '')
        if not selected_dates_str:
            raise forms.ValidationError('日付を選択してください。')
        
        try:
            date_strings = json.loads(selected_dates_str)
            dates = []
            for date_str in date_strings:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    dates.append(date_obj)
                except ValueError:
                    raise forms.ValidationError(f'無効な日付形式です: {date_str}')
            return dates
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError('日付データの形式が正しくありません。')
    
    def clean_custom_start_time(self):
        """カスタム開始時間のバリデーション"""
        import re
        time_str = self.cleaned_data.get('custom_start_time', '').strip()
        if not time_str:
            return time_str
        
        # HH:MM形式のチェック
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', time_str):
            raise forms.ValidationError('時間はHH:MM形式（例: 09:15）で入力してください。')
        
        return time_str
    
    def clean_custom_end_time(self):
        """カスタム終了時間のバリデーション"""
        import re
        time_str = self.cleaned_data.get('custom_end_time', '').strip()
        if not time_str:
            return time_str
        
        # HH:MM形式のチェック
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', time_str):
            raise forms.ValidationError('時間はHH:MM形式（例: 17:30）で入力してください。')
        
        return time_str
    
    def clean(self):
        """フォーム全体のバリデーション"""
        cleaned_data = super().clean()
        time_input_type = cleaned_data.get('time_input_type')
        
        if time_input_type == 'preset':
            start_time = cleaned_data.get('start_time')
            end_time = cleaned_data.get('end_time')
            if not start_time or not end_time:
                raise forms.ValidationError('定型選択の場合は開始時間と終了時間を選択してください。')
        elif time_input_type == 'custom':
            custom_start_time = cleaned_data.get('custom_start_time')
            custom_end_time = cleaned_data.get('custom_end_time')
            if not custom_start_time or not custom_end_time:
                raise forms.ValidationError('自由記述の場合は開始時間と終了時間を入力してください。')
        
        return cleaned_data

class ShiftTypeForm(forms.ModelForm):
    class Meta:
        model = ShiftType
        fields = ['name', 'start_time', 'end_time', 'color', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'シフト種別名',
            'start_time': '開始時間',
            'end_time': '終了時間',
            'color': '色',
            'description': '説明',
        }

class ShiftTemplateForm(forms.ModelForm):
    class Meta:
        model = ShiftTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'テンプレート名',
            'description': '説明',
        }

class ShiftTemplateDetailForm(forms.ModelForm):
    class Meta:
        model = ShiftTemplateDetail
        fields = ['staff', 'shift_type', 'weekday', 'start_time', 'end_time']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'shift_type': forms.Select(attrs={'class': 'form-control'}),
            'weekday': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
        labels = {
            'staff': 'スタッフ',
            'shift_type': 'シフト種別',
            'weekday': '曜日',
            'start_time': '開始時間',
            'end_time': '終了時間',
        }

class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

class TemplateApplyForm(forms.Form):
    template = forms.ModelChoiceField(
        label='テンプレート',
        queryset=ShiftTemplate.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        label='適用開始日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        label='適用終了日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

class ShiftExportForm(forms.Form):
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    format = forms.ChoiceField(
        label='出力形式',
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class ShiftReasonForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['staff', 'date', 'deletion_reason', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'deletion_reason': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'staff': 'スタッフ',
            'date': '日付',
            'deletion_reason': '事由',
            'notes': '備考',
        }


# wakakusa-shift-2から移植した新しいフォーム

class LeaveRequestForm(forms.ModelForm):
    """休み・通院申請フォーム"""
    class Meta:
        model = LeaveRequest
        fields = ['request_type', 'start_date', 'end_date', 'reason', 'priority']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'request_type': '申請種別',
            'start_date': '開始日',
            'end_date': '終了日',
            'reason': '理由',
            'priority': '緊急度',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('終了日は開始日以降である必要があります。')
        
        return cleaned_data


class ShiftProposalForm(forms.ModelForm):
    """シフト打診フォーム"""
    class Meta:
        model = ShiftProposal
        fields = ['proposed_to', 'shift_date', 'start_time', 'end_time', 'shift_type', 'position', 'message', 'response_deadline']
        widgets = {
            'proposed_to': forms.Select(attrs={'class': 'form-select'}),
            'shift_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'shift_type': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'response_deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # 実際にシフト勤務をするスタッフのみを対象に（職員・アルバイト）
        queryset = Staff.objects.filter(
            is_active=True, 
            approval_status='approved',
            role_type__in=['staff', 'part_time']  # 職員・アルバイトのみ
        )
        if organization:
            queryset = queryset.filter(organization=organization)
        self.fields['proposed_to'].queryset = queryset
        self.fields['shift_type'].required = False
        self.fields['position'].required = False
        self.fields['message'].required = False
        self.fields['response_deadline'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError('終了時間は開始時間より後である必要があります。')
        
        return cleaned_data


class ShiftProposalResponseForm(forms.ModelForm):
    """シフト打診回答フォーム"""
    class Meta:
        model = ShiftProposal
        fields = ['status', 'response_message']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'response_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 回答時は承諾か拒否のみ選択可能
        self.fields['status'].choices = [
            ('accepted', '承諾'),
            ('declined', '拒否'),
        ]
        self.fields['response_message'].required = False


class StaffCompatibilityForm(forms.ModelForm):
    """スタッフ間相性設定フォーム"""
    class Meta:
        model = StaffCompatibility
        fields = ['staff1', 'staff2', 'compatibility_level', 'reason']
        widgets = {
            'staff1': forms.Select(attrs={'class': 'form-select'}),
            'staff2': forms.Select(attrs={'class': 'form-select'}),
            'compatibility_level': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_staff = Staff.objects.filter(is_active=True, approval_status='approved')
        self.fields['staff1'].queryset = active_staff
        self.fields['staff2'].queryset = active_staff
        self.fields['reason'].required = False

    def clean(self):
        cleaned_data = super().clean()
        staff1 = cleaned_data.get('staff1')
        staff2 = cleaned_data.get('staff2')
        
        if staff1 and staff2 and staff1 == staff2:
            raise forms.ValidationError('同じスタッフ同士の相性設定はできません。')
        
        return cleaned_data


class HolidayForm(forms.ModelForm):
    """祝日・休日フォーム"""
    class Meta:
        model = Holiday
        fields = ['date', 'name', 'holiday_type', 'is_active']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'holiday_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class EventForm(forms.ModelForm):
    """イベントフォーム"""
    class Meta:
        model = Event
        fields = ['title', 'description', 'event_type', 'start_datetime', 'end_datetime', 'location']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'start_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_datetime': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['location'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')
        
        if start_datetime and end_datetime and start_datetime >= end_datetime:
            raise forms.ValidationError('終了日時は開始日時より後である必要があります。')
        
        return cleaned_data


class EventParticipantForm(forms.ModelForm):
    """イベント参加者フォーム"""
    class Meta:
        model = EventParticipant
        fields = ['staff', 'status']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = Staff.objects.filter(is_active=True, approval_status='approved')


# カレンダー機能拡張フォーム



class CalendarLeaveRequestForm(forms.ModelForm):
    """カレンダーから休暇申請フォーム"""
    class Meta:
        model = LeaveRequest
        fields = ['request_type', 'start_date', 'end_date', 'reason', 'priority']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }


# 日付範囲とエクスポート関連フォーム

class DateRangeForm(forms.Form):
    """日付範囲選択フォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('終了日は開始日以降である必要があります。')
        
        return cleaned_data


class ShiftExportForm(forms.Form):
    """シフトエクスポートフォーム"""
    start_date = forms.DateField(
        label='開始日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='終了日',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    format = forms.ChoiceField(
        label='出力形式',
        choices=[
            ('pdf', 'PDF'),
            ('csv', 'CSV'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    staff = forms.ModelMultipleChoiceField(
        label='スタッフ（複数選択可、未選択で全員）',
        queryset=Staff.objects.none(),  # 初期値は空
        widget=forms.CheckboxSelectMultiple(),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に所属するスタッフを取得
        if organization:
            # 組織に所属するスタッフのみ表示
            queryset = Staff.objects.filter(organization=organization).order_by('name')
        else:
            # 組織が指定されていない場合は全スタッフ
            queryset = Staff.objects.all().order_by('name')
        
        self.fields['staff'].queryset = queryset


# ===== 発注管理機能フォーム =====

class ItemForm(forms.ModelForm):
    """品目登録・編集フォーム"""
    
    class Meta:
        model = Item
        fields = ['item_code', 'item_name', 'unit', 'order_url', 'threshold', 'organization']
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: AA001'}),
            'item_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: レタス種子'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '例: 袋'}),
            'order_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/order'}),
            'threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '10'}),
            'organization': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'item_code': '品目コード',
            'item_name': '品目名',
            'unit': '単位',
            'order_url': '発注先URL',
            'threshold': '在庫閾値',
            'organization': '組織',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        if organization and not self.instance.pk:
            # 新規作成時は現在の組織を初期値に設定
            self.fields['organization'].initial = organization
            self.fields['organization'].widget = forms.HiddenInput()


class InventoryForm(forms.ModelForm):
    """在庫登録・編集フォーム"""
    
    class Meta:
        model = Inventory
        fields = ['item', 'current_stock']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
        labels = {
            'item': '品目',
            'current_stock': '在庫数',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に基づいて品目をフィルタリング
        if organization:
            self.fields['item'].queryset = Item.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('item_code')


class TransactionForm(forms.ModelForm):
    """入出庫処理フォーム"""
    
    class Meta:
        model = Transaction
        fields = ['item', 'transaction_type', 'quantity', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '備考があれば入力してください'}),
        }
        labels = {
            'item': '品目',
            'transaction_type': 'トランザクションタイプ',
            'quantity': '数量',
            'notes': '備考',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に基づいて品目をフィルタリング
        if organization:
            self.fields['item'].queryset = Item.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('item_code')


class OrderForm(forms.ModelForm):
    """発注登録フォーム"""
    
    class Meta:
        model = Order
        fields = ['item', 'ordered_quantity', 'supplier_url', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'ordered_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'supplier_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': '発注先URL（任意）'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '備考があれば入力してください'}),
        }
        labels = {
            'item': '品目',
            'ordered_quantity': '発注数量',
            'supplier_url': '発注先URL',
            'notes': '備考',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 組織に基づいて品目をフィルタリング
        if organization:
            self.fields['item'].queryset = Item.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('item_code')
        
        # 品目が選択されている場合、発注先URLを自動設定
        if self.instance.pk and self.instance.item and self.instance.item.order_url:
            self.fields['supplier_url'].initial = self.instance.item.order_url


class OrderStatusForm(forms.ModelForm):
    """発注ステータス変更フォーム"""
    
    class Meta:
        model = Order
        fields = ['status', 'delivery_date', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'delivery_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'status': 'ステータス',
            'delivery_date': '納品日時',
            'notes': '備考',
        }


# ===== 請求書・納品書発行機能フォーム =====

class InvoiceForm(forms.ModelForm):
    """請求書作成・編集フォーム"""
    
    class Meta:
        model = Invoice
        fields = [
            'bill_to_name', 'bill_to_address', 'bill_to_contact', 
            'bill_to_phone', 'bill_to_email', 'issue_date', 'due_date',
            'tax_rate', 'notes'
        ]
        widgets = {
            'bill_to_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '請求先名'}),
            'bill_to_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '請求先住所'}),
            'bill_to_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '担当者名'}),
            'bill_to_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '電話番号'}),
            'bill_to_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'メールアドレス'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '備考'}),
        }
        labels = {
            'bill_to_name': '請求先名',
            'bill_to_address': '請求先住所',
            'bill_to_contact': '担当者',
            'bill_to_phone': '電話番号',
            'bill_to_email': 'メールアドレス',
            'issue_date': '発行日',
            'due_date': '支払期限',
            'tax_rate': '消費税率(%)',
            'notes': '備考',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 初期値設定
        if not self.instance.pk:
            from datetime import date, timedelta
            self.fields['issue_date'].initial = date.today()
            self.fields['due_date'].initial = date.today() + timedelta(days=30)
            self.fields['tax_rate'].initial = 10.0


class InvoiceItemForm(forms.ModelForm):
    """請求書明細フォーム"""
    
    class Meta:
        model = InvoiceItem
        fields = ['item_name', 'item_description', 'quantity', 'unit', 'unit_price']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '品目名'}),
            'item_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '品目説明'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '単位'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'item_name': '品目名',
            'item_description': '品目説明',
            'quantity': '数量',
            'unit': '単位',
            'unit_price': '単価',
        }


class InvoiceStatusForm(forms.ModelForm):
    """請求書ステータス変更フォーム"""
    
    class Meta:
        model = Invoice
        fields = ['status', 'payment_date', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'status': 'ステータス',
            'payment_date': '入金日',
            'notes': '備考',
        }


class DeliveryNoteForm(forms.ModelForm):
    """納品書作成・編集フォーム"""
    
    class Meta:
        model = DeliveryNote
        fields = [
            'deliver_to_name', 'deliver_to_address', 'deliver_to_contact',
            'deliver_to_phone', 'issue_date', 'delivery_date', 'notes'
        ]
        widgets = {
            'deliver_to_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '納品先名'}),
            'deliver_to_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '納品先住所'}),
            'deliver_to_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '担当者名'}),
            'deliver_to_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '電話番号'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '備考'}),
        }
        labels = {
            'deliver_to_name': '納品先名',
            'deliver_to_address': '納品先住所',
            'deliver_to_contact': '担当者',
            'deliver_to_phone': '電話番号',
            'issue_date': '発行日',
            'delivery_date': '納品予定日',
            'notes': '備考',
        }
    
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # 初期値設定
        if not self.instance.pk:
            from datetime import date, timedelta
            self.fields['issue_date'].initial = date.today()
            self.fields['delivery_date'].initial = date.today() + timedelta(days=7)


class DeliveryNoteItemForm(forms.ModelForm):
    """納品書明細フォーム"""
    
    class Meta:
        model = DeliveryNoteItem
        fields = ['item_name', 'item_description', 'quantity', 'unit', 'delivered_quantity']
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '品目名'}),
            'item_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '品目説明'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '単位'}),
            'delivered_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'item_name': '品目名',
            'item_description': '品目説明',
            'quantity': '予定数量',
            'unit': '単位',
            'delivered_quantity': '実際の納品数量',
        }


class DeliveryNoteStatusForm(forms.ModelForm):
    """納品書ステータス変更フォーム"""
    
    class Meta:
        model = DeliveryNote
        fields = ['status', 'actual_delivery_date', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'actual_delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'status': 'ステータス',
            'actual_delivery_date': '実際の納品日',
            'notes': '備考',
        }