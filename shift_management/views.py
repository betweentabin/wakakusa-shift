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
from weasyprint import HTML, CSS
from .models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail
from .forms import (
    StaffForm, ShiftTypeForm, ShiftForm, ShiftTemplateForm, 
    ShiftTemplateDetailForm, DateRangeForm, TemplateApplyForm,
    BulkShiftForm, ShiftExportForm, ShiftReasonForm  # 新規追加フォーム
)
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
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
    """ログインビュー"""
    if request.user.is_authenticated:
        # 既にログイン済みの場合は権限に応じてリダイレクト
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
                messages.success(request, f'ようこそ、{username}さん！')
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                # 権限に応じてリダイレクト先を決定
                elif user.is_superuser or user.is_staff:
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
    return redirect('shift_management:login')

@login_required
def home_redirect(request):
    """ホームページリダイレクト - 権限に応じて適切なページにリダイレクト"""
    if request.user.is_superuser or request.user.is_staff:
        return redirect('shift_management:calendar')
    else:
        return redirect('shift_management:staff_view')

@login_required
def shift_calendar(request):
    """シフトカレンダー表示"""
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
    
    # 日付範囲内のシフトを取得
    shifts = Shift.objects.filter(date__range=[start_date, end_date]).select_related('staff', 'shift_type')
    
    # スタッフ一覧を取得
    staff_list = Staff.objects.filter(is_active=True)
    
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
    }
    
    return render(request, 'shift_management/calendar.html', context)

@login_required
def staff_list(request):
    """スタッフ一覧表示"""
    staffs = Staff.objects.all()
    return render(request, 'shift_management/staff_list.html', {'staffs': staffs})

@login_required
def staff_create(request):
    """スタッフ新規作成"""
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'スタッフを登録しました。')
            return redirect('shift_management:staff_list')
    else:
        form = StaffForm()
    
    return render(request, 'shift_management/staff_form.html', {'form': form, 'is_create': True})

@login_required
def staff_edit(request, pk):
    """スタッフ編集"""
    staff = get_object_or_404(Staff, pk=pk)
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
    if request.method == 'POST':
        staff.is_active = False
        staff.save()
        messages.success(request, 'スタッフを無効化しました。')
        return redirect('shift_management:staff_list')
    
    return render(request, 'shift_management/staff_delete.html', {'staff': staff})

@login_required
def shift_create(request):
    """シフト新規作成"""
    if request.method == 'POST':
        form = ShiftForm(request.POST)
        if form.is_valid():
            form.save()
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
        
        form = ShiftForm(initial=initial)
    
    return render(request, 'shift_management/shift_form.html', {'form': form, 'is_create': True})

@login_required
def shift_edit(request, pk):
    """シフト編集"""
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        form = ShiftForm(request.POST, instance=shift)
        if form.is_valid():
            form.save()
            messages.success(request, 'シフトを更新しました。')
            # カレンダー更新フラグを追加してリダイレクト
            return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    else:
        form = ShiftForm(instance=shift)
    
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
    if request.method == 'POST':
        form = BulkShiftForm(request.POST)
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
                            end_time=end_time
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
        
        form = BulkShiftForm(initial=initial)
    
    # シフト種別にデフォルト時間のデータ属性を追加
    for field in form.fields['shift_type'].choices:
        if hasattr(field, 'instance') and field.instance:
            field.attrs = {
                'data-start-time': field.instance.start_time.strftime('%H:%M'),
                'data-end-time': field.instance.end_time.strftime('%H:%M')
            }
    
    return render(request, 'shift_management/bulk_shift_form.html', {'form': form})

@login_required
def shift_type_list(request):
    """シフト種別一覧表示"""
    shift_types = ShiftType.objects.all()
    return render(request, 'shift_management/shift_type_list.html', {'shift_types': shift_types})

@login_required
def shift_type_create(request):
    """シフト種別新規作成"""
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
    """シフトテンプレート一覧表示"""
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
    """シフト表の印刷・エクスポート（新規追加）"""
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
            
            # シフトデータ取得
            shifts = Shift.objects.filter(
                date__range=[start_date, end_date],
                staff__in=staff_list
            ).select_related('staff', 'shift_type').order_by('date', 'start_time')
            
            # 日付範囲の全日付リスト作成
            date_list = []
            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date)
                current_date += datetime.timedelta(days=1)
            
            # 出力形式に応じた処理
            if format_type == 'pdf':
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
    
    print(f"[DEBUG] Querying shifts between {start_date} and {end_date}") # DEBUG
    shifts = Shift.objects.filter(date__range=[start_date, end_date]).select_related('staff', 'shift_type')
    print(f"[DEBUG] Found {shifts.count()} shifts") # DEBUG
    
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
            events.append({
                'id': shift.id,
                'title': f'{shift.staff.name} ({shift.shift_type.name if shift.shift_type else "未設定"})',
                'start': f'{shift.date.isoformat()}T{shift.start_time.isoformat()}',
                'end': f'{shift.date.isoformat()}T{shift.end_time.isoformat()}',
                'color': shift.shift_type.color if shift.shift_type else '#3498db',
                'staff_id': shift.staff.id,
                'shift_type_id': shift.shift_type.id if shift.shift_type else None,
                'is_reason': False,
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

@login_required
@require_POST
def api_shift_delete(request):
    """Ajax用シフト削除API"""
    shift_id = request.POST.get('shift_id')
    if not shift_id:
        return JsonResponse({'error': 'shift_idが指定されていません'}, status=400)
    try:
        shift = Shift.objects.get(pk=shift_id)
        shift.delete()
        return JsonResponse({'success': True})
    except Shift.DoesNotExist:
        return JsonResponse({'error': 'シフトが存在しません'}, status=404)

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
    
    # 期間内のシフトを取得
    shifts = Shift.objects.filter(
        date__range=[start_date, end_date],
        is_deleted_with_reason=False  # 事由付きシフトは除外
    ).select_related('staff', 'shift_type').order_by('date', 'start_time')
    
    # スタッフ一覧を取得
    staff_list = Staff.objects.filter(is_active=True).order_by('name')
    
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
    
    # シフトデータを日付別に分類
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
                
                chart_data[shift.date].append({
                    'staff_name': shift.staff.name,
                    'shift_type': shift.shift_type.name if shift.shift_type else '未設定',
                    'start_minutes': start_minutes,
                    'end_minutes': end_minutes,
                    'duration': end_minutes - start_minutes,
                    'left_percent': round(left_percent, 2),
                    'width_percent': round(width_percent, 2),
                    'color': shift.shift_type.color if shift.shift_type else '#3498db',
                    'start_time': shift.start_time,
                    'end_time': shift.end_time,
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
    }
    
    return render(request, 'shift_management/time_chart.html', context)

@login_required
def staff_shift_view(request):
    """スタッフ用シフト確認ビュー（読み取り専用）"""
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
    
    # 該当月のシフトを取得
    shifts = Shift.objects.filter(
        date__range=[first_day, last_day]
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
        form = ShiftForm(request.POST)
        if form.is_valid():
            shift = form.save(commit=False)
            # スタッフを自分に固定
            shift.staff = staff_obj
            shift.save()
            messages.success(request, 'シフトを登録しました。')
            return redirect('shift_management:staff_view')
    else:
        # GETパラメータから初期値を設定
        initial = {'staff': staff_obj.id}
        if 'date' in request.GET:
            initial['date'] = request.GET.get('date')
        
        form = ShiftForm(initial=initial)
        # スタッフフィールドを非表示にして自分に固定
        form.fields['staff'].widget = forms.HiddenInput()
        form.fields['staff'].initial = staff_obj.id
    
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
        form = ShiftForm(request.POST, instance=shift)
        if form.is_valid():
            shift = form.save(commit=False)
            # スタッフを自分に固定
            shift.staff = staff_obj
            shift.save()
            messages.success(request, 'シフトを更新しました。')
            return redirect('shift_management:staff_view')
    else:
        form = ShiftForm(instance=shift)
        # スタッフフィールドを非表示にして自分に固定
        form.fields['staff'].widget = forms.HiddenInput()
        form.fields['staff'].initial = staff_obj.id
    
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
        
        # 全スタッフのシフトデータを取得（通常のシフトのみ）
        shifts = Shift.objects.filter(
            date__range=[start_date, end_date],
            is_deleted_with_reason=False,  # 事由付き削除されていないもののみ
            start_time__isnull=False,      # 開始時間があるもののみ
            end_time__isnull=False         # 終了時間があるもののみ
        ).select_related('staff', 'shift_type')
        
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
            
            event = {
                'id': shift.id,
                'title': f'{shift.staff.name} ({shift_type_name})',
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'color': shift_color,
                'staff_id': shift.staff.id,
                'shift_type_id': shift.shift_type.id if shift.shift_type else None,
                'is_reason': False,
                'is_own_shift': is_own_shift,
                'editable': is_own_shift,  # 自分のシフトのみ編集可能
                'startEditable': is_own_shift,
                'durationEditable': is_own_shift,
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
    ライブネスチェック（アプリケーションが生きているかどうか）
    /live/ エンドポイントで使用
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': datetime.datetime.now().isoformat()
    })
