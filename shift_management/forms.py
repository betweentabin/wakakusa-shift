from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    Staff, Shift, ShiftType, Organization, ShiftTemplate, ShiftTemplateDetail,
    LeaveRequest, ShiftProposal, StaffCompatibility, Holiday, Event, EventParticipant
)

# 時間選択のための選択肢を生成（30分刻み）
TIME_CHOICES = []
for hour in range(24):
    for minute in [0, 30]:
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
        super().__init__(*args, **kwargs)
        # 実際にシフト勤務をするスタッフのみを対象に（職員・アルバイト）
        self.fields['proposed_to'].queryset = Staff.objects.filter(
            is_active=True, 
            approval_status='approved',
            role_type__in=['staff', 'part_time']  # 職員・アルバイトのみ
        )
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
        queryset=Staff.objects.filter(is_active=True, approval_status='approved'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )