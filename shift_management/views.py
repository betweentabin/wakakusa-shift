from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from django.template.loader import render_to_string
from django import forms
import json
import calendar
import datetime
from datetime import date, timedelta
import csv
from io import StringIO
import tempfile
import os
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
from .models import (
    Organization, Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail,
    LeaveRequest, ShiftProposal, StaffCompatibility, Holiday, Event, EventParticipant,
    Notification, create_notification
)
from .forms import (
    OrganizationForm, OrganizationSelectForm, StaffForm, ShiftTypeForm, ShiftForm, StaffShiftForm, ShiftTemplateForm, 
    ShiftTemplateDetailForm, DateRangeForm, TemplateApplyForm, BulkShiftForm, CalendarBulkShiftForm,
    AdvancedBulkShiftForm, ShiftExportForm, ShiftReasonForm,  # 既存フォーム
    LeaveRequestForm, ShiftProposalForm, ShiftProposalResponseForm, StaffCompatibilityForm,  # 新規フォーム
    HolidayForm, EventForm, EventParticipantForm, CalendarLeaveRequestForm
)
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required  
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import connection

# ヘルパー関数
def get_staff_for_user(user):
    """
    ログインユーザーに対応するStaffオブジェクトを取得
    userフィールドまたは名前で照合
    """
    try:
        # まずuserフィールドで検索
        return Staff.objects.get(user=user)
    except Staff.DoesNotExist:
        try:
            # userフィールドがない場合は名前で照合
            return Staff.objects.get(name=user.username, is_active=True)
        except Staff.DoesNotExist:
            return None

# 認証関連のビュー
def user_login(request):
    """ログインビュー（組織自動選択対応）"""
    if request.user.is_authenticated:
        # 既にログイン済みの場合は権限に応じてリダイレクト
        current_staff = get_staff_for_user(request.user)
        if current_staff and current_staff.organization:
            # スタッフの組織を自動選択
            request.session['current_organization_id'] = current_staff.organization.id
            request.session['current_organization_name'] = current_staff.organization.name
        
        if request.user.is_superuser or request.user.is_staff:
            return redirect('shift_management:calendar')
        else:
            return redirect('shift_management:staff_view')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # ログイン成功後に組織を自動選択
                current_staff = get_staff_for_user(user)
                if current_staff and current_staff.organization:
                    request.session['current_organization_id'] = current_staff.organization.id
                    request.session['current_organization_name'] = current_staff.organization.name
                    messages.success(
                        request, 
                        f'ようこそ、{username}さん！組織「{current_staff.organization.name}」でログインしました。'
                    )
                else:
                    messages.success(request, f'ようこそ、{username}さん！')
                
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                # 権限に応じてリダイレクト先を決定
                elif user.is_superuser:
                    # スーパーユーザーは組織選択画面へ
                    return redirect('shift_management:organization_select')
                elif user.is_staff or (current_staff and current_staff.role_type == 'manager'):
                    return redirect('shift_management:calendar')
                else:
                    return redirect('shift_management:staff_view')
        else:
            messages.error(request, 'ユーザー名またはパスワードが正しくありません。')
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

def user_logout(request):
    """ログアウトビュー"""
    logout(request)
    messages.success(request, 'ログアウトしました。')
    return redirect('login')  # Django標準のログインページにリダイレクト

@login_required
def home_redirect(request):
    """ホームページリダイレクト - 権限に応じて適切なページにリダイレクト"""
    current_staff = get_staff_for_user(request.user)
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        return redirect('shift_management:calendar')
    else:
        return redirect('shift_management:staff_view')

@login_required
def shift_calendar(request):
    """シフトカレンダー表示（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト管理画面へのアクセス権限がありません。')
        return redirect('shift_management:staff_view')
    today = timezone.now().date()
    # デフォルトでは今月の1日から末日までを表示
    year = today.year
    month = today.month
    _, last_day = calendar.monthrange(year, month)
    
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, last_day)
    
    # 日付範囲フォームが送信された場合
    form = DateRangeForm(request.GET or None, initial={
        'start_date': start_date,
        'end_date': end_date
    })
    
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    
    # 現在のユーザーに対応するStaffオブジェクトを取得
    current_staff = get_staff_for_user(request.user)
    
    # 権限に応じてスタッフ一覧を制限
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        # 管理者は全スタッフを表示
        staff_list = Staff.objects.filter(is_active=True)
    elif current_staff and current_staff.role_type == 'staff':
        # 職員は職員とアルバイトを表示
        staff_list = Staff.objects.filter(
            is_active=True,
            role_type__in=['staff', 'part_time']
        )
    elif current_staff and current_staff.role_type == 'part_time':
        # アルバイトは同じアルバイトのみ表示
        staff_list = Staff.objects.filter(
            is_active=True,
            role_type='part_time'
        )
    elif current_staff and current_staff.role_type == 'user':
        # 利用者は自分のみ表示
        staff_list = Staff.objects.filter(id=current_staff.id)
    else:
        # 対応するStaffオブジェクトがない場合は空のクエリセット
        staff_list = Staff.objects.none()
    
    # 日付範囲内のシフトを取得（承認済み + 承認待ち）
    # 権限に応じてシフトも制限
    shifts = Shift.objects.filter(
        date__range=[start_date, end_date],
        approval_status__in=['approved', 'pending'],
        staff__in=staff_list  # 権限に応じて制限されたスタッフのシフトのみ
    ).select_related('staff', 'shift_type')
    
    # シフト種別一覧を取得
    shift_types = ShiftType.objects.all()
    
    # カレンダーデータの作成
    calendar_data = []
    current_date = start_date
    while current_date <= end_date:
        day_shifts = []
        for staff in staff_list:
            staff_shifts = [shift for shift in shifts if shift.staff_id == staff.id and shift.date == current_date]
            day_shifts.append({
                'staff': staff,
                'shifts': staff_shifts
            })
        
        calendar_data.append({
            'date': current_date,
            'weekday': current_date.weekday(),
            'staff_shifts': day_shifts
        })
        
        current_date += datetime.timedelta(days=1)
    
    context = {
        'form': form,
        'calendar_data': calendar_data,
        'staff_list': staff_list,
        'shift_types': shift_types,
        'start_date': start_date,
        'end_date': end_date,
        'current_staff': current_staff,  # 現在のスタッフ情報を追加
        'user_role': current_staff.role_type if current_staff else 'none',  # ユーザーの権限種別を追加
    }
    
    return render(request, 'shift_management/calendar.html', context)

@login_required
def staff_list(request):
    """スタッフ一覧表示（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'スタッフ管理画面へのアクセス権限がありません。')
        return redirect('shift_management:staff_view')
    
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    # 組織に基づいてスタッフをフィルタリング
    if current_organization and not request.user.is_superuser:
        # 組織管理者は所属組織のスタッフのみ表示
        staffs = Staff.objects.filter(organization=current_organization)
    elif request.user.is_superuser:
        # スーパーユーザーは全組織のスタッフを表示
        staffs = Staff.objects.all()
    else:
        # 組織が選択されていない場合は空のリストを返す
        staffs = Staff.objects.none()
    
    return render(request, 'shift_management/staff_list.html', {
        'staffs': staffs,
        'current_organization': current_organization
    })

@login_required
def staff_create(request):
    """スタッフ新規作成（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'スタッフ作成権限がありません。')
        return redirect('shift_management:staff_view')
    
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            # フォームのsaveメソッドを使用してユーザーアカウント作成処理も含めて保存
            staff = form.save(commit=False)
            # 組織管理者の場合は現在の組織を自動設定
            if current_organization and not request.user.is_superuser:
                staff.organization = current_organization
            staff.approval_status = 'pending'  # 新規登録時は承認待ち状態
            staff.save()
            messages.success(request, 'スタッフを登録しました。管理者の承認をお待ちください。')
            return redirect('shift_management:staff_list')
    else:
        # 組織管理者の場合は現在の組織を初期値に設定
        initial = {}
        if current_organization and not request.user.is_superuser:
            initial['organization'] = current_organization
        form = StaffForm(initial=initial)
    
    return render(request, 'shift_management/staff_form.html', {'form': form, 'is_create': True})

@login_required
def staff_edit(request, pk):
    """スタッフ編集"""
    staff = get_object_or_404(Staff, pk=pk)
    
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    # 組織管理者は自分の組織のスタッフのみ編集可能（スーパーユーザーは全て編集可能）
    if not request.user.is_superuser and current_organization and staff.organization != current_organization:
        messages.error(request, '他の組織のスタッフは編集できません。')
        return redirect('shift_management:staff_list')
    
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, 'スタッフ情報を更新しました。')
            return redirect('shift_management:staff_list')
    else:
        form = StaffForm(instance=staff)
    
    return render(request, 'shift_management/staff_form.html', {'form': form, 'staff': staff, 'is_create': False})

@login_required
def staff_delete(request, pk):
    """スタッフ削除"""
    staff = get_object_or_404(Staff, pk=pk)
    
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    # 組織管理者は自分の組織のスタッフのみ削除可能（スーパーユーザーは全て削除可能）
    if not request.user.is_superuser and current_organization and staff.organization != current_organization:
        messages.error(request, '他の組織のスタッフは削除できません。')
        return redirect('shift_management:staff_list')
    
    if request.method == 'POST':
        staff.is_active = False
        staff.save()
        messages.success(request, 'スタッフを無効化しました。')
        return redirect('shift_management:staff_list')
    
    return render(request, 'shift_management/staff_delete.html', {'staff': staff})

@login_required
def shift_create(request):
    """シフト新規作成（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト作成権限がありません。')
        return redirect('shift_management:staff_view')
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    if request.method == 'POST':
        form = ShiftForm(request.POST, organization=current_organization)
        if form.is_valid():
            shift = form.save(commit=False)
            # 管理者が作成したシフトは承認済み状態で保存
            shift.approval_status = 'approved'
            shift.approved_at = timezone.now()
            shift.approved_by = request.user
            shift.created_by = request.user
            shift.save()
            messages.success(request, 'シフトを登録しました。')
            # カレンダー更新フラグを追加してリダイレクト
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # GETパラメータから初期値を設定
        initial = {}
        if 'date' in request.GET:
            initial['date'] = request.GET.get('date')
        if 'staff' in request.GET:
            initial['staff'] = request.GET.get('staff')
        
        form = ShiftForm(initial=initial, organization=current_organization)
    
    return render(request, 'shift_management/shift_form.html', {'form': form, 'is_create': True})

@login_required
def shift_edit(request, pk):
    """シフト編集"""
    shift = get_object_or_404(Shift, pk=pk)
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    if request.method == 'POST':
        form = ShiftForm(request.POST, instance=shift, organization=current_organization)
        if form.is_valid():
            shift = form.save(commit=False)
            # 管理者が編集したシフトは承認済み状態を維持
            if not shift.created_by:
                shift.created_by = request.user
            shift.save()
            messages.success(request, 'シフトを更新しました。')
            # カレンダー更新フラグを追加してリダイレクト
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        form = ShiftForm(instance=shift, organization=current_organization)
    
    return render(request, 'shift_management/shift_form.html', {'form': form, 'shift': shift, 'is_create': False})

@login_required
def shift_delete(request, pk):
    """シフト削除"""
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        shift.delete()
        messages.success(request, 'シフトを削除しました。')
        # カレンダー更新フラグを追加してリダイレクト
        return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    
    return render(request, 'shift_management/shift_delete.html', {'shift': shift})

@login_required
def shift_reason_create(request):
    """事由登録（公休、有給等）"""
    if request.method == 'POST':
        form = ShiftReasonForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '事由を登録しました。')
            # カレンダー更新フラグを追加してリダイレクト
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # GETパラメータから初期値を設定
        initial = {}
        if 'date' in request.GET:
            initial['date'] = request.GET.get('date')
        if 'staff' in request.GET:
            initial['staff'] = request.GET.get('staff')
        
        form = ShiftReasonForm(initial=initial)
    
    return render(request, 'shift_management/shift_reason_form.html', {'form': form})

@login_required
def bulk_shift_create(request):
    """複数シフト一括登録（新規追加）"""
    # カレンダー版の一括登録画面へリダイレクト
    return redirect('shift_management:calendar_bulk_shift_create')
    
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, '一括シフト作成権限がありません。')
        return redirect('shift_management:staff_view')
    
    # 現在の組織を取得
    current_organization = request.session.get('current_organization')
    if current_organization:
        current_organization = get_object_or_404(Organization, id=current_organization)
    
    if request.method == 'POST':
        form = BulkShiftForm(request.POST, organization=current_organization)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            staff_list = form.cleaned_data['staff']
            shift_type = form.cleaned_data['shift_type']
            weekdays = form.cleaned_data['weekdays']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            overwrite = form.cleaned_data['overwrite']
            
            # 日付範囲内の各日に対してシフトを作成
            current_date = start_date
            shifts_created = 0
            
            while current_date <= end_date:
                weekday = current_date.weekday()
                
                # 選択された曜日のみ処理
                if str(weekday) in weekdays:
                    for staff in staff_list:
                        # 既存のシフトをチェック
                        existing_shifts = Shift.objects.filter(
                            staff=staff,
                            date=current_date
                        )
                        
                        if existing_shifts.exists() and not overwrite:
                            # 既存のシフトがあり、上書きしない設定の場合はスキップ
                            continue
                        
                        # 既存のシフトを削除（上書きする場合）
                        if existing_shifts.exists() and overwrite:
                            existing_shifts.delete()
                        
                        # 新しいシフトを作成
                        Shift.objects.create(
                            staff=staff,
                            shift_type=shift_type,
                            date=current_date,
                            start_time=start_time,
                            end_time=end_time,
                            approval_status='approved',  # 管理者が作成したシフトは承認済み
                            approved_at=timezone.now(),
                            approved_by=request.user,
                            created_by=request.user
                        )
                        shifts_created += 1
                
                current_date += datetime.timedelta(days=1)
            
            messages.success(request, f'{shifts_created}件のシフトを一括登録しました。')
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # デフォルトでは今日から1週間を設定
        today = timezone.now().date()
        next_week = today + datetime.timedelta(days=7)
        
        # GETパラメータから初期値を設定
        initial = {
            'start_date': request.GET.get('start_date', today),
            'end_date': request.GET.get('end_date', next_week)
        }
        
        form = BulkShiftForm(initial=initial, organization=current_organization)
    
    # シフト種別にデフォルト時間のデータ属性を追加
    for field in form.fields['shift_type'].choices:
        if hasattr(field, 'instance') and field.instance:
            field.attrs = {
                'data-start-time': field.instance.start_time.strftime('%H:%M'),
                'data-end-time': field.instance.end_time.strftime('%H:%M')
            }
    
    return render(request, 'shift_management/bulk_shift_form.html', {'form': form})

@login_required  
def traditional_bulk_shift_create(request):
    """複数シフト一括登録（従来版：日付範囲+曜日指定）（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, '一括シフト作成権限がありません。')
        return redirect('shift_management:staff_view')
    
    # 現在の組織を取得
    current_organization = request.session.get('current_organization')
    if current_organization:
        current_organization = get_object_or_404(Organization, id=current_organization)
    
    if request.method == 'POST':
        form = BulkShiftForm(request.POST, organization=current_organization)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            staff_list = form.cleaned_data['staff']
            shift_type = form.cleaned_data['shift_type']
            weekdays = form.cleaned_data['weekdays']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            overwrite = form.cleaned_data['overwrite']
            
            # 日付範囲内の各日に対してシフトを作成
            current_date = start_date
            shifts_created = 0
            
            while current_date <= end_date:
                weekday = current_date.weekday()
                
                # 選択された曜日のみ処理
                if str(weekday) in weekdays:
                    for staff in staff_list:
                        # 既存のシフトをチェック
                        existing_shifts = Shift.objects.filter(
                            staff=staff,
                            date=current_date
                        )
                        
                        if existing_shifts.exists() and not overwrite:
                            # 既存のシフトがあり、上書きしない設定の場合はスキップ
                            continue
                        
                        # 既存のシフトを削除（上書きする場合）
                        if existing_shifts.exists() and overwrite:
                            existing_shifts.delete()
                        
                        # 新しいシフトを作成
                        Shift.objects.create(
                            staff=staff,
                            shift_type=shift_type,
                            date=current_date,
                            start_time=start_time,
                            end_time=end_time,
                            approval_status='approved',  # 管理者が作成したシフトは承認済み
                            approved_at=timezone.now(),
                            approved_by=request.user,
                            created_by=request.user
                        )
                        shifts_created += 1
                
                current_date += datetime.timedelta(days=1)
            
            messages.success(request, f'{shifts_created}件のシフトを一括登録しました。')
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # デフォルトでは今日から1週間を設定
        today = timezone.now().date()
        next_week = today + datetime.timedelta(days=7)
        
        # GETパラメータから初期値を設定
        initial = {
            'start_date': request.GET.get('start_date', today),
            'end_date': request.GET.get('end_date', next_week)
        }
        
        form = BulkShiftForm(initial=initial, organization=current_organization)
    
    # シフト種別にデフォルト時間のデータ属性を追加
    for field in form.fields['shift_type'].choices:
        if hasattr(field, 'instance') and field.instance:
            field.attrs = {
                'data-start-time': field.instance.start_time.strftime('%H:%M'),
                'data-end-time': field.instance.end_time.strftime('%H:%M')
            }
    
    return render(request, 'shift_management/bulk_shift_form.html', {'form': form})

@login_required
def calendar_bulk_shift_create(request):
    """カレンダー上での一括シフト登録"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト登録の権限がありません。')
        return redirect('shift_management:calendar')
    
    # 現在の組織を取得
    current_organization = request.session.get('current_organization')
    if current_organization:
        current_organization = get_object_or_404(Organization, id=current_organization)
    
    if request.method == 'POST':
        form = CalendarBulkShiftForm(request.POST)
        if form.is_valid():
            try:
                selected_dates = form.cleaned_data['selected_dates']  # これは既にdateオブジェクトのリスト
                staff_list = form.cleaned_data['staff']
                shift_type = form.cleaned_data['shift_type']
                start_time_str = form.cleaned_data['start_time']
                end_time_str = form.cleaned_data['end_time']
                overwrite = form.cleaned_data.get('overwrite', False)
                individual_times_str = form.cleaned_data.get('individual_times', '')
                
                # デバッグ情報
                print(f"DEBUG: selected_dates = {selected_dates}")
                print(f"DEBUG: staff_list = {staff_list}")
                print(f"DEBUG: shift_type = {shift_type}")
                print(f"DEBUG: start_time_str = {start_time_str}")
                print(f"DEBUG: end_time_str = {end_time_str}")
                
                # 個別時間データの解析
                individual_times = {}
                if individual_times_str:
                    try:
                        individual_times = json.loads(individual_times_str)
                    except (json.JSONDecodeError, ValueError):
                        individual_times = {}
                
                # 時間文字列をtimeオブジェクトに変換
                from django.utils.dateparse import parse_time
                start_time = parse_time(start_time_str) if isinstance(start_time_str, str) else start_time_str
                end_time = parse_time(end_time_str) if isinstance(end_time_str, str) else end_time_str
                
                created_shifts = []
                skipped_shifts = []
                
                # 各日付と各スタッフの組み合わせでシフトを作成
                for date in selected_dates:
                    # 個別時間設定がある場合はそれを使用、なければデフォルトを使用
                    date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
                    if individual_times and date_str in individual_times:
                        shift_start_time = parse_time(individual_times[date_str]['start_time'])
                        shift_end_time = parse_time(individual_times[date_str]['end_time'])
                    else:
                        shift_start_time = start_time
                        shift_end_time = end_time
                    
                    for staff in staff_list:
                        # 既存シフトの確認
                        existing_shift = Shift.objects.filter(
                            staff=staff,
                            date=date
                        ).first()
                        
                        if existing_shift and not overwrite:
                            staff_name = getattr(staff, 'name', f'Staff {staff.id}')
                            skipped_shifts.append(f'{staff_name} - {date}')
                            continue
                        
                        if existing_shift and overwrite:
                            # 既存シフトを削除
                            existing_shift.delete()
                        
                        # 新しいシフトを作成（shift-2と同じシンプルな形式）
                        shift = Shift.objects.create(
                            staff=staff,
                            date=date,
                            start_time=shift_start_time,
                            end_time=shift_end_time,
                            shift_type=shift_type,
                            approval_status='approved'  # 管理者作成なので自動承認
                        )
                        staff_name = getattr(staff, 'name', f'Staff {staff.id}')
                        created_shifts.append(f'{staff_name} - {date}')
                
                # 結果メッセージ
                success_message = f'{len(created_shifts)}件のシフトを登録しました。'
                if skipped_shifts:
                    success_message += f' {len(skipped_shifts)}件は既存シフトのためスキップしました。'
                
                messages.success(request, success_message)
                return redirect('shift_management:calendar')
                
            except Exception as e:
                print(f"DEBUG: Exception occurred: {str(e)}")
                messages.error(request, f'シフト登録中にエラーが発生しました: {str(e)}')
        else:
            print(f"DEBUG: Form is not valid. Form type: {type(form)}")
            print(f"DEBUG: Form fields: {list(form.fields.keys())}")
            print(f"DEBUG: Form errors: {form.errors}")
            print(f"DEBUG: POST data: {request.POST}")
            messages.error(request, f'フォームエラー: {form.errors}')
    else:
        form = CalendarBulkShiftForm()
    
    # シフト種別のデフォルト時間情報をJSONで渡す
    shift_types_data = {}
    if current_organization:
        shift_types = ShiftType.objects.filter(organization=current_organization)
    else:
        shift_types = ShiftType.objects.all()
        
    for shift_type in shift_types:
        try:
            start_time = shift_type.start_time.strftime('%H:%M') if shift_type.start_time else '09:00'
            end_time = shift_type.end_time.strftime('%H:%M') if shift_type.end_time else '17:00'
        except (AttributeError, ValueError):
            start_time = '09:00'
            end_time = '17:00'
            
        shift_types_data[shift_type.id] = {
            'start_time': start_time,
            'end_time': end_time,
        }
    
    # 既存のシフトデータを取得（カレンダー表示用）
    from datetime import timedelta
    
    shift_events = []
    try:
        # 現在の月の前後1ヶ月分のシフトを取得
        today = timezone.now().date()
        start_date = today.replace(day=1) - timedelta(days=30)
        end_date = today + timedelta(days=60)
        
        shifts_filter = Shift.objects.filter(
            date__range=[start_date, end_date],
            is_deleted_with_reason=False
        )
        
        if current_organization:
            shifts_filter = shifts_filter.filter(staff__organization=current_organization)
            
        shifts = shifts_filter.select_related('staff', 'shift_type')
        
        # シフトデータをFullCalendar用に整形
        for shift in shifts:
            try:
                # 安全にアクセスできるよう属性の存在確認
                staff_name = getattr(shift.staff, 'name', 'Unknown Staff')
                shift_type_name = getattr(shift.shift_type, 'name', 'Unknown Type')
                shift_type_color = getattr(shift.shift_type, 'color', '#6c757d')
                
                shift_events.append({
                    'title': f'{staff_name} ({shift_type_name})',
                    'start': shift.date.isoformat(),
                    'backgroundColor': shift_type_color,
                    'borderColor': shift_type_color,
                    'textColor': '#fff',
                    'extendedProps': {
                        'staffName': staff_name,
                        'shiftType': shift_type_name,
                        'startTime': shift.start_time.strftime('%H:%M') if shift.start_time else '00:00',
                        'endTime': shift.end_time.strftime('%H:%M') if shift.end_time else '00:00',
                        'approvalStatus': getattr(shift, 'approval_status', 'pending')
                    }
                })
            except Exception as e:
                # 個別のシフト処理でエラーが発生した場合はスキップ
                print(f"シフト処理エラーをスキップ: {e}")
                continue
    except Exception as e:
        # シフトデータ取得でエラーが発生した場合は空のリストを使用
        print(f"シフトデータ取得エラー: {e}")
        shift_events = []
    
    return render(request, 'shift_management/calendar_bulk_shift_form.html', {
        'form': form,
        'shift_types_data': shift_types_data,
        'existing_shifts': json.dumps(shift_events),
    })

@login_required
def advanced_bulk_shift_create(request):
    """日ごとに異なる時間帯を設定できる高度な一括シフト登録"""
    if request.method == 'POST':
        form = AdvancedBulkShiftForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            staff_list = form.cleaned_data['staff']
            default_shift_type = form.cleaned_data['shift_type']
            weekdays = form.cleaned_data['weekdays']
            time_settings_json = form.cleaned_data['time_settings']
            overwrite = form.cleaned_data['overwrite']
            
            # 時間設定をパース
            time_settings = {}
            if time_settings_json:
                try:
                    import json
                    time_settings = json.loads(time_settings_json)
                except json.JSONDecodeError:
                    messages.error(request, '時間設定の形式が正しくありません。')
                    return render(request, 'shift_management/advanced_bulk_shift_form.html', {'form': form})
            
            # 日付範囲内の各日に対してシフトを作成
            current_date = start_date
            shifts_created = 0
            
            while current_date <= end_date:
                weekday = current_date.weekday()
                date_str = current_date.strftime('%Y-%m-%d')
                
                # 選択された曜日のみ処理
                if str(weekday) in weekdays:
                    # 日付ごとの時間設定を取得
                    if date_str in time_settings:
                        start_time = time_settings[date_str]['start_time']
                        end_time = time_settings[date_str]['end_time']
                    else:
                        # 時間設定がない場合はデフォルトのシフト種別の時間を使用
                        if default_shift_type:
                            start_time = default_shift_type.start_time.strftime('%H:%M')
                            end_time = default_shift_type.end_time.strftime('%H:%M')
                        else:
                            # デフォルトの時間を設定
                            start_time = '09:00'
                            end_time = '17:00'
                    
                    for staff in staff_list:
                        # 既存のシフトをチェック
                        existing_shifts = Shift.objects.filter(
                            staff=staff,
                            date=current_date
                        )
                        
                        if existing_shifts.exists() and not overwrite:
                            # 既存のシフトがあり、上書きしない設定の場合はスキップ
                            continue
                        
                        # 既存のシフトを削除（上書きする場合）
                        if existing_shifts.exists() and overwrite:
                            existing_shifts.delete()
                        
                        # 新しいシフトを作成
                        Shift.objects.create(
                            staff=staff,
                            shift_type=default_shift_type,
                            date=current_date,
                            start_time=start_time,
                            end_time=end_time,
                            approval_status='approved',  # 管理者が作成したシフトは承認済み
                            approved_at=timezone.now(),
                            approved_by=request.user,
                            created_by=request.user
                        )
                        shifts_created += 1
                
                current_date += datetime.timedelta(days=1)
            
            messages.success(request, f'{shifts_created}件のシフトを一括登録しました。')
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # デフォルトでは今日から1週間を設定
        today = timezone.now().date()
        next_week = today + datetime.timedelta(days=7)
        
        # GETパラメータから初期値を設定
        initial = {
            'start_date': request.GET.get('start_date', today),
            'end_date': request.GET.get('end_date', next_week)
        }
        
        form = AdvancedBulkShiftForm(initial=initial)
    
    return render(request, 'shift_management/advanced_bulk_shift_form.html', {'form': form})

@login_required
def shift_type_list(request):
    """シフト種別一覧表示（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト種別管理画面へのアクセス権限がありません。')
        return redirect('shift_management:staff_view')
    
    shift_types = ShiftType.objects.all()
    return render(request, 'shift_management/shift_type_list.html', {'shift_types': shift_types})

@login_required
def shift_type_create(request):
    """シフト種別新規作成（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト種別作成権限がありません。')
        return redirect('shift_management:staff_view')
    if request.method == 'POST':
        form = ShiftTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'シフト種別を登録しました。')
            return redirect('shift_management:shift_type_list')
    else:
        form = ShiftTypeForm()
    
    return render(request, 'shift_management/shift_type_form.html', {'form': form, 'is_create': True})

@login_required
def shift_type_edit(request, pk):
    """シフト種別編集"""
    shift_type = get_object_or_404(ShiftType, pk=pk)
    if request.method == 'POST':
        form = ShiftTypeForm(request.POST, instance=shift_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'シフト種別を更新しました。')
            return redirect('shift_management:shift_type_list')
    else:
        form = ShiftTypeForm(instance=shift_type)
    
    return render(request, 'shift_management/shift_type_form.html', {'form': form, 'shift_type': shift_type, 'is_create': False})

@login_required
def shift_type_delete(request, pk):
    """シフト種別削除"""
    shift_type = get_object_or_404(ShiftType, pk=pk)
    if request.method == 'POST':
        shift_type.delete()
        messages.success(request, 'シフト種別を削除しました。')
        return redirect('shift_management:shift_type_list')
    
    return render(request, 'shift_management/shift_type_delete.html', {'shift_type': shift_type})

@login_required
def template_list(request):
    """シフトテンプレート一覧表示（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'テンプレート管理画面へのアクセス権限がありません。')
        return redirect('shift_management:staff_view')
    
    templates = ShiftTemplate.objects.all()
    return render(request, 'shift_management/template_list.html', {'templates': templates})

@login_required
def template_create(request):
    """シフトテンプレート新規作成"""
    if request.method == 'POST':
        form = ShiftTemplateForm(request.POST)
        if form.is_valid():
            template = form.save()
            messages.success(request, 'シフトテンプレートを作成しました。詳細を追加してください。')
            return redirect('shift_management:template_edit', pk=template.pk)
    else:
        form = ShiftTemplateForm()
    
    return render(request, 'shift_management/template_form.html', {'form': form, 'is_create': True})

@login_required
def template_edit(request, pk):
    """シフトテンプレート編集"""
    template = get_object_or_404(ShiftTemplate, pk=pk)
    form = ShiftTemplateForm(instance=template)
    
    # テンプレート詳細の追加フォーム
    detail_form = ShiftTemplateDetailForm(initial={'template': template})
    
    # 既存の詳細を取得
    details = ShiftTemplateDetail.objects.filter(template=template).select_related('staff', 'shift_type')
    
    if request.method == 'POST':
        if 'update_template' in request.POST:
            form = ShiftTemplateForm(request.POST, instance=template)
            if form.is_valid():
                form.save()
                messages.success(request, 'テンプレート情報を更新しました。')
                return redirect('shift_management:template_edit', pk=template.pk)
        
        elif 'add_detail' in request.POST:
            detail_form = ShiftTemplateDetailForm(request.POST)
            if detail_form.is_valid():
                detail = detail_form.save(commit=False)
                detail.template = template
                detail.save()
                messages.success(request, 'テンプレート詳細を追加しました。')
                return redirect('shift_management:template_edit', pk=template.pk)
    
    context = {
        'form': form,
        'detail_form': detail_form,
        'template': template,
        'details': details,
        'is_create': False
    }
    
    return render(request, 'shift_management/template_edit.html', context)

@login_required
def template_delete(request, pk):
    """シフトテンプレート削除"""
    template = get_object_or_404(ShiftTemplate, pk=pk)
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'シフトテンプレートを削除しました。')
        return redirect('shift_management:template_list')
    
    return render(request, 'shift_management/template_delete.html', {'template': template})

@login_required
def template_apply(request, pk):
    """シフトテンプレートを適用"""
    template = get_object_or_404(ShiftTemplate, pk=pk)
    
    if request.method == 'POST':
        form = TemplateApplyForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            overwrite = form.cleaned_data['overwrite']
            
            # テンプレート詳細を取得
            details = ShiftTemplateDetail.objects.filter(template=template)
            
            # 日付範囲内の各日に対してテンプレートを適用
            current_date = start_date
            shifts_created = 0
            
            while current_date <= end_date:
                weekday = current_date.weekday()
                
                # その曜日に該当するテンプレート詳細を取得
                day_details = [d for d in details if d.weekday == weekday]
                
                for detail in day_details:
                    # 既存のシフトをチェック
                    existing_shifts = Shift.objects.filter(
                        staff=detail.staff,
                        date=current_date
                    )
                    
                    if existing_shifts.exists() and not overwrite:
                        # 既存のシフトがあり、上書きしない設定の場合はスキップ
                        continue
                    
                    # 既存のシフトを削除（上書きする場合）
                    if existing_shifts.exists() and overwrite:
                        existing_shifts.delete()
                    
                    # 新しいシフトを作成
                    Shift.objects.create(
                        staff=detail.staff,
                        shift_type=detail.shift_type,
                        date=current_date,
                        start_time=detail.start_time,
                        end_time=detail.end_time
                    )
                    shifts_created += 1
                
                current_date += datetime.timedelta(days=1)
            
            messages.success(request, f'テンプレートを適用し、{shifts_created}件のシフトを作成しました。')
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        # デフォルトでは翌週の月曜から日曜までを設定
        today = timezone.now().date()
        days_ahead = 7 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + datetime.timedelta(days=days_ahead)
        next_sunday = next_monday + datetime.timedelta(days=6)
        
        form = TemplateApplyForm(initial={
            'start_date': next_monday,
            'end_date': next_sunday
        })
    
    return render(request, 'shift_management/template_apply.html', {'form': form, 'template': template})

@login_required
def template_detail_delete(request, pk):
    """シフトテンプレート詳細を削除"""
    detail = get_object_or_404(ShiftTemplateDetail, pk=pk)
    template_pk = detail.template.pk # Get parent template's PK for redirection

    if request.method == 'POST':
        detail.delete()
        messages.success(request, 'テンプレート詳細を削除しました。')
        # Redirect back to the template edit page
        return redirect('shift_management:template_edit', pk=template_pk)
    
    # For GET request, display confirmation page
    return render(request, 'shift_management/template_detail_delete.html', {'detail': detail})

@login_required
def shift_export(request):
    """シフト表の印刷・エクスポート（新規追加）（管理者権限のみ）"""
    # 管理者権限チェック
    current_staff = get_staff_for_user(request.user)
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフトエクスポート権限がありません。')
        return redirect('shift_management:staff_view')
    if request.method == 'POST':
        form = ShiftExportForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            selected_staff = form.cleaned_data['staff']
            format_type = form.cleaned_data['format_type']
            
            # スタッフフィルター
            if selected_staff:
                staff_list = selected_staff
            else:
                staff_list = Staff.objects.filter(is_active=True)
            
            # 承認済みシフトデータ取得
            shifts = Shift.objects.filter(
                date__range=[start_date, end_date],
                staff__in=staff_list,
                approval_status='approved'  # 承認済みのシフトのみ
            ).select_related('staff', 'shift_type').order_by('date', 'start_time')
            
            # 日付範囲の全日付リスト作成
            date_list = []
            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date)
                current_date += datetime.timedelta(days=1)
            
            # 出力形式に応じた処理
            if format_type == 'pdf':
                # PDF出力機能の利用可否をチェック
                if not WEASYPRINT_AVAILABLE:
                    messages.error(request, 'PDF出力機能は現在利用できません。CSVでの出力をお試しください。')
                    return redirect('shift_management:shift_export')
                
                try:
                    # PDF出力
                    context = {
                        'start_date': start_date,
                        'end_date': end_date,
                        'staff_list': staff_list,
                        'date_list': date_list,
                        'shifts': shifts,
                    }
                    
                    # HTMLテンプレートをレンダリング
                    html_string = render_to_string('shift_management/shift_pdf_template.html', context)
                    
                    # WeasyPrintでPDF生成
                    html = HTML(string=html_string)
                    css = CSS(string='''
                        @page {
                            size: A4 landscape;
                            margin: 1cm;
                        }
                        body {
                            font-family: sans-serif;
                        }
                        table {
                            width: 100%;
                            border-collapse: collapse;
                        }
                        th, td {
                            border: 1px solid #ddd;
                            padding: 4px;
                            text-align: center;
                            font-size: 12px;
                        }
                        th {
                            background-color: #f2f2f2;
                        }
                        .shift-entry {
                            margin-bottom: 2px;
                            padding: 2px;
                            border-radius: 3px;
                        }
                    ''')
                    
                    # PDFファイル生成
                    pdf_file = html.write_pdf(stylesheets=[css])
                    
                    # レスポンス作成
                    response = HttpResponse(pdf_file, content_type='application/pdf')
                    filename = f'shift_table_{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")}.pdf'
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    
                    return response
                    
                except Exception as e:
                    messages.error(request, f'PDF生成中にエラーが発生しました: {str(e)}。CSVでの出力をお試しください。')
                    return redirect('shift_management:shift_export')
                
            elif format_type == 'csv':
                # CSV出力
                response = HttpResponse(content_type='text/csv')
                filename = f'shift_table_{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")}.csv'
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                # CSVライター設定
                response.write('\ufeff')  # BOMを追加してExcelでの文字化け対策
                writer = csv.writer(response)
                
                # ヘッダー行
                header = ['スタッフ名']
                for date in date_list:
                    header.append(f'{date.strftime("%Y/%m/%d")}({["月","火","水","木","金","土","日"][date.weekday()]})')
                writer.writerow(header)
                
                # スタッフごとの行
                for staff in staff_list:
                    row = [staff.name]
                    for date in date_list:
                        # その日のシフトを取得
                        day_shifts = [s for s in shifts if s.staff_id == staff.id and s.date == date]
                        if day_shifts:
                            shift_texts = []
                            for shift in day_shifts:
                                shift_type_name = shift.shift_type.name if shift.shift_type else "未設定"
                                shift_texts.append(f'{shift_type_name} {shift.start_time.strftime("%H:%M")}-{shift.end_time.strftime("%H:%M")}')
                            row.append('\n'.join(shift_texts))
                        else:
                            row.append('')
                    writer.writerow(row)
                
                return response
    else:
        # デフォルトでは今月の1日から末日までを設定
        today = timezone.now().date()
        year = today.year
        month = today.month
        _, last_day = calendar.monthrange(year, month)
        
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, last_day)
        
        form = ShiftExportForm(initial={
            'start_date': start_date,
            'end_date': end_date,
            'format_type': 'pdf'
        })
    
    return render(request, 'shift_management/shift_export.html', {'form': form})

@login_required
def api_shifts(request):
    """シフトデータをJSON形式で返すAPI"""
    print("[DEBUG] api_shifts called") # DEBUG
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')
    
    print(f"[DEBUG] Received start_date_str: {start_date_str}, end_date_str: {end_date_str}") # DEBUG

    if not start_date_str or not end_date_str:
        print("[DEBUG] Error: Start date or end date not provided") # DEBUG
        return JsonResponse({'error': '開始日と終了日を指定してください'}, status=400)
    
    try:
        print(f"[DEBUG] Attempting to parse dates: start={start_date_str}, end={end_date_str}") # DEBUG
        # ISO形式の日付文字列から日付部分のみを抽出
        start_date_iso = start_date_str.split('T')[0]
        end_date_iso = end_date_str.split('T')[0]
        start_date = datetime.datetime.strptime(start_date_iso, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_iso, '%Y-%m-%d').date()
        print(f"[DEBUG] Parsed dates: start_date={start_date}, end_date={end_date}") # DEBUG
    except ValueError:
        print(f"[DEBUG] Error: Date format incorrect for start={start_date_str} or end={end_date_str}") # DEBUG
        return JsonResponse({'error': '日付形式が正しくありません'}, status=400)
    
    # 現在のユーザーに対応するStaffオブジェクトを取得
    current_staff = get_staff_for_user(request.user)
    
    # 権限に応じてスタッフ一覧を制限
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        # 管理者は全スタッフのシフトを表示
        staff_filter = Q()  # 制限なし
    elif current_staff and current_staff.role_type == 'staff':
        # 職員は職員とアルバイトのシフトを表示
        staff_filter = Q(staff__role_type__in=['staff', 'part_time'])
    elif current_staff and current_staff.role_type == 'part_time':
        # アルバイトは同じアルバイトのシフトのみ表示
        staff_filter = Q(staff__role_type='part_time')
    elif current_staff and current_staff.role_type == 'user':
        # 利用者は自分のシフトのみ表示
        staff_filter = Q(staff=current_staff)
    else:
        # 対応するStaffオブジェクトがない場合は何も表示しない
        staff_filter = Q(pk__isnull=True)  # 何も取得しない条件
    
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    print(f"[DEBUG] Current organization: {current_organization}") # DEBUG
    print(f"[DEBUG] Querying shifts between {start_date} and {end_date} with staff filter") # DEBUG
    
    # 基本クエリ（日付範囲と承認状態）
    base_query = Shift.objects.filter(
        date__range=[start_date, end_date],
        approval_status__in=['approved', 'pending']
    )
    
    # 組織フィルタリング（スーパーユーザー以外は必須）
    if current_organization:
        base_query = base_query.filter(staff__organization=current_organization)
    elif not request.user.is_superuser:
        # 組織が選択されていない場合は空の結果を返す
        base_query = base_query.none()
    
    # 権限フィルタリングを適用
    shifts = base_query.filter(staff_filter).select_related('staff', 'shift_type')
    print(f"[DEBUG] Found {shifts.count()} shifts (approved + pending) with permission filter") # DEBUG
    
    events = []
    for shift in shifts:
        if shift.is_deleted_with_reason:
            # 事由付きの場合は灰色で表示
            events.append({
                'id': shift.id,
                'title': f'{shift.staff.name} ({shift.get_deletion_reason_display()})',
                'start': f'{shift.date.isoformat()}',  # 終日イベントとして表示
                'allDay': True,
                'color': '#6c757d',  # グレー
                'textColor': '#ffffff',
                'staff_id': shift.staff.id,
                'shift_type_id': None,
                'is_reason': True,
                'reason': shift.deletion_reason,
            })
        else:
            # 通常のシフトの場合
            # 承認状態に応じてタイトルと色を調整
            title_suffix = ""
            color = shift.shift_type.color if shift.shift_type else '#3498db'
            
            if shift.approval_status == 'pending':
                title_suffix = " [申請中]"
                # 承認待ちは色を薄くして点線で表示
                color = '#ffc107'  # 黄色系で承認待ちを表現
            
            events.append({
                'id': shift.id,
                'title': f'{shift.staff.name} ({shift.shift_type.name if shift.shift_type else "未設定"}){title_suffix}',
                'start': f'{shift.date.isoformat()}T{shift.start_time.isoformat()}',
                'end': f'{shift.date.isoformat()}T{shift.end_time.isoformat()}',
                'color': color,
                'staff_id': shift.staff.id,
                'shift_type_id': shift.shift_type.id if shift.shift_type else None,
                'is_reason': False,
                'approval_status': shift.approval_status,
                'is_pending': shift.approval_status == 'pending',
            })
    
    if events: # DEBUG
        print(f"[DEBUG] First event example: {events[0]}") # DEBUG
    else: # DEBUG
        print("[DEBUG] No events generated") # DEBUG
        
    return JsonResponse(events, safe=False)

@login_required
@require_POST
def api_shift_update(request):
    """ドラッグ＆ドロップでシフトを更新するAPI（新規追加）"""
    shift_id = request.POST.get('shift_id')
    new_date = request.POST.get('new_date')
    new_start_time = request.POST.get('new_start_time')
    new_end_time = request.POST.get('new_end_time')
    
    if not all([shift_id, new_date, new_start_time, new_end_time]):
        return JsonResponse({'error': '必要なパラメータが不足しています'}, status=400)
    
    try:
        shift = Shift.objects.get(pk=shift_id)
        shift.date = datetime.datetime.strptime(new_date, '%Y-%m-%d').date()
        
        # 時間の変換
        from django.utils.dateparse import parse_time
        shift.start_time = parse_time(new_start_time)
        shift.end_time = parse_time(new_end_time)
        
        shift.save()
        
        return JsonResponse({
            'success': True,
            'message': 'シフトを更新しました',
            'shift_id': shift.id,
            'date': shift.date.isoformat(),
            'start_time': shift.start_time.isoformat(),
            'end_time': shift.end_time.isoformat()
        })
    except Shift.DoesNotExist:
        return JsonResponse({'error': '指定されたシフトが見つかりません'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'エラーが発生しました: {str(e)}'}, status=500)

@require_POST
def api_shift_delete(request):
    """Ajax用シフト削除API"""
    # Ajaxリクエストかどうかを確認（Django 2.xとの互換性のため）
    is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
    if not is_ajax:
        return JsonResponse({'error': 'Ajaxリクエストのみ許可されています'}, status=400)
    
    # ログインチェック
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'ログインが必要です'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POSTメソッドのみ許可されています'}, status=405)
    
    shift_id = request.POST.get('shift_id')
    if not shift_id:
        return JsonResponse({'error': 'shift_idが指定されていません'}, status=400)
    
    try:
        shift = Shift.objects.get(pk=shift_id)
        
        # 権限チェック
        current_staff = get_staff_for_user(request.user)
        if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
            return JsonResponse({'error': 'シフト削除の権限がありません'}, status=403)
        
        shift.delete()
        return JsonResponse({'success': True, 'message': 'シフトを削除しました'})
    except Shift.DoesNotExist:
        return JsonResponse({'error': 'シフトが存在しません'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def time_chart(request):
    """時間チャート表示"""
    # 表示期間の設定（デフォルトは今月）
    today = timezone.now().date()
    year = today.year
    month = today.month
    
    # GETパラメータから期間を取得
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    if start_date_str and end_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            # 無効な日付の場合はデフォルトに戻す
            _, last_day = calendar.monthrange(year, month)
            start_date = datetime.date(year, month, 1)
            end_date = datetime.date(year, month, last_day)
    else:
        # デフォルトは今月
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, last_day)
    
    # 現在のユーザーに対応するStaffオブジェクトを取得
    current_staff = get_staff_for_user(request.user)
    
    # 権限に応じてスタッフ一覧を制限
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        # 管理者は全スタッフのシフトを表示
        staff_filter = Q()  # 制限なし
        staff_list = Staff.objects.filter(is_active=True).order_by('name')
    elif current_staff and current_staff.role_type == 'staff':
        # 職員は職員とアルバイトのシフトを表示
        staff_filter = Q(staff__role_type__in=['staff', 'part_time'])
        staff_list = Staff.objects.filter(is_active=True, role_type__in=['staff', 'part_time']).order_by('name')
    elif current_staff and current_staff.role_type == 'part_time':
        # アルバイトは同じアルバイトのシフトのみ表示
        staff_filter = Q(staff__role_type='part_time')
        staff_list = Staff.objects.filter(is_active=True, role_type='part_time').order_by('name')
    elif current_staff and current_staff.role_type == 'user':
        # 利用者は自分のシフトのみ表示
        staff_filter = Q(staff=current_staff)
        staff_list = Staff.objects.filter(id=current_staff.id).order_by('name')
    else:
        # 対応するStaffオブジェクトがない場合は何も表示しない
        staff_filter = Q(pk__isnull=True)  # 何も取得しない条件
        staff_list = Staff.objects.none()
    
    # 期間内のシフトを取得（承認済み + 承認待ち）（権限に応じて制限）
    shifts = Shift.objects.filter(
        date__range=[start_date, end_date],
        approval_status__in=['approved', 'pending'],  # 承認済み + 承認待ち
        is_deleted_with_reason=False  # 事由付きシフトは除外
    ).filter(staff_filter).select_related('staff', 'shift_type').order_by('date', 'start_time')
    
    # 日付リストを作成
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += datetime.timedelta(days=1)
    
    # 時間軸の設定（6:00から24:00まで）
    start_hour = 6
    end_hour = 24
    total_minutes = (end_hour - start_hour) * 60  # 18時間 = 1080分
    
    # 日付別のシフトデータを整理
    chart_data = {}
    for date in date_list:
        chart_data[date] = []
    
    # シフトデータを日付別に分類（重複対応）
    for shift in shifts:
        if shift.start_time and shift.end_time and shift.date in chart_data:
            # 開始時間と終了時間を分単位で計算（6:00を0分とする）
            start_minutes = max(0, (shift.start_time.hour - start_hour) * 60 + shift.start_time.minute)
            end_minutes = min(total_minutes, (shift.end_time.hour - start_hour) * 60 + shift.end_time.minute)
            
            # 有効な時間範囲内のシフトのみ追加
            if start_minutes < total_minutes and end_minutes > 0:
                # パーセンテージを計算
                left_percent = (start_minutes / total_minutes) * 100
                width_percent = ((end_minutes - start_minutes) / total_minutes) * 100
                
                # 重複レベルを計算（同じ時間帯にいるスタッフ数）
                overlap_level = 0
                for existing_shift in chart_data[shift.date]:
                    if (start_minutes < existing_shift['end_minutes'] and 
                        end_minutes > existing_shift['start_minutes']):
                        overlap_level += 1
                
                # 承認状態に応じて表示を調整
                display_name = shift.staff.name
                shift_type_name = shift.shift_type.name if shift.shift_type else '未設定'
                color = shift.shift_type.color if shift.shift_type else '#3498db'
                
                if shift.approval_status == 'pending':
                    display_name += " [申請中]"
                    shift_type_name += " [申請中]"
                    color = '#ffc107'  # 承認待ちは黄色
                
                chart_data[shift.date].append({
                    'staff_name': display_name,
                    'shift_type': shift_type_name,
                    'start_minutes': start_minutes,
                    'end_minutes': end_minutes,
                    'duration': end_minutes - start_minutes,
                    'left_percent': round(left_percent, 2),
                    'width_percent': round(width_percent, 2),
                    'color': color,
                    'start_time': shift.start_time,
                    'end_time': shift.end_time,
                    'overlap_level': overlap_level,  # 重複レベルを追加
                    'staff_id': shift.staff.id,  # スタッフIDを追加
                    'approval_status': shift.approval_status,
                    'is_pending': shift.approval_status == 'pending',
                })
    
    # 時間軸のラベルを作成
    time_labels = []
    for hour in range(start_hour, end_hour + 1):
        time_labels.append(f"{hour:02d}:00")
    
    # 統計情報を計算
    total_shifts = sum(len(chart_data[date]) for date in date_list)
    max_daily_shifts = max(len(chart_data[date]) for date in date_list) if date_list else 0
    avg_daily_shifts = round(total_shifts / len(date_list), 1) if date_list else 0
    
    # 時間別のシフト数を計算してピーク時間を特定
    hourly_counts = {}
    for hour in range(start_hour, end_hour):
        hourly_counts[f"{hour:02d}:00"] = 0
    
    for date in date_list:
        for shift in chart_data[date]:
            start_hour_shift = shift['start_time'].hour
            end_hour_shift = shift['end_time'].hour
            
            # シフトが含まれる時間帯をカウント
            for hour in range(max(start_hour, start_hour_shift), min(end_hour, end_hour_shift + 1)):
                hour_key = f"{hour:02d}:00"
                if hour_key in hourly_counts:
                    hourly_counts[hour_key] += 1
    
    # ピーク時間を特定
    peak_time = '-'
    if hourly_counts and max(hourly_counts.values()) > 0:
        peak_time = max(hourly_counts, key=hourly_counts.get)
    
    # フォーム用の初期値
    form_data = {
        'start_date': start_date,
        'end_date': end_date
    }
    
    context = {
        'chart_data': chart_data,
        'date_list': date_list,
        'time_labels': time_labels,
        'staff_list': staff_list,
        'form_data': form_data,
        'start_date': start_date,
        'end_date': end_date,
        'start_hour': start_hour,
        'end_hour': end_hour,
        'total_minutes': total_minutes,
        # 統計情報
        'max_staff_count': max_daily_shifts,
        'avg_staff_count': avg_daily_shifts,
        'peak_time': peak_time,
        'total_days': len(date_list),
        'total_shifts': total_shifts,
        'current_staff': current_staff,  # 現在のスタッフ情報を追加
        'user_role': current_staff.role_type if current_staff else 'none',  # ユーザーの権限種別を追加
    }
    
    return render(request, 'shift_management/time_chart.html', context)

@login_required
def staff_shift_view(request):
    """スタッフ用シフト確認ビュー（読み取り専用）"""
    # admin/superuserの場合は管理者カレンダーへリダイレクト
    if request.user.is_superuser or request.user.is_staff:
        return redirect('shift_management:calendar')
    
    # 現在の年月を取得（URLパラメータがあればそれを使用）
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # 月の最初と最後の日を取得
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    
    # カレンダー表示用の日付リストを作成
    calendar_days = []
    current_date = first_day
    
    # 月の最初の週の空白日を追加
    start_weekday = first_day.weekday()  # 0=月曜日, 6=日曜日
    # 日曜日を0にするため調整
    start_weekday = (start_weekday + 1) % 7
    
    for _ in range(start_weekday):
        calendar_days.append(None)
    
    # 月の日付を追加
    while current_date <= last_day:
        calendar_days.append(current_date)
        current_date += timedelta(days=1)
    
    # 週を完成させるため空白日を追加
    while len(calendar_days) % 7 != 0:
        calendar_days.append(None)
    
    # 週ごとにグループ化
    weeks = []
    for i in range(0, len(calendar_days), 7):
        weeks.append(calendar_days[i:i+7])
    
    # 該当月の承認済みシフトを取得
    shifts = Shift.objects.filter(
        date__range=[first_day, last_day],
        approval_status='approved'  # 承認済みのシフトのみ表示
    ).select_related('staff', 'shift_type').order_by('date', 'start_time')
    
    # 日付ごとにシフトをグループ化
    shifts_by_date = {}
    for shift in shifts:
        if shift.date not in shifts_by_date:
            shifts_by_date[shift.date] = []
        shifts_by_date[shift.date].append(shift)
    
    # 前月・次月の計算
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    
    context = {
        'year': year,
        'month': month,
        'weeks': weeks,
        'shifts_by_date': shifts_by_date,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'month_name': f'{year}年{month}月',
        'is_staff_view': True,  # スタッフビューフラグ
    }
    
    return render(request, 'shift_management/staff_calendar.html', context)

@login_required
def staff_shift_create(request):
    """スタッフ用シフト新規作成（自分のシフトのみ）"""
    # スタッフ自身のStaffオブジェクトを取得
    staff_obj = get_staff_for_user(request.user)
    if not staff_obj:
        messages.error(request, f'ユーザー名「{request.user.username}」に対応するスタッフ情報が見つかりません。管理者にお問い合わせください。')
        return redirect('shift_management:staff_view')
    
    if request.method == 'POST':
        form = StaffShiftForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            # スタッフを自分に固定
            shift.staff = staff_obj
            # スタッフが作成したシフトは承認待ち状態に設定
            shift.approval_status = 'pending'
            shift.created_by = request.user
            shift.save()
            messages.success(request, 'シフトを登録しました。管理者の承認をお待ちください。')
            return redirect('shift_management:staff_view')
    else:
        # GETパラメータから初期値を設定
        initial = {'staff': staff_obj.id}
        if 'date' in request.GET:
            initial['date'] = request.GET.get('date')
        
        form = StaffShiftForm(initial=initial)
    
    return render(request, 'shift_management/staff_shift_form.html', {
        'form': form, 
        'is_create': True,
        'staff_obj': staff_obj
    })

@login_required
def staff_shift_edit(request, pk):
    """スタッフ用シフト編集（自分のシフトのみ）"""
    # スタッフ自身のStaffオブジェクトを取得
    staff_obj = get_staff_for_user(request.user)
    if not staff_obj:
        messages.error(request, f'ユーザー名「{request.user.username}」に対応するスタッフ情報が見つかりません。管理者にお問い合わせください。')
        return redirect('shift_management:staff_view')
    
    # 自分のシフトのみ編集可能
    shift = get_object_or_404(Shift, pk=pk, staff=staff_obj)
    
    if request.method == 'POST':
        form = StaffShiftForm(request.POST, instance=shift)
        if form.is_valid():
            shift = form.save(commit=False)
            # スタッフを自分に固定
            shift.staff = staff_obj
            # 編集時は再度承認待ち状態に設定
            shift.approval_status = 'pending'
            shift.approved_at = None
            shift.approved_by = None
            shift.rejection_reason = ''
            shift.save()
            messages.success(request, 'シフトを更新しました。管理者の承認をお待ちください。')
            return redirect('shift_management:staff_view')
    else:
        form = StaffShiftForm(instance=shift)
    
    return render(request, 'shift_management/staff_shift_form.html', {
        'form': form, 
        'shift': shift,
        'is_create': False,
        'staff_obj': staff_obj
    })

@login_required
def staff_shift_delete(request, pk):
    """スタッフ用シフト削除（自分のシフトのみ）"""
    # スタッフ自身のStaffオブジェクトを取得
    staff_obj = get_staff_for_user(request.user)
    if not staff_obj:
        messages.error(request, f'ユーザー名「{request.user.username}」に対応するスタッフ情報が見つかりません。管理者にお問い合わせください。')
        return redirect('shift_management:staff_view')
    
    # 自分のシフトのみ削除可能
    shift = get_object_or_404(Shift, pk=pk, staff=staff_obj)
    
    if request.method == 'POST':
        shift.delete()
        messages.success(request, 'シフトを削除しました。')
        return redirect('shift_management:staff_view')
    
    return render(request, 'shift_management/staff_shift_delete.html', {
        'shift': shift,
        'staff_obj': staff_obj
    })

@login_required
def staff_api_shifts(request):
    """スタッフ用シフトデータAPI（編集可能）"""
    try:
        # パラメータを取得
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')
        
        if not start_date_str or not end_date_str:
            return JsonResponse({'error': '開始日と終了日が必要です'}, status=400)
        
        # 日付文字列をパース
        try:
            # ISO形式の日付文字列をパース
            start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).date()
            end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).date()
        except ValueError:
            # フォールバック: 別の形式を試す
            start_date = datetime.datetime.strptime(start_date_str[:10], '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str[:10], '%Y-%m-%d').date()
        
        # スタッフ自身のStaffオブジェクトを取得
        staff_obj = get_staff_for_user(request.user)
        if not staff_obj:
            return JsonResponse({'error': f'ユーザー名「{request.user.username}」に対応するスタッフ情報が見つかりません'}, status=400)
        
        # 現在選択中の組織を取得
        current_organization = get_current_organization(request)
        
        # 権限に応じてシフトデータを制限
        if request.user.is_superuser or staff_obj.role_type == 'manager':
            # 管理者は全スタッフのシフトを表示
            staff_filter = Q()
        elif staff_obj.role_type == 'staff':
            # 職員は職員とアルバイトのシフトを表示
            staff_filter = Q(staff__role_type__in=['staff', 'part_time'])
        elif staff_obj.role_type == 'part_time':
            # アルバイトは同じアルバイトのシフトのみ表示
            staff_filter = Q(staff__role_type='part_time')
        elif staff_obj.role_type == 'user':
            # 利用者は自分のシフトのみ表示
            staff_filter = Q(staff=staff_obj)
        else:
            # 不明な権限の場合は自分のシフトのみ
            staff_filter = Q(staff=staff_obj)
        
        # 基本クエリ（日付範囲と承認状態）
        base_query = Shift.objects.filter(
            date__range=[start_date, end_date],
            approval_status__in=['approved', 'pending'],  # 承認済み + 承認待ち
            is_deleted_with_reason=False,  # 事由付き削除されていないもののみ
            start_time__isnull=False,      # 開始時間があるもののみ
            end_time__isnull=False         # 終了時間があるもののみ
        )
        
        # 組織フィルタリング（スーパーユーザー以外は必須）
        if current_organization:
            base_query = base_query.filter(staff__organization=current_organization)
        elif not request.user.is_superuser:
            # 組織が選択されていない場合は空の結果を返す
            base_query = base_query.none()
        
        # 権限フィルタリングを適用して最終クエリを作成
        shifts = base_query.filter(staff_filter).select_related('staff', 'shift_type')
        
        # FullCalendar用のイベントデータを作成
        events = []
        for shift in shifts:
            # シフト種別の情報を取得
            if shift.shift_type:
                shift_type_name = shift.shift_type.name
                shift_color = shift.shift_type.color
            else:
                shift_type_name = '未設定'
                shift_color = '#6c757d'  # グレー色
            
            # 開始・終了時刻を組み合わせ
            start_datetime = datetime.datetime.combine(shift.date, shift.start_time)
            end_datetime = datetime.datetime.combine(shift.date, shift.end_time)
            
            # 自分のシフトかどうかを判定
            is_own_shift = shift.staff.id == staff_obj.id
            
            # 承認状態に応じてタイトルと色を調整
            title_suffix = ""
            if shift.approval_status == 'pending':
                title_suffix = " [申請中]"
                if is_own_shift:
                    # 自分の承認待ちシフトは黄色
                    shift_color = '#ffc107'
                else:
                    # 他人の承認待ちシフトは薄い色
                    shift_color = '#f8f9fa'
            
            event = {
                'id': shift.id,
                'title': f'{shift.staff.name} ({shift_type_name}){title_suffix}',
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'color': shift_color,
                'staff_id': shift.staff.id,
                'shift_type_id': shift.shift_type.id if shift.shift_type else None,
                'is_reason': False,
                'is_own_shift': is_own_shift,
                'approval_status': shift.approval_status,
                'is_pending': shift.approval_status == 'pending',
                'editable': is_own_shift and shift.approval_status == 'pending',  # 自分の承認待ちシフトのみ編集可能
                'startEditable': is_own_shift and shift.approval_status == 'pending',
                'durationEditable': is_own_shift and shift.approval_status == 'pending',
            }
            events.append(event)
        
        # 自分の事由データも取得（事由付きシフト）
        reason_shifts = Shift.objects.filter(
            staff=staff_obj,  # 自分の事由のみ
            date__range=[start_date, end_date],
            is_deleted_with_reason=True
        ).select_related('staff')
        
        for reason_shift in reason_shifts:
            # 事由の表示名を取得
            reason_display = dict(Shift.DELETION_REASON_CHOICES).get(reason_shift.deletion_reason, reason_shift.deletion_reason or 'その他')
            
            event = {
                'id': f'reason_{reason_shift.id}',
                'title': f'{reason_shift.staff.name} ({reason_display})',
                'start': reason_shift.date.isoformat(),
                'end': reason_shift.date.isoformat(),
                'color': '#e74c3c',
                'staff_id': reason_shift.staff.id,
                'is_reason': True,
                'allDay': True,
                'editable': False,  # 事由は編集不可
            }
            events.append(event)
        
        return JsonResponse(events, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': f'エラーが発生しました: {str(e)}'}, status=500)

# ヘルスチェック・監視用ビュー
def health_check(request):
    """
    システムヘルスチェック
    /health/ エンドポイントで使用
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'checks': {}
    }
    
    # データベース接続チェック
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['checks']['database'] = 'ok'
    except Exception as e:
        health_status['checks']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # キャッシュチェック
    try:
        from django.core.cache import cache
        cache_key = 'health_check_test'
        cache.set(cache_key, 'test_value', 30)
        cached_value = cache.get(cache_key)
        if cached_value == 'test_value':
            health_status['checks']['cache'] = 'ok'
        else:
            health_status['checks']['cache'] = 'error: cache not working'
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['cache'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # ディスク容量チェック
    try:
        from django.conf import settings
        disk_usage = os.statvfs(settings.BASE_DIR)
        free_space = disk_usage.f_bavail * disk_usage.f_frsize
        total_space = disk_usage.f_blocks * disk_usage.f_frsize
        usage_percent = ((total_space - free_space) / total_space) * 100
        
        if usage_percent > 90:
            health_status['checks']['disk'] = f'warning: {usage_percent:.1f}% used'
            health_status['status'] = 'degraded'
        else:
            health_status['checks']['disk'] = f'ok: {usage_percent:.1f}% used'
    except Exception as e:
        health_status['checks']['disk'] = f'error: {str(e)}'
    
    # ログディレクトリチェック
    try:
        from django.conf import settings
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        if os.path.exists(log_dir) and os.access(log_dir, os.W_OK):
            health_status['checks']['logs'] = 'ok'
        else:
            health_status['checks']['logs'] = 'error: log directory not writable'
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['logs'] = f'error: {str(e)}'
    
    # HTTPステータスコードを設定
    status_code = 200
    if health_status['status'] == 'unhealthy':
        status_code = 503
    elif health_status['status'] == 'degraded':
        status_code = 200  # 警告レベルは200で返す
    
    return JsonResponse(health_status, status=status_code)

def readiness_check(request):
    """
    レディネスチェック（アプリケーションが準備完了かどうか）
    /ready/ エンドポイントで使用
    """
    try:
        # 必要なテーブルが存在するかチェック
        from shift_management.models import Staff, ShiftType, Shift
        
        # 簡単なクエリを実行
        Staff.objects.exists()
        ShiftType.objects.exists()
        Shift.objects.exists()
        
        return JsonResponse({
            'status': 'ready',
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.datetime.now().isoformat()
        }, status=503)

def liveness_check(request):
    """
    Liveness probe - アプリケーションが生きているかチェック
    """
    try:
        # 簡単なデータベース接続チェック
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {
                'database': 'ok'
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=503)

@login_required
def api_pending_shifts(request):
    """承認待ちシフトを取得するAPI"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': '権限がありません'}, status=403)
    
    try:
        pending_shifts = Shift.objects.filter(
            approval_status='pending'
        ).select_related('staff', 'shift_type', 'created_by').order_by('-created_at')
        
        shifts_data = []
        for shift in pending_shifts:
            created_by_name = "システム"
            if shift.created_by:
                try:
                    # Staffモデルとの関連を確認
                    staff_obj = get_staff_for_user(shift.created_by)
                    if staff_obj:
                        created_by_name = f"{staff_obj.name} (スタッフ)"
                    else:
                        created_by_name = f"{shift.created_by.username} (管理者)"
                except Exception:
                    created_by_name = f"{shift.created_by.username} (管理者)"
            
            shifts_data.append({
                'id': shift.id,
                'staff_name': shift.staff.name,
                'date': shift.date.strftime('%Y-%m-%d'),
                'date_display': shift.date.strftime('%m月%d日'),
                'weekday': ['月', '火', '水', '木', '金', '土', '日'][shift.date.weekday()],
                'shift_type': shift.shift_type.name if shift.shift_type else '未設定',
                'shift_type_color': shift.shift_type.color if shift.shift_type else '#6c757d',
                'start_time': shift.start_time.strftime('%H:%M') if shift.start_time else '',
                'end_time': shift.end_time.strftime('%H:%M') if shift.end_time else '',
                'notes': shift.notes or '',
                'created_by': created_by_name,
                'created_at': shift.created_at.strftime('%Y-%m-%d %H:%M'),
            })
        
        return JsonResponse({
            'shifts': shifts_data,
            'count': len(shifts_data)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def api_approve_shift(request):
    """シフトを承認するAPI"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': '権限がありません'}, status=403)
    
    try:
        data = json.loads(request.body)
        shift_id = data.get('shift_id')
        
        if not shift_id:
            return JsonResponse({'error': 'シフトIDが必要です'}, status=400)
        
        shift = get_object_or_404(Shift, id=shift_id)
        
        if shift.approval_status != 'pending':
            return JsonResponse({'error': 'このシフトは既に処理済みです'}, status=400)
        
        # シフトを承認
        shift.approval_status = 'approved'
        shift.approved_at = timezone.now()
        shift.approved_by = request.user
        shift.rejection_reason = ''
        shift.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{shift.staff.name}さんの{shift.date.strftime("%m月%d日")}のシフトを承認しました',
            'shift': {
                'id': shift.id,
                'staff_name': shift.staff.name,
                'date_display': shift.date.strftime('%m月%d日'),
                'shift_type': shift.shift_type.name,
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': '無効なJSONデータです'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def api_reject_shift(request):
    """シフトを却下するAPI"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': '権限がありません'}, status=403)
    
    try:
        data = json.loads(request.body)
        shift_id = data.get('shift_id')
        rejection_reason = data.get('rejection_reason', '')
        
        if not shift_id:
            return JsonResponse({'error': 'シフトIDが必要です'}, status=400)
        
        shift = get_object_or_404(Shift, id=shift_id)
        
        if shift.approval_status != 'pending':
            return JsonResponse({'error': 'このシフトは既に処理済みです'}, status=400)
        
        # シフトを却下
        shift.approval_status = 'rejected'
        shift.approved_at = None
        shift.approved_by = None
        shift.rejection_reason = rejection_reason
        shift.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{shift.staff.name}さんの{shift.date.strftime("%m月%d日")}のシフトを却下しました',
            'shift': {
                'id': shift.id,
                'staff_name': shift.staff.name,
                'date_display': shift.date.strftime('%m月%d日'),
                'shift_type': shift.shift_type.name,
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': '無効なJSONデータです'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def api_bulk_approve_shifts(request):
    """複数のシフトを一括承認するAPI"""
    if not (request.user.is_superuser or request.user.is_staff):
        return JsonResponse({'error': '権限がありません'}, status=403)
    
    try:
        data = json.loads(request.body)
        shift_ids = data.get('shift_ids', [])
        
        if not shift_ids:
            return JsonResponse({'error': 'シフトIDが必要です'}, status=400)
        
        shifts = Shift.objects.filter(
            id__in=shift_ids,
            approval_status='pending'
        )
        
        approved_count = 0
        approved_shifts = []
        
        for shift in shifts:
            shift.approval_status = 'approved'
            shift.approved_at = timezone.now()
            shift.approved_by = request.user
            shift.rejection_reason = ''
            shift.save()
            approved_count += 1
            approved_shifts.append({
                'id': shift.id,
                'staff_name': shift.staff.name,
                'date_display': shift.date.strftime('%m月%d日'),
                'shift_type': shift.shift_type.name,
            })
        
        return JsonResponse({
            'success': True,
            'message': f'{approved_count}件のシフトを一括承認しました',
            'approved_shifts': approved_shifts,
            'count': approved_count
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': '無効なJSONデータです'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def has_organization_management_permission(user):
    """組織管理権限を持っているかチェック"""
    # 開発中は全てのログインユーザーに権限を付与
    return user.is_authenticated
    
    # 本番環境では以下のコメントを外す
    # # スーパーユーザーまたは組織管理専用アカウント
    # if user.is_superuser:
    #     return True
    # 
    # # 組織管理専用のスタッフアカウント（is_staffかつ特定の条件）
    # if user.is_staff and user.username in ['org_super_admin']:
    #     return True
    # 
    # # 組織の管理者アカウント（管理者権限を持つスタッフ）
    # try:
    #     staff = get_staff_for_user(user)
    #     if staff and staff.role_type == 'manager' and staff.approval_status == 'approved':
    #         return True
    # except:
    #     pass
    # 
    # return False

@login_required
def organization_list(request):
    """組織一覧表示（強化されたアクセス制御）"""
    if not has_organization_management_permission(request.user):
        messages.warning(request, '🔐 組織管理エリアにアクセスするには、組織管理者権限が必要です。')
        return redirect('shift_management:organization_admin_login')
    
    organizations = Organization.objects.all().order_by('name')
    
    # 検索機能
    search_query = request.GET.get('search', '')
    if search_query:
        organizations = organizations.filter(
            models.Q(name__icontains=search_query) |
            models.Q(code__icontains=search_query) |
            models.Q(contact_email__icontains=search_query)
        )
    
    # ページネーション
    paginator = Paginator(organizations, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_count': organizations.count(),
        'is_super_admin': request.user.is_superuser,
    }
    return render(request, 'shift_management/organization_list.html', context)

@login_required
def organization_create(request):
    """組織作成（強化されたアクセス制御）"""
    if not has_organization_management_permission(request.user):
        messages.warning(request, '🔐 組織作成には組織管理者権限が必要です。')
        return redirect('shift_management:organization_admin_login')
    
    if request.method == 'POST':
        form = OrganizationForm(request.POST)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'✅ 組織「{organization.name}」を作成しました。')
            return redirect('shift_management:organization_list')
    else:
        form = OrganizationForm()
    
    return render(request, 'shift_management/organization_form.html', {
        'form': form,
        'title': '組織作成',
        'action': '作成'
    })

@login_required
def organization_edit(request, pk):
    """組織編集（強化されたアクセス制御）"""
    if not has_organization_management_permission(request.user):
        messages.warning(request, '🔐 組織編集には組織管理者権限が必要です。')
        return redirect('shift_management:organization_admin_login')
    
    organization = get_object_or_404(Organization, pk=pk)
    
    if request.method == 'POST':
        form = OrganizationForm(request.POST, instance=organization)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'✅ 組織「{organization.name}」を更新しました。')
            return redirect('shift_management:organization_list')
    else:
        form = OrganizationForm(instance=organization)
    
    return render(request, 'shift_management/organization_form.html', {
        'form': form,
        'organization': organization,
        'title': '組織編集',
        'action': '更新'
    })

@login_required
def organization_detail(request, pk):
    """組織詳細表示（強化されたアクセス制御）"""
    if not has_organization_management_permission(request.user):
        messages.warning(request, '🔐 組織詳細閲覧には組織管理者権限が必要です。')
        return redirect('shift_management:organization_admin_login')
    
    organization = get_object_or_404(Organization, pk=pk)
    
    # 組織のスタッフ一覧
    staff_list = organization.staff_set.all().order_by('name')
    
    # 最近のシフト統計
    from datetime import datetime, timedelta
    today = date.today()
    start_date = today - timedelta(days=30)
    
    recent_shifts = Shift.objects.filter(
        staff__organization=organization,
        date__gte=start_date
    ).count()
    
    context = {
        'organization': organization,
        'staff_list': staff_list,
        'staff_count': staff_list.count(),
        'active_staff_count': staff_list.filter(is_active=True, approval_status='approved').count(),
        'recent_shifts_count': recent_shifts,
    }
    return render(request, 'shift_management/organization_detail.html', context)

@login_required
def organization_select(request):
    """組織選択画面"""
    if request.method == 'POST':
        form = OrganizationSelectForm(request.POST)
        if form.is_valid():
            organization = form.cleaned_data['organization']
            request.session['current_organization_id'] = organization.id
            request.session['current_organization_name'] = organization.name
            messages.success(request, f'組織「{organization.name}」を選択しました。')
            return redirect('shift_management:calendar')
    else:
        form = OrganizationSelectForm()
        # 現在選択中の組織があれば初期値として設定
        current_org_id = request.session.get('current_organization_id')
        if current_org_id:
            try:
                current_org = Organization.objects.get(id=current_org_id, is_active=True)
                form.fields['organization'].initial = current_org
            except Organization.DoesNotExist:
                pass
    
    return render(request, 'shift_management/organization_select.html', {
        'form': form,
        'current_organization_id': request.session.get('current_organization_id'),
        'current_organization_name': request.session.get('current_organization_name'),
    })

def get_current_organization(request):
    """現在選択中の組織を取得するヘルパー関数"""
    org_id = request.session.get('current_organization_id')
    if org_id:
        try:
            return Organization.objects.get(id=org_id, is_active=True)
        except Organization.DoesNotExist:
            # 無効な組織IDの場合はセッションをクリア
            if 'current_organization_id' in request.session:
                del request.session['current_organization_id']
            if 'current_organization_name' in request.session:
                del request.session['current_organization_name']
    return None

@login_required
def calendar_view(request):
    """カレンダー表示（組織フィルタリング対応）"""
    # 現在選択中の組織を取得
    current_organization = get_current_organization(request)
    
    # スーパーユーザー以外は組織選択が必須
    if not request.user.is_superuser and not current_organization:
        messages.info(request, '組織を選択してください。')
        return redirect('shift_management:organization_select')
    
    # 現在のユーザーに対応するスタッフを取得
    current_staff = get_staff_for_user(request.user)
    
    # 権限チェック
    user_role = 'admin' if request.user.is_superuser else (
        current_staff.role_type if current_staff else 'user'
    )
    
    # 組織に基づいてスタッフをフィルタリング
    if current_organization:
        staff_list = Staff.objects.filter(
            organization=current_organization,
            is_active=True,
            approval_status='approved'
        )
    else:
        # スーパーユーザーの場合は全組織
        staff_list = Staff.objects.filter(is_active=True, approval_status='approved')
    
    # 権限に応じてスタッフリストをさらにフィルタリング
    if current_staff and user_role != 'admin':
        filtered_staff_ids = []
        for staff in staff_list:
            if current_staff.can_view_staff_shifts(staff):
                filtered_staff_ids.append(staff.id)
        staff_list = staff_list.filter(id__in=filtered_staff_ids)
    
    # シフトデータを取得（組織フィルタリング適用）
    if current_organization:
        shifts = Shift.objects.filter(
            staff__organization=current_organization,
            approval_status='approved'
        ).select_related('staff', 'shift_type')
    else:
        shifts = Shift.objects.filter(
            approval_status='approved'
        ).select_related('staff', 'shift_type')
    
    # 権限に応じてシフトをフィルタリング
    if current_staff and user_role != 'admin':
        visible_staff_ids = [staff.id for staff in staff_list]
        shifts = shifts.filter(staff_id__in=visible_staff_ids)
    
    # シフト種別とテンプレートも組織でフィルタリング
    shift_types = ShiftType.objects.all()
    shift_templates = ShiftTemplate.objects.all()
    
    # 承認待ちのシフト（管理者のみ）
    pending_shifts = []
    if user_role in ['admin', 'manager']:
        if current_organization:
            pending_shifts = Shift.objects.filter(
                staff__organization=current_organization,
                approval_status='pending'
            ).select_related('staff', 'shift_type').order_by('-created_at')
        else:
            pending_shifts = Shift.objects.filter(
                approval_status='pending'
            ).select_related('staff', 'shift_type').order_by('-created_at')
    
    # 利用可能な組織一覧（スーパーユーザーまたは管理者の場合）
    available_organizations = []
    if request.user.is_superuser:
        available_organizations = Organization.objects.filter(is_active=True)
    elif current_staff and current_staff.role_type == 'manager':
        # 管理者は自分の組織のみ表示
        available_organizations = Organization.objects.filter(
            id=current_staff.organization.id, 
            is_active=True
        ) if current_staff.organization else []

    context = {
        'staff_list': staff_list,
        'shift_types': shift_types,
        'shifts': shifts,
        'shift_templates': shift_templates,
        'current_staff': current_staff,
        'user_role': user_role,
        'pending_shifts': pending_shifts,
        'current_organization': current_organization,
        'available_organizations': available_organizations,
        'can_edit': user_role in ['admin', 'manager'],
        'can_approve': user_role in ['admin', 'manager'],
    }
    
    return render(request, 'shift_management/calendar.html', context)

def organization_admin_login(request):
    """組織管理専用ログイン画面"""
    if request.user.is_authenticated and has_organization_management_permission(request.user):
        return redirect('shift_management:organization_list')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                # 組織管理権限をチェック
                if has_organization_management_permission(user):
                    login(request, user)
                    messages.success(
                        request, 
                        f'🔐 組織管理者として {username} でログインしました。'
                    )
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('shift_management:organization_list')
                else:
                    messages.error(request, '🚫 組織管理権限がありません。組織管理者またはスーパーアドミンのみアクセス可能です。')
            else:
                messages.error(request, '❌ ユーザー名またはパスワードが正しくありません。')
        else:
            messages.error(request, '❌ 入力内容に誤りがあります。')
    else:
        form = AuthenticationForm()
    
    return render(request, 'shift_management/organization_admin_login.html', {
        'form': form,
        'title': '組織管理者ログイン'
    })


# wakakusa-shift-2から移植した新機能

@login_required
def leave_request_list(request):
    """休み・通院申請一覧"""
    current_staff = get_staff_for_user(request.user)
    current_organization = get_current_organization(request)
    
    # 権限に応じて申請一覧を制限
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        # 管理者は組織内の全申請を表示
        if current_organization:
            leave_requests = LeaveRequest.objects.filter(staff__organization=current_organization)
        elif request.user.is_superuser:
            # スーパーユーザーは全組織の申請を表示
            leave_requests = LeaveRequest.objects.all()
        else:
            leave_requests = LeaveRequest.objects.none()
    elif current_staff:
        # 一般スタッフは自分の申請のみ
        leave_requests = LeaveRequest.objects.filter(staff=current_staff)
    else:
        leave_requests = LeaveRequest.objects.none()
    
    # ページネーション
    paginator = Paginator(leave_requests.select_related('staff', 'user', 'approved_by'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_staff': current_staff,
        'user_role': current_staff.role_type if current_staff else 'none',
    }
    
    return render(request, 'shift_management/leave_request_list.html', context)


@login_required
def leave_request_create(request):
    """休み・通院申請作成"""
    staff_obj = get_staff_for_user(request.user)
    if not staff_obj:
        messages.error(request, f'ユーザー名「{request.user.username}」に対応するスタッフ情報が見つかりません。')
        return redirect('shift_management:leave_request_list')
    
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.user = request.user
            leave_request.staff = staff_obj
            
            # 組織のフィルタリング（多組織対応）
            if staff_obj.organization:
                # 同じ組織の管理者のみに通知
                managers = User.objects.filter(
                    Q(is_superuser=True) |
                    Q(staff__organization=staff_obj.organization, staff__role_type='manager')
                ).distinct()
            else:
                # 組織が設定されていない場合はスーパーユーザーのみ
                managers = User.objects.filter(is_superuser=True)
            
            leave_request.save()
            
            # 管理者に通知を送信
            for manager in managers:
                create_notification(
                    recipient=manager,
                    notification_type='leave_request',
                    title='新しい休み申請があります',
                    message=f'{staff_obj.name}さんから{leave_request.get_request_type_display()}の申請が届いています。',
                    leave_request=leave_request
                )
            
            messages.success(request, '休み・通院申請を送信しました。管理者の承認をお待ちください。')
            return redirect('shift_management:leave_request_list')
    else:
        form = LeaveRequestForm()
    
    return render(request, 'shift_management/leave_request_form.html', {
        'form': form, 'staff_obj': staff_obj, 'is_create': True
    })


@login_required
def shift_proposal_list(request):
    """シフト打診一覧"""
    current_staff = get_staff_for_user(request.user)
    
    if request.user.is_superuser or (current_staff and current_staff.role_type == 'manager'):
        sent_proposals = ShiftProposal.objects.filter(proposed_by=request.user)
        received_proposals = ShiftProposal.objects.filter(proposed_to=current_staff) if current_staff else ShiftProposal.objects.none()
    elif current_staff:
        sent_proposals = ShiftProposal.objects.none()
        received_proposals = ShiftProposal.objects.filter(proposed_to=current_staff)
    else:
        sent_proposals = ShiftProposal.objects.none()
        received_proposals = ShiftProposal.objects.none()
    
    # user_roleの決定（スーパーユーザーは管理者扱い）
    if request.user.is_superuser:
        user_role = 'manager'
    elif current_staff:
        user_role = current_staff.role_type
    else:
        user_role = 'none'
    
    context = {
        'sent_proposals': sent_proposals.select_related('proposed_to', 'shift_type')[:10],
        'received_proposals': received_proposals.select_related('proposed_by', 'shift_type')[:10],
        'current_staff': current_staff,
        'user_role': user_role,
    }
    
    return render(request, 'shift_management/shift_proposal_list.html', context)


@login_required
def shift_proposal_create(request):
    """シフト打診作成（管理者権限のみ）"""
    current_staff = get_staff_for_user(request.user)
    
    # 管理者権限チェック（スーパーユーザーまたはmanager権限）
    if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
        messages.error(request, 'シフト打診の作成は管理者権限が必要です。')
        return redirect('shift_management:shift_proposal_list')
    
    if request.method == 'POST':
        form = ShiftProposalForm(request.POST)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.proposed_by = request.user
            proposal.save()
            
            # 打診先スタッフに通知（ユーザーアカウントがある場合のみ）
            if proposal.proposed_to.user:
                create_notification(
                    recipient=proposal.proposed_to.user,
                    notification_type='shift_proposal',
                    title='新しいシフト打診があります',
                    message=f'{proposal.shift_date}のシフトについて打診が届いています。',
                    shift_proposal=proposal
                )
            
            messages.success(request, f'{proposal.proposed_to.name}さんにシフト打診を送信しました。')
            return redirect('shift_management:shift_proposal_list')
    else:
        form = ShiftProposalForm()
        # 組織フィルタリング（実際にシフト勤務をするスタッフのみ対象）
        if current_staff and current_staff.organization:
            form.fields['proposed_to'].queryset = Staff.objects.filter(
                is_active=True,
                approval_status='approved',
                organization=current_staff.organization,
                role_type__in=['staff', 'part_time']  # 職員・アルバイトのみ
            )
    
    return render(request, 'shift_management/shift_proposal_form.html', {
        'form': form, 'is_create': True
    })


@login_required
def shift_proposal_respond(request, pk):
    """シフト打診回答"""
    proposal = get_object_or_404(ShiftProposal, pk=pk)
    current_staff = get_staff_for_user(request.user)
    
    # 打診先スタッフ本人のみアクセス可能
    if proposal.proposed_to != current_staff:
        messages.error(request, 'この打診への回答権限がありません。')
        return redirect('shift_management:shift_proposal_list')
    
    if request.method == 'POST':
        form = ShiftProposalResponseForm(request.POST, instance=proposal)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.responded_at = timezone.now()
            proposal.save()
            
            # 打診者に通知
            create_notification(
                recipient=proposal.proposed_by,
                notification_type=f'shift_proposal_{proposal.status}',
                title='シフト打診に回答がありました',
                message=f'{proposal.proposed_to.name}さんが{proposal.shift_date}のシフト打診に回答しました。',
                shift_proposal=proposal
            )
            
            messages.success(request, 'シフト打診に回答しました。')
            return redirect('shift_management:shift_proposal_list')
    else:
        form = ShiftProposalResponseForm(instance=proposal)
    
    return render(request, 'shift_management/shift_proposal_respond.html', {
        'form': form, 'proposal': proposal
    })


@login_required
def notification_list(request):
    """通知一覧"""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # ページネーション
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'shift_management/notification_list.html', {
        'page_obj': page_obj,
        'unread_count': notifications.filter(is_read=False).count()
    })


@login_required
def notification_mark_read(request, pk):
    """通知を既読にする"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('shift_management:notification_list')


@login_required
@require_POST
def api_mark_all_notifications_read(request):
    """全通知を既読にする"""
    updated_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({
        'success': True,
        'updated_count': updated_count
    })


@login_required
@require_POST
def api_approve_leave_request(request):
    """休暇申請を承認"""
    try:
        data = json.loads(request.body)
        leave_request = get_object_or_404(LeaveRequest, id=data['id'])
        
        # 権限チェック
        current_staff = get_staff_for_user(request.user)
        if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
            return JsonResponse({'success': False, 'error': '承認権限がありません'})
        
        leave_request.approval_status = 'approved'
        leave_request.approved_by = request.user
        leave_request.approved_at = timezone.now()
        leave_request.save()
        
        # 承認済み申請をシフトとしてカレンダーに反映
        create_shift_from_leave_request(leave_request)
        
        # 申請者に通知
        if leave_request.user:
            create_notification(
                recipient=leave_request.user,
                notification_type='leave_approved',
                title='休暇申請が承認されました',
                message=f'{leave_request.get_request_type_display()}の申請が承認されました。',
                leave_request=leave_request
            )
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def create_shift_from_leave_request(leave_request):
    """承認済み休み申請からシフトオブジェクトを作成してカレンダーに反映"""
    try:
        from datetime import timedelta
        
        # 休み用のシフト種別を取得または作成
        shift_type_name = leave_request.get_request_type_display()
        leave_shift_type, created = ShiftType.objects.get_or_create(
            name=shift_type_name,
            defaults={
                'color': '#dc3545' if leave_request.request_type == 'sick_leave' else '#28a745',
                'start_time': '00:00',
                'end_time': '23:59',
                'description': '休み申請による自動作成'
            }
        )
        
        # 期間中の各日に対してシフトを作成
        current_date = leave_request.start_date
        created_shifts = []
        
        while current_date <= leave_request.end_date:
            # 同じ日に既にシフトがある場合はスキップ
            existing_shift = Shift.objects.filter(
                staff=leave_request.staff,
                date=current_date
            ).first()
            
            if not existing_shift:
                shift = Shift.objects.create(
                    staff=leave_request.staff,
                    date=current_date,
                    start_time=leave_shift_type.start_time,
                    end_time=leave_shift_type.end_time,
                    shift_type=leave_shift_type,
                    approval_status='approved',
                    approved_by=leave_request.approved_by,
                    approved_at=leave_request.approved_at,
                    created_by=leave_request.approved_by,
                    notes=f'休み申請から自動作成: {leave_request.reason or shift_type_name}'
                )
                created_shifts.append(shift)
            
            current_date += timedelta(days=1)
        
        print(f"休み申請から{len(created_shifts)}件のシフトを作成しました")
        return created_shifts
            
    except Exception as e:
        print(f"シフト作成エラー: {e}")
        return []


@login_required
@require_POST
def api_reject_leave_request(request):
    """休暇申請を却下"""
    try:
        data = json.loads(request.body)
        leave_request = get_object_or_404(LeaveRequest, id=data['id'])
        
        # 権限チェック
        current_staff = get_staff_for_user(request.user)
        if not (request.user.is_superuser or (current_staff and current_staff.role_type == 'manager')):
            return JsonResponse({'success': False, 'error': '却下権限がありません'})
        
        leave_request.approval_status = 'rejected'
        leave_request.rejection_reason = data.get('reason', '')
        leave_request.save()
        
        # 申請者に通知
        if leave_request.user:
            create_notification(
                recipient=leave_request.user,
                notification_type='leave_rejected',
                title='休暇申請が却下されました',
                message=f'{leave_request.get_request_type_display()}の申請が却下されました。',
                leave_request=leave_request
            )
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def create_shift_from_leave_request(leave_request):
    """承認済み休み申請からシフトオブジェクトを作成してカレンダーに反映"""
    try:
        from datetime import timedelta
        
        # 休み用のシフト種別を取得または作成
        shift_type_name = leave_request.get_request_type_display()
        leave_shift_type, created = ShiftType.objects.get_or_create(
            name=shift_type_name,
            defaults={
                'color': '#dc3545' if leave_request.request_type == 'sick_leave' else '#28a745',
                'start_time': '00:00',
                'end_time': '23:59',
                'description': '休み申請による自動作成'
            }
        )
        
        # 期間中の各日に対してシフトを作成
        current_date = leave_request.start_date
        created_shifts = []
        
        while current_date <= leave_request.end_date:
            # 同じ日に既にシフトがある場合はスキップ
            existing_shift = Shift.objects.filter(
                staff=leave_request.staff,
                date=current_date
            ).first()
            
            if not existing_shift:
                shift = Shift.objects.create(
                    staff=leave_request.staff,
                    date=current_date,
                    start_time=leave_shift_type.start_time,
                    end_time=leave_shift_type.end_time,
                    shift_type=leave_shift_type,
                    approval_status='approved',
                    approved_by=leave_request.approved_by,
                    approved_at=leave_request.approved_at,
                    created_by=leave_request.approved_by,
                    notes=f'休み申請から自動作成: {leave_request.reason or shift_type_name}'
                )
                created_shifts.append(shift)
            
            current_date += timedelta(days=1)
        
        print(f"休み申請から{len(created_shifts)}件のシフトを作成しました")
        return created_shifts
            
    except Exception as e:
        print(f"シフト作成エラー: {e}")
        return []
@login_required
@require_POST
def organization_switch(request):
    """組織切り替えAPI"""
    try:
        data = json.loads(request.body)
        organization_id = data.get('organization_id')
        
        if organization_id:
            # 指定された組織に切り替え
            try:
                organization = Organization.objects.get(id=organization_id, is_active=True)
                request.session['current_organization_id'] = organization.id
                request.session['current_organization_name'] = organization.name
                
                return JsonResponse({
                    'success': True,
                    'organization_id': organization.id,
                    'organization_name': organization.name
                })
            except Organization.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': '指定された組織が見つかりません'
                })
        else:
            # 全組織表示（スーパーユーザーのみ）
            if request.user.is_superuser:
                request.session.pop('current_organization_id', None)
                request.session.pop('current_organization_name', None)
                
                return JsonResponse({
                    'success': True,
                    'organization_id': None,
                    'organization_name': '全ての組織'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': '権限がありません'
                })
                
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })