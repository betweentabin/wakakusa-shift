from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse
from django.template.loader import render_to_string
import json
import datetime
import calendar
import csv
from io import StringIO
import tempfile
import os
from weasyprint import HTML, CSS
from .models import Staff, ShiftType, Shift, ShiftTemplate, ShiftTemplateDetail
from .forms import (
    StaffForm, ShiftTypeForm, ShiftForm, ShiftTemplateForm, 
    ShiftTemplateDetailForm, DateRangeForm, TemplateApplyForm,
    BulkShiftForm, ShiftExportForm  # 新規追加フォーム
)

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

def staff_list(request):
    """スタッフ一覧表示"""
    staffs = Staff.objects.all()
    return render(request, 'shift_management/staff_list.html', {'staffs': staffs})

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

def staff_delete(request, pk):
    """スタッフ削除"""
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == 'POST':
        staff.is_active = False
        staff.save()
        messages.success(request, 'スタッフを無効化しました。')
        return redirect('shift_management:staff_list')
    
    return render(request, 'shift_management/staff_delete.html', {'staff': staff})

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

def shift_delete(request, pk):
    """シフト削除"""
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == 'POST':
        shift.delete()
        messages.success(request, 'シフトを削除しました。')
        # カレンダー更新フラグを追加してリダイレクト
        return redirect(f"{reverse('shift_management:calendar')}?refresh_calendar=true")
    
    return render(request, 'shift_management/shift_delete.html', {'shift': shift})

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

def shift_type_list(request):
    """シフト種別一覧表示"""
    shift_types = ShiftType.objects.all()
    return render(request, 'shift_management/shift_type_list.html', {'shift_types': shift_types})

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

def shift_type_delete(request, pk):
    """シフト種別削除"""
    shift_type = get_object_or_404(ShiftType, pk=pk)
    if request.method == 'POST':
        shift_type.delete()
        messages.success(request, 'シフト種別を削除しました。')
        return redirect('shift_management:shift_type_list')
    
    return render(request, 'shift_management/shift_type_delete.html', {'shift_type': shift_type})

def template_list(request):
    """シフトテンプレート一覧表示"""
    templates = ShiftTemplate.objects.all()
    return render(request, 'shift_management/template_list.html', {'templates': templates})

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

def template_delete(request, pk):
    """シフトテンプレート削除"""
    template = get_object_or_404(ShiftTemplate, pk=pk)
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'シフトテンプレートを削除しました。')
        return redirect('shift_management:template_list')
    
    return render(request, 'shift_management/template_delete.html', {'template': template})

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

def api_shifts(request):
    """シフトデータをJSON形式で返すAPI"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if not start_date or not end_date:
        return JsonResponse({'error': '開始日と終了日を指定してください'}, status=400)
    
    try:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': '日付形式が正しくありません'}, status=400)
    
    shifts = Shift.objects.filter(date__range=[start_date, end_date]).select_related('staff', 'shift_type')
    
    events = []
    for shift in shifts:
        events.append({
            'id': shift.id,
            'title': f'{shift.staff.name} ({shift.shift_type.name if shift.shift_type else "未設定"})',
            'start': f'{shift.date.isoformat()}T{shift.start_time.isoformat()}',
            'end': f'{shift.date.isoformat()}T{shift.end_time.isoformat()}',
            'color': shift.shift_type.color if shift.shift_type else '#3498db',
            'staff_id': shift.staff.id,
            'shift_type_id': shift.shift_type.id if shift.shift_type else None,
        })
    
    return JsonResponse(events, safe=False)

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
