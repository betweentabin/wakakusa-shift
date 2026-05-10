from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse
import json
from urllib.parse import urlencode
from .models import CultivationLayout, CultivationSection, CultivationPlan, CultivationLog, Crop, Plot, ShelfCrop, CultivationAlert, HarvestTarget
from .forms import CultivationLayoutForm, CultivationPlanForm, CultivationLogForm, PlotForm, ShelfCropForm, CultivationSectionForm, CropImageForm, CropForm, PlotInlineForm, BulkAddLanesForm
from .utils import process_import_file
from shift_management.views import get_current_organization
from shift_management.utils import filter_by_organization, is_global_admin

def get_plot_level_details(plot):
    """棚の各レベルの詳細情報を取得する共通ヘルパー関数"""
    crops_by_level = plot.get_crops_by_level()
    level_details = []

    for level in range(1, plot.levels + 1):
        level_crops = crops_by_level.get(level, [])
        level_info = {
            'level': level,
            'status': 'empty',
            'crop_name': '空き',
            'crop': None,
            'crop_id': None,
            'plate_count': 0,
            'days_until_harvest': None,
            'progress_percentage': None,
            'sowing_date': None,
            'pre_planting_date': None,
            'planting_date': None,
            'expected_harvest_date': None,
        }

        if level_crops:
            crop = level_crops[0]  # 最新の作物
            growth_status = crop.get_growth_status()
            level_info['crop'] = crop
            level_info['crop_id'] = crop.id
            level_info['crop_name'] = crop.variety
            level_info['plate_count'] = crop.plate_count
            level_info['sowing_date'] = crop.sowing_date.isoformat() if crop.sowing_date else None
            level_info['pre_planting_date'] = crop.pre_planting_date.isoformat() if crop.pre_planting_date else None
            level_info['planting_date'] = crop.planting_date.isoformat() if crop.planting_date else None
            level_info['expected_harvest_date'] = crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None

            # get_growth_status() の値をそのまま使用
            level_info['status'] = growth_status

            if crop.days_until_harvest() is not None:
                level_info['days_until_harvest'] = crop.days_until_harvest()
                level_info['progress_percentage'] = crop.growth_progress_percentage()

        # レベルごとの色を設定
        status_colors = {
            'empty': '#f5f5f5',
            'sowing': '#eceff1',
            'pre_planted': '#fff9c4',
            'planted': '#c8e6c9',
            'harvest_ready': '#ffe0b2',
            'harvested': '#eeeeee',
        }
        level_info['color'] = status_colors.get(level_info['status'], '#f5f5f5')

        level_details.append(level_info)

    return level_details

# Create your views here.

def is_admin_user(user):
    """管理者権限をチェックする関数"""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True

    from shift_management.models import Staff
    return Staff.objects.filter(
        user=user,
        role_type__in=['manager', 'global_admin'],
        is_active=True,
        approval_status='approved',
    ).exists()


def redirect_to_organization_select(request):
    """組織選択後に元の栽培管理ページへ戻す"""
    url = reverse('shift_management:organization_select')
    return redirect(f'{url}?{urlencode({"next": request.get_full_path()})}')


def crop_queryset_for_organization(organization):
    """現在組織で利用できる作物マスタを返す"""
    crops = Crop.objects.all()
    if organization:
        crops = crops.filter(Q(organization=organization) | Q(organization__isnull=True))
    return crops.order_by('name')


def build_excel_floor_plan_rows(floor_plan_data):
    """Excelのレーン表に近い行列データを作る"""
    plots = sorted(
        floor_plan_data.get('plots', []),
        key=lambda item: (
            item.get('plot', {}).get('y_position') or 0,
            item.get('plot', {}).get('x_position') or 0,
            item.get('shelf_number') or '',
        )
    )

    rows = []
    current_y = object()
    current_row = None
    for plot_info in plots:
        y_position = plot_info.get('plot', {}).get('y_position') or 0
        if y_position != current_y:
            current_y = y_position
            current_row = {
                'y_position': y_position,
                'plots': [],
            }
            rows.append(current_row)
        current_row['plots'].append(plot_info)

    max_columns = max((len(row['plots']) for row in rows), default=3)
    return rows, max(max_columns, 3)


def apply_floor_plan_crop_info(level_info, crop):
    """棚配置平面図向けに段ごとの作物表示情報を追加する"""
    status_labels = {
        'empty': '空き',
        'sowing': '播種',
        'pre_planted': '仮植',
        'planted': '定植',
        'harvest_ready': '収穫',
        'harvested': '収穫済',
        'overdue': '期限超過',
    }

    if not crop:
        level_info.update({
            'crop_id': None,
            'plate_count': 0,
            'stage_status': 'empty',
            'status_label': status_labels['empty'],
            'today_actions': [],
            'date_items': [],
        })
        return level_info

    stage_status = crop.get_growth_status()
    if crop.days_overdue() > 0:
        stage_status = 'overdue'

    today_actions = crop.is_today_action()
    action_labels = []
    if today_actions['is_sowing_today']:
        action_labels.append('播種')
    if today_actions['is_pre_planting_today']:
        action_labels.append('仮植')
    if today_actions['is_planting_today']:
        action_labels.append('定植')
    if today_actions['is_harvest_today']:
        action_labels.append('収穫')

    date_items = [
        {'label': '播', 'date': crop.sowing_date},
        {'label': '仮', 'date': crop.pre_planting_date},
        {'label': '定', 'date': crop.planting_date},
        {'label': '収', 'date': crop.expected_harvest_date},
    ]

    level_info.update({
        'crop_id': crop.id,
        'crop_name': crop.variety,
        'plate_count': crop.plate_count,
        'stage_status': stage_status,
        'status_label': status_labels.get(stage_status, '栽培中'),
        'today_actions': action_labels,
        'has_today_action': today_actions['any'],
        'date_items': date_items,
        'sowing_date': crop.sowing_date,
        'pre_planting_date': crop.pre_planting_date,
        'planting_date': crop.planting_date,
        'expected_harvest_date': crop.expected_harvest_date,
    })
    return level_info

@login_required(login_url='/login/')
def cultivation_top(request):
    """栽培計画トップページ"""
    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # 組織フィルタリング
    if is_global_admin(request.user):
        layouts = CultivationLayout.objects.all()
    elif current_organization:
        layouts = CultivationLayout.objects.filter(organization=current_organization)
    else:
        layouts = CultivationLayout.objects.none()

    layouts = layouts.order_by('-created_at')
    
    # 全体統計を計算
    total_layouts = layouts.count()
    total_plots = 0
    total_levels = 0
    active_crops = 0
    harvest_ready = 0
    overdue_crops = 0
    
    # 各レイアウトの統計も計算
    for layout in layouts:
        # 棚区画システムの統計を使用
        try:
            plots = layout.plots.all()
            plots_count = plots.count()
            
            # 比較用：直接クエリでも確認
            direct_plots = Plot.objects.filter(layout=layout)
            direct_count = direct_plots.count()
            
            
            # 直接クエリの結果を使用
            plots = direct_plots
            plots_count = direct_count
            
        except AttributeError:
            plots = []
            plots_count = 0
        
        # 作物統計を初期化
        active_crops_count = 0
        harvest_ready_count = 0
        empty_levels_count = 0
        levels_count = 0
        overdue_count = 0
        
        plots_with_details = []
        for plot in plots:
            levels_count += plot.levels

            # 共通ヘルパー関数を使用してレベル詳細を取得
            level_details = get_plot_level_details(plot)

            # プロットに詳細情報を追加（ミニ棚グリッド用）
            plot.level_details = level_details
            plots_with_details.append(plot)

            # 統計カウント
            for level_info in level_details:
                if level_info['status'] == 'empty':
                    empty_levels_count += 1
                elif level_info['status'] in ('planted', 'pre_planted', 'sowing'):
                    active_crops_count += 1
                elif level_info['status'] == 'harvest_ready':
                    harvest_ready_count += 1

        # レイアウトに統計情報を追加
        layout.plots_count = plots_count
        layout.total_levels = levels_count
        layout.active_crops_count = active_crops_count
        layout.harvest_ready_count = harvest_ready_count
        layout.empty_levels_count = empty_levels_count
        layout.overdue_count = overdue_count
        layout.plots_with_details = plots_with_details
        
        # 全体統計に加算
        total_plots += plots_count
        total_levels += levels_count
        active_crops += active_crops_count
        harvest_ready += harvest_ready_count
        overdue_crops += overdue_count
    
    context = {
        'layouts': layouts,
        'total_layouts': total_layouts,
        'total_plots': total_plots,
        'total_levels': total_levels,
        'active_crops': active_crops,
        'harvest_ready': harvest_ready,
        'overdue_crops': overdue_crops,
    }
    return render(request, 'cultivation/cultivation_top.html', context)

@login_required(login_url='/login/')
def layout_list(request):
    """栽培レイアウト一覧 → cultivation_top に統合済み"""
    return redirect('cultivation:cultivation_top')


def _layout_list_unused(request):
    """（参照用）旧レイアウト一覧ビュー"""
    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # 組織フィルタリング
    if is_global_admin(request.user):
        layouts = CultivationLayout.objects.all()
    elif current_organization:
        layouts = CultivationLayout.objects.filter(organization=current_organization)
    else:
        layouts = CultivationLayout.objects.none()

    layouts = layouts.order_by('-created_at')
    
    # 各レイアウトの統計も計算
    for layout in layouts:
        # 棚区画システムの統計を使用
        try:
            plots = layout.plots.all()
            plots_count = plots.count()
            
            # 比較用：直接クエリでも確認
            direct_plots = Plot.objects.filter(layout=layout)
            direct_count = direct_plots.count()
            
            
            # 直接クエリの結果を使用
            plots = direct_plots
            plots_count = direct_count
            
        except AttributeError:
            plots = []
            plots_count = 0
        
        # 作物統計を初期化
        active_crops_count = 0
        harvest_ready_count = 0
        empty_levels_count = 0
        total_levels = 0
        overdue_count = 0
        
        # plots_with_detailsを初期化
        plots_with_details = []
        
        for plot in plots:
            total_levels += plot.levels
            
            # 共通ヘルパー関数を使用してレベル詳細を取得
            level_details = get_plot_level_details(plot)
            
            # プロットに詳細情報を追加
            plot.level_details = level_details
            plots_with_details.append(plot)
            
            # 統計カウント（棚区画管理ページと同じロジック）
            for level_info in level_details:
                if level_info['status'] == 'empty':
                    empty_levels_count += 1
                elif level_info['status'] == 'growing':
                    active_crops_count += 1
                elif level_info['status'] == 'harvest_ready':
                    harvest_ready_count += 1
                elif level_info['status'] == 'overdue':
                    overdue_count += 1
        
        # レイアウトに統計情報を追加
        layout.plots_count = plots_count
        layout.total_levels = total_levels
        layout.active_crops_count = active_crops_count
        layout.harvest_ready_count = harvest_ready_count
        layout.empty_levels_count = empty_levels_count
        layout.overdue_count = overdue_count
        layout.plots_with_details = plots_with_details
        
    
    context = {
        'layouts': layouts,
        'total_layouts': layouts.count(),
    }
    return render(request, 'cultivation/layout_list.html', context)

@login_required(login_url='/login/')
def layout_create(request):
    """改良されたレイアウト作成"""
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    if request.method == 'POST':
        form = CultivationLayoutForm(request.POST, request.FILES)
        if form.is_valid():
            layout = form.save(commit=False)
            layout.organization = current_organization  # 組織を自動設定
            layout.save()
            
            # 共通変数を初期化
            ocr_processed = False
            enable_ocr = False
            ocr_data = None
            
            # テンプレートが選択されている場合、自動的に区画を作成
            template_type = request.POST.get('template_type')
            if template_type:
                created_count = create_sections_from_template(layout, template_type)
                if created_count > 0:
                    messages.success(request, f'レイアウト「{layout.name}」を作成し、{created_count}個の区画を自動生成しました')
                else:
                    messages.success(request, f'レイアウト「{layout.name}」を作成しました')
                # テンプレート処理ではOCRは使用しない
                ocr_processed = False
                enable_ocr = False
            else:
                # OCR機能が有効化されているかチェック
                enable_ocr = form.cleaned_data.get('enable_ocr', False)
                ocr_file = form.cleaned_data.get('ocr_file')
                auto_generate = form.cleaned_data.get('auto_generate_sections', True)
                confidence_threshold = form.cleaned_data.get('ocr_confidence_threshold', 70)
                
                # 変数を再初期化（既に上で初期化済み）
                ocr_result = None
                
                if enable_ocr and ocr_file:
                    # OCR処理実行
                    ocr_data = process_ocr_file_preview(ocr_file, confidence_threshold)
                    
                    if ocr_data.get('success'):
                        ocr_processed = True
                        ocr_result = ocr_data
                    
                    # auto_generateがTrueの場合、区画を自動生成
                    if auto_generate:
                        # OCR結果から区画を生成
                        try:
                            sections_created = 0
                            existing_positions = set()
                            
                            # 既存区画の位置を記録（重複防止）
                            for section in layout.sections.all():
                                existing_positions.add((section.row, section.column))
                            
                            # OCR結果からシェルフ情報を抽出して区画を作成
                            pages = ocr_data.get('pages', [])
                            shelf_positions = {}  # 棚番号から位置へのマッピング
                            
                            for page in pages:
                                shelf_info_list = page.get('shelf_info', [])
                                
                                # 棚情報をグリッド位置に変換
                                for idx, shelf_info in enumerate(shelf_info_list):
                                    shelf_number = shelf_info.get('shelf_number', '')
                                    if shelf_number:
                                        # 簡単なグリッド配置ロジック（実際のレイアウトに応じて調整）
                                        # 行と列を計算（例：10列のグリッド）
                                        columns_per_row = 10
                                        row = (idx // columns_per_row) + 1
                                        column = (idx % columns_per_row) + 1
                                        
                                        # 既に存在する位置は避ける
                                        while (row, column) in existing_positions:
                                            column += 1
                                            if column > columns_per_row:
                                                column = 1
                                                row += 1
                                        
                                        try:
                                            section = CultivationSection.objects.create(
                                                layout=layout,
                                                name=shelf_number,
                                                row=row,
                                                column=column
                                            )
                                            sections_created += 1
                                            existing_positions.add((row, column))
                                            shelf_positions[shelf_number] = (row, column)
                                        except Exception as e:
                                            messages.warning(request, f'区画 {shelf_number} の作成に失敗: {str(e)}')
                            
                            if sections_created > 0:
                                messages.success(request, f'レイアウト「{layout.name}」を作成し、{sections_created}個の区画をOCRから自動生成しました')
                            else:
                                messages.warning(request, f'レイアウトは作成されましたが、OCRから区画を生成できませんでした')
                                
                        except Exception as e:
                            messages.warning(request, f'レイアウトは作成されましたが、区画の自動生成でエラーが発生しました: {str(e)}')
                    else:
                        messages.success(request, f'レイアウト「{layout.name}」を作成しました（OCR処理済み）')
                else:
                    error_msg = ocr_data.get("error", "不明なエラー") if ocr_data else "OCR処理でエラーが発生しました"
                    messages.warning(request, f'レイアウトは作成されましたが、OCR処理でエラーが発生しました: {error_msg}')
            
            # インポートファイルが指定されている場合は処理（OCRと併用可能）
            if layout.import_file:
                file_path = layout.import_file.path
                success, message = process_import_file(layout, file_path)
                
                if success:
                    messages.success(request, f'レイアウト「{layout.name}」を作成し、{message}')
                else:
                    messages.warning(request, f'レイアウトは作成されましたが、ファイル処理でエラーが発生しました: {message}')
            else:
                messages.success(request, f'レイアウト「{layout.name}」を作成しました')
            
            # OCR処理が成功した場合、プレビューページへリダイレクト
            if ocr_processed and enable_ocr:
                return redirect('cultivation:layout_preview_with_layout', layout_id=layout.id)
            else:
                return redirect('cultivation:cultivation_top')
    else:
        form = CultivationLayoutForm()
    
    context = {
        'form': form,
    }
    return render(request, 'cultivation/layout_create_simple_improved.html', context)

def create_sections_from_template(layout, template_type):
    """テンプレートに基づいて区画を自動作成"""
    templates = {
        'small-grid': {'rows': 2, 'cols': 3, 'pattern': 'simple'},
        'medium-grid': {'rows': 3, 'cols': 4, 'pattern': 'simple'},
        'large-grid': {'rows': 4, 'cols': 5, 'pattern': 'simple'},
        'greenhouse': {'rows': 2, 'cols': 6, 'pattern': 'greenhouse'},
    }
    
    if template_type not in templates:
        return 0
    
    template = templates[template_type]
    rows = template['rows']
    cols = template['cols']
    pattern = template['pattern']
    
    created_count = 0
    
    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            # 温室パターンの場合、中央に通路を作る
            if pattern == 'greenhouse' and col in [3, 4]:
                continue
            
            section_name = f"区画-{row}-{col}"
            if pattern == 'greenhouse':
                section_name = f"{chr(64 + row)}{col if col < 3 else col - 2}"
            
            try:
                CultivationSection.objects.create(
                    layout=layout,
                    name=section_name,
                    row=row,
                    column=col,
                    description=f"テンプレートから自動作成された区画"
                )
                created_count += 1
            except Exception:
                pass  # 重複などのエラーは無視
    
    return created_count

@login_required(login_url='/login/')
def layout_create_simple(request):
    """シンプルなレイアウト作成 → layout_create に統合済み"""
    return redirect('cultivation:layout_create')

@login_required(login_url='/login/')
def layout_detail(request, layout_id):
    """レイアウト詳細表示 - 区画または棚区画2D/3D平面図を表示"""
    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    # layout_idをクエリパラメータとして設定し、plot_grid_viewを呼び出す
    request.GET = request.GET.copy()
    request.GET['layout'] = layout_id
    request.GET['mode'] = 'floor_plan'

    # 表示タイプを決定（棚区画を優先）
    try:
        layout = get_object_or_404(CultivationLayout, id=layout_id)

        # 組織チェック：グローバル管理者でない場合、自組織のレイアウトのみ表示可能
        if not is_global_admin(request.user) and current_organization:
            if layout.organization != current_organization:
                messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                return redirect('cultivation:cultivation_top')

        plots = Plot.objects.filter(layout=layout)
        sections = layout.sections.all()
        
        # URLパラメータでdisplayが指定されている場合はそれを使用
        display_param = request.GET.get('display')
        if display_param in ['plots', 'sections']:
            request.GET['display'] = display_param
        elif plots.exists():
            # 棚区画があれば棚区画を表示
            request.GET['display'] = 'plots'
        elif sections.exists():
            # 栽培区画のみがあれば栽培区画を表示
            request.GET['display'] = 'sections'
        else:
            # どちらもない場合は棚区画表示
            request.GET['display'] = 'plots'
    except:
        request.GET['display'] = 'plots'
    
    return plot_grid_view(request)

@login_required(login_url='/login/')
def layout_floor_plan(request, layout_id):
    """レイアウトの2D平面図表示（plot_grid_viewをラップ）"""
    # layout_idをクエリパラメータとして設定し、plot_grid_viewを呼び出す
    request.GET = request.GET.copy()
    request.GET['layout'] = layout_id
    request.GET['mode'] = 'floor_plan'
    return plot_grid_view(request)

@login_required(login_url='/login/')
def plot_management(request):
    """棚区画管理の一元化ページ"""
    from .models import Plot, CultivationLayout
    from collections import defaultdict

    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # レイアウトごとに棚を分類
    layout_id = request.GET.get('layout_id')
    if layout_id == 'none':
        # 未分類の棚を表示（組織フィルタ適用）
        selected_layout = 'none'
        plots = Plot.objects.filter(layout__isnull=True)
        if not is_global_admin(request.user) and current_organization:
            plots = plots.filter(organization=current_organization)
        plots = plots.order_by('shelf_number')
    elif layout_id:
        try:
            selected_layout = CultivationLayout.objects.get(id=layout_id)
            plots = Plot.objects.filter(layout=selected_layout)
            if not is_global_admin(request.user) and current_organization:
                plots = plots.filter(organization=current_organization)
            plots = plots.order_by('shelf_number')
        except CultivationLayout.DoesNotExist:
            selected_layout = None
            plots = Plot.objects.all()
            if not is_global_admin(request.user) and current_organization:
                plots = plots.filter(organization=current_organization)
            plots = plots.order_by('shelf_number')
    else:
        selected_layout = None
        plots = Plot.objects.all()
        if not is_global_admin(request.user) and current_organization:
            plots = plots.filter(organization=current_organization)
        plots = plots.order_by('shelf_number')

    # 全レイアウトの取得（組織フィルタ適用）
    if is_global_admin(request.user):
        all_layouts = CultivationLayout.objects.all()
    elif current_organization:
        all_layouts = CultivationLayout.objects.filter(organization=current_organization)
    else:
        all_layouts = CultivationLayout.objects.none()
    
    # レイアウト別の棚集計（組織でフィルタ）
    layouts_with_plots = defaultdict(list)
    uncategorized_plots_count = 0
    plots_for_layout_count = Plot.objects.select_related('layout')
    if not is_global_admin(request.user) and current_organization:
        plots_for_layout_count = plots_for_layout_count.filter(organization=current_organization)
    for plot in plots_for_layout_count:
        if plot.layout:
            layouts_with_plots[plot.layout].append(plot)
        else:
            layouts_with_plots['未分類'].append(plot)
            uncategorized_plots_count += 1

    # 統計情報の計算
    total_plots = plots.count()
    # 全棚数（組織でフィルタ）
    all_plots_qs = Plot.objects.all()
    if not is_global_admin(request.user) and current_organization:
        all_plots_qs = all_plots_qs.filter(organization=current_organization)
    all_plots_count = all_plots_qs.count()
    growing_count = 0
    harvest_ready_count = 0
    empty_count = 0
    overdue_count = 0
    
    # 各棚の詳細情報を取得
    plots_with_details = []
    
    for plot in plots:
        plot_has_crops = False
        
        # 共通ヘルパー関数を使用してレベル別の詳細情報を取得
        level_details = get_plot_level_details(plot)
        
        # 統計カウント用の処理
        for level_info in level_details:
            if level_info['status'] != 'empty':
                plot_has_crops = True
                if level_info['status'] == 'harvest_ready':
                    harvest_ready_count += 1
                elif level_info['status'] in ('planted', 'pre_planted', 'sowing'):
                    growing_count += 1
        
        if not plot_has_crops:
            empty_count += 1
        
        # 棚全体のステータスを決定（優先度順: harvest_ready > planted > pre_planted > sowing > harvested > empty）
        statuses = {l['status'] for l in level_details}
        if 'harvest_ready' in statuses:
            plot_status = 'harvest_ready'
        elif 'planted' in statuses:
            plot_status = 'planted'
        elif 'pre_planted' in statuses:
            plot_status = 'pre_planted'
        elif 'sowing' in statuses:
            plot_status = 'sowing'
        elif 'harvested' in statuses:
            plot_status = 'harvested'
        else:
            plot_status = 'empty'
        
        plots_with_details.append({
            'plot': plot,
            'level_details': level_details,
            'status': plot_status,
            'utilization_rate': plot.get_utilization_rate() if hasattr(plot, 'get_utilization_rate') else 0
        })
    
    # JSONシリアライゼーション用にplots_with_detailsを準備
    plots_json_data = []
    for item in plots_with_details:
        plot = item['plot']
        # level_detailsからDjangoモデルオブジェクト('crop')を除いたJSON安全なコピーを作成
        safe_level_details = [
            {k: v for k, v in ld.items() if k != 'crop'}
            for ld in item['level_details']
        ]
        plots_json_data.append({
            'plot': {
                'id': plot.id,
                'levels': plot.levels,
                'shelf_number': plot.shelf_number,
                'x_position': plot.x_position,
                'y_position': plot.y_position,
            },
            'shelf_number': plot.shelf_number,
            'levels': plot.levels,
            'level_details': safe_level_details,
            'status': item['status'],
            'utilization_rate': item['utilization_rate'],
        })
    
    # JSONシリアライゼーションを安全に実行
    try:
        plots_json = json.dumps({'plots': plots_json_data})
    except (TypeError, ValueError) as e:
        print(f"ERROR: Failed to serialize plots data: {e}")
        plots_json = json.dumps({'plots': []})
    
    context = {
        'plots_with_details': plots_with_details,
        'plots_json': plots_json,
        'all_layouts': all_layouts,
        'selected_layout': selected_layout,
        'layouts_with_plots': layouts_with_plots,
        'uncategorized_plots_count': uncategorized_plots_count,
        'statistics': {
            'total_plots': total_plots,
            'all_plots_count': all_plots_count,
            'growing_count': growing_count,
            'harvest_ready_count': harvest_ready_count,
            'empty_count': empty_count,
            'overdue_count': overdue_count,
        }
    }
    return render(request, 'cultivation/plot_management.html', context)

@user_passes_test(is_admin_user, login_url='/login/')
def plot_floor_plan_with_layout(request, layout_id):
    """レイアウト指定での棚区画2D平面図表示"""
    from .models import Plot, CultivationLayout
    
    # レイアウトを取得
    try:
        selected_layout = get_object_or_404(CultivationLayout, id=layout_id)
        plots = Plot.objects.filter(layout=selected_layout).order_by('shelf_number')
    except:
        selected_layout = None
        plots = Plot.objects.all().order_by('shelf_number')
    
    # 統計情報の計算
    total_plots = plots.count()
    growing_count = 0
    harvest_ready_count = 0
    empty_count = 0
    overdue_count = 0
    
    # 2D平面図用のデータを構築
    floor_plan_data = {
        'plots': []
    }
    
    for plot in plots:
        crops_by_level = plot.get_crops_by_level()
        
        # SVG座標の計算（保存された位置を使用、なければデフォルト位置）
        if hasattr(plot, 'svg_x') and plot.svg_x is not None and plot.svg_y is not None:
            svg_x = plot.svg_x
            svg_y = plot.svg_y
        else:
            svg_x = 50 + (plot.x_position - 1) * 120 
            svg_y = 50 + (plot.y_position - 1) * 80
            # 初期位置を保存
            plot.svg_x = svg_x
            plot.svg_y = svg_y
            plot.save()
        svg_width = 100
        svg_height = plot.levels * 20 + 20
        
        # レベル別の詳細情報を取得
        level_details = []
        for level in range(1, plot.levels + 1):
            level_crops = crops_by_level.get(level, [])
            level_info = {
                'level': level,
                'status': 'empty',
                'crop_name': '空き',
                'crop': None,
                'days_until_harvest': None,
                'progress_percentage': None
            }
            
            if level_crops:
                crop = level_crops[0]
                apply_floor_plan_crop_info(level_info, crop)
                
                if crop.days_until_harvest() is not None:
                    level_info['days_until_harvest'] = crop.days_until_harvest()
                    level_info['progress_percentage'] = crop.growth_progress_percentage()
                    
                    if crop.days_overdue() > 0:
                        level_info['status'] = 'overdue'
                        overdue_count += 1
                    elif crop.days_until_harvest() <= 0:
                        level_info['status'] = 'harvest_ready'
                        harvest_ready_count += 1
                    else:
                        level_info['status'] = 'growing'
                        growing_count += 1
                else:
                    level_info['status'] = 'growing'
                    growing_count += 1
            else:
                apply_floor_plan_crop_info(level_info, None)
                empty_count += 1
            
            # レベルのY座標を事前計算
            level_info['rect_y'] = svg_y + (level - 1) * 20 + 10
            level_info['text_y'] = svg_y + (level - 1) * 20 + 22
            level_details.append(level_info)
        
        # 3D座標を計算・更新
        plot.update_3d_position_if_needed()
        
        floor_plan_data['plots'].append({
            'id': plot.id,
            'plot': {
                'id': plot.id,
                'levels': plot.levels,
                'shelf_number': plot.shelf_number,
                'x_position': plot.x_position,
                'y_position': plot.y_position,
                'max_plates': plot.max_plates,
                'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            },
            'shelf_number': plot.shelf_number,
            'levels': plot.levels,
            'max_plates': plot.max_plates,
            'level_details': level_details,
            'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            'svg_x': svg_x,
            'svg_y': svg_y,
            'svg_width': svg_width,
            'svg_height': svg_height,
            'threejs_x': plot.threejs_x,
            'threejs_y': plot.threejs_y,
            'threejs_z': plot.threejs_z,
        })
    
    # 統計情報
    statistics = {
        'total_items': total_plots,
        'growing_count': growing_count,
        'harvest_ready_count': harvest_ready_count,
        'empty_count': empty_count,
        'overdue_count': overdue_count,
    }
    
    import json, math

    def _clean(obj):
        """JSON非対応の値（NaN/Inf/Decimal等）を安全な値に変換"""
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return 0.0
        return obj

    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            return str(obj)
        def iterencode(self, o, _one_shot=False):
            return super().iterencode(o, _one_shot=_one_shot)

    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data, cls=SafeEncoder)
    except Exception as e:
        import traceback
        print(f"ERROR in plot_floor_plan_with_layout: Failed to serialize: {e}")
        print(traceback.format_exc())
        floor_plan_data_json = '{"plots":[]}'

    excel_layout_rows, excel_layout_columns = build_excel_floor_plan_rows(floor_plan_data)

    context = {
        'floor_plan_data': floor_plan_data,
        'floor_plan_data_json': floor_plan_data_json,
        'excel_layout_rows': excel_layout_rows,
        'excel_layout_columns': excel_layout_columns,
        'statistics': statistics,
        'display_type': 'plots',
        'selected_layout': selected_layout,  # レイアウト指定
    }
    
    return render(request, 'cultivation/plot_floor_plan.html', context)

@login_required(login_url='/login/')
def plot_floor_plan(request):
    """棚区画の2D平面図表示"""
    from .models import Plot
    plots = Plot.objects.all().order_by('shelf_number')
    
    # 統計情報の計算
    total_plots = plots.count()
    growing_count = 0
    harvest_ready_count = 0
    empty_count = 0
    overdue_count = 0
    
    # 2D平面図用のデータを構築
    floor_plan_data = {
        'plots': []
    }
    
    for plot in plots:
        crops_by_level = plot.get_crops_by_level()
        
        # SVG座標の計算（保存された位置を使用、なければデフォルト位置）
        if hasattr(plot, 'svg_x') and plot.svg_x is not None and plot.svg_y is not None:
            svg_x = plot.svg_x
            svg_y = plot.svg_y
        else:
            svg_x = 50 + (plot.x_position - 1) * 120 
            svg_y = 50 + (plot.y_position - 1) * 80
            # 初期位置を保存
            plot.svg_x = svg_x
            plot.svg_y = svg_y
            plot.save()
        svg_width = 100
        svg_height = plot.levels * 20 + 20
        
        # レベル別の詳細情報を取得
        level_details = []
        for level in range(1, plot.levels + 1):
            level_crops = crops_by_level.get(level, [])
            level_info = {
                'level': level,
                'status': 'empty',
                'crop_name': '空き',
                'crop': None,
                'days_until_harvest': None,
                'progress_percentage': None
            }
            
            if level_crops:
                crop = level_crops[0]
                apply_floor_plan_crop_info(level_info, crop)
                
                if crop.days_until_harvest() is not None:
                    level_info['days_until_harvest'] = crop.days_until_harvest()
                    level_info['progress_percentage'] = crop.growth_progress_percentage()
                    
                    if crop.days_overdue() > 0:
                        level_info['status'] = 'overdue'
                        overdue_count += 1
                    elif crop.days_until_harvest() <= 0:
                        level_info['status'] = 'harvest_ready'
                        harvest_ready_count += 1
                    else:
                        level_info['status'] = 'growing'
                        growing_count += 1
                else:
                    level_info['status'] = 'growing'
                    growing_count += 1
            else:
                apply_floor_plan_crop_info(level_info, None)
                empty_count += 1
            
            # レベルのY座標を事前計算
            level_info['rect_y'] = svg_y + (level - 1) * 20 + 10
            level_info['text_y'] = svg_y + (level - 1) * 20 + 22
            level_details.append(level_info)
        
        # 3D座標を計算・更新
        plot.update_3d_position_if_needed()
        
        floor_plan_data['plots'].append({
            'id': plot.id,
            'plot': {
                'id': plot.id,
                'levels': plot.levels,
                'shelf_number': plot.shelf_number,
                'x_position': plot.x_position,
                'y_position': plot.y_position,
                'max_plates': plot.max_plates,
                'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            },
            'shelf_number': plot.shelf_number,
            'levels': plot.levels,
            'max_plates': plot.max_plates,
            'level_details': level_details,
            'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            'svg_x': svg_x,
            'svg_y': svg_y,
            'svg_width': svg_width,
            'svg_height': svg_height,
            'threejs_x': plot.threejs_x,
            'threejs_y': plot.threejs_y,
            'threejs_z': plot.threejs_z,
        })
    
    # 統計情報
    statistics = {
        'total_items': total_plots,
        'growing_count': growing_count,
        'harvest_ready_count': harvest_ready_count,
        'empty_count': empty_count,
        'overdue_count': overdue_count,
    }
    
    import json, math

    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            return str(obj)

    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data, cls=SafeEncoder)
    except Exception as e:
        import traceback
        print(f"ERROR in plot_floor_plan: Failed to serialize: {e}")
        print(traceback.format_exc())
        floor_plan_data_json = '{"plots":[]}'

    excel_layout_rows, excel_layout_columns = build_excel_floor_plan_rows(floor_plan_data)

    context = {
        'floor_plan_data': floor_plan_data,
        'floor_plan_data_json': floor_plan_data_json,
        'excel_layout_rows': excel_layout_rows,
        'excel_layout_columns': excel_layout_columns,
        'statistics': statistics,
        'display_type': 'plots',
        'selected_layout': None,  # 全レイアウト表示
    }
    
    return render(request, 'cultivation/plot_floor_plan.html', context)

@login_required(login_url='/login/')
def layout_delete(request, layout_id):
    """栽培レイアウトの削除"""
    layout = get_object_or_404(CultivationLayout, id=layout_id)
    
    if request.method == 'POST':
        layout_name = layout.name
        layout.delete()
        messages.success(request, f'栽培レイアウト「{layout_name}」を削除しました')
        return redirect('cultivation:cultivation_top')
    
    # 削除される関連データをカウント
    sections_count = layout.sections.count()
    plans_count = CultivationPlan.objects.filter(section__layout=layout).count()
    logs_count = CultivationLog.objects.filter(plan__section__layout=layout).count()
    
    context = {
        'layout': layout,
        'sections_count': sections_count,
        'plans_count': plans_count,
        'logs_count': logs_count,
    }
    return render(request, 'cultivation/layout_confirm_delete.html', context)

@login_required(login_url='/login/')
def section_detail(request, section_id):
    """区画詳細ページ - 棚設定も含む"""
    from .models import CultivationSection, Plot, ShelfCrop
    section = get_object_or_404(CultivationSection, id=section_id)
    
    # 対応する棚を取得または作成
    try:
        plot = section.plot
    except Plot.DoesNotExist:
        # 棚がない場合は作成
        plot = Plot.objects.create(
            layout=section.layout,
            section=section,
            shelf_number=f"棚-{section.name}",
            x_position=section.column,
            y_position=section.row,
            levels=3,
            width=1.2,
            depth=0.6,
            height_per_level=0.4,
            base_height=0.8,
            svg_x=50 + (section.column - 1) * 120,
            svg_y=50 + (section.row - 1) * 80
        )
    
    # 棚の各段の作物情報を取得
    crops_by_level = plot.get_crops_by_level()
    
    plans = section.plans.all().order_by('-created_at')
    current_plan = plans.first() if plans.exists() else None
    logs = []
    
    if current_plan:
        logs = current_plan.logs.all().order_by('-log_date')
    
    context = {
        'section': section,
        'plot': plot,
        'crops_by_level': crops_by_level,
        'plans': plans,
        'current_plan': current_plan,
        'logs': logs,
        'level_range': range(1, plot.levels + 1),
    }
    return render(request, 'cultivation/section_detail.html', context)

@login_required(login_url='/login/')
def plan_create(request, section_id):
    """栽培計画作成"""
    section = get_object_or_404(CultivationSection, id=section_id)
    organization = section.layout.organization if section.layout else get_current_organization(request)
    
    if request.method == 'POST':
        form = CultivationPlanForm(request.POST, organization=organization)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.section = section
            plan.save()
            messages.success(request, f'{section.name}の栽培計画を作成しました')
            return redirect('cultivation:section_detail', section_id=section.id)
    else:
        form = CultivationPlanForm(organization=organization)
    
    context = {
        'form': form,
        'section': section,
        'is_create': True,
    }
    return render(request, 'cultivation/plan_form.html', context)

@login_required(login_url='/login/')
def plan_edit(request, plan_id):
    """栽培計画編集"""
    plan = get_object_or_404(CultivationPlan, id=plan_id)
    organization = plan.section.layout.organization if plan.section and plan.section.layout else get_current_organization(request)
    
    if request.method == 'POST':
        form = CultivationPlanForm(request.POST, instance=plan, organization=organization)
        if form.is_valid():
            form.save()
            messages.success(request, f'{plan.section.name}の栽培計画を更新しました')
            return redirect('cultivation:section_detail', section_id=plan.section.id)
    else:
        form = CultivationPlanForm(instance=plan, organization=organization)
    
    context = {
        'form': form,
        'plan': plan,
        'section': plan.section,
        'is_create': False,
    }
    return render(request, 'cultivation/plan_form.html', context)

@user_passes_test(is_admin_user, login_url='/login/')
def section_edit_plot(request, section_id):
    """区画の棚設定編集"""
    from .models import CultivationSection, Plot
    from .forms import PlotForm
    
    section = get_object_or_404(CultivationSection, id=section_id)
    
    # 対応する棚を取得または作成
    try:
        plot = section.plot
    except Plot.DoesNotExist:
        plot = Plot.objects.create(
            layout=section.layout,
            section=section,
            shelf_number=f"棚-{section.name}",
            x_position=section.column,
            y_position=section.row,
            levels=3,
            width=1.2,
            depth=0.6,
            height_per_level=0.4,
            base_height=0.8,
            svg_x=50 + (section.column - 1) * 120,
            svg_y=50 + (section.row - 1) * 80
        )
    
    if request.method == 'POST':
        form = PlotForm(request.POST, instance=plot)
        if form.is_valid():
            plot = form.save()
            messages.success(request, f'区画「{section.name}」の棚設定を更新しました')
            return redirect('cultivation:section_detail', section_id=section.id)
    else:
        form = PlotForm(instance=plot)
    
    context = {
        'section': section,
        'plot': plot,
        'form': form,
        'title': f'区画「{section.name}」の棚設定',
    }
    return render(request, 'cultivation/section_edit_plot.html', context)

@user_passes_test(is_admin_user, login_url='/login/')
def section_crop_manage(request, section_id, level):
    """区画の特定段の作物管理"""
    from .models import CultivationSection, ShelfCrop, Crop
    
    section = get_object_or_404(CultivationSection, id=section_id)
    plot = section.plot
    level = int(level)
    current_organization = get_current_organization(request) or section.layout.organization
    
    # 該当段の現在の作物を取得（最新のもの）
    current_crop = plot.shelf_crops.filter(level=level).order_by('-planting_date').first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'plant':
            # 新しい作物を植える
            crop_id = request.POST.get('crop_id')
            planting_date = request.POST.get('planting_date')
            expected_harvest_days = request.POST.get('expected_harvest_days')
            
            if crop_id:
                from datetime import datetime, timedelta
                
                crop = get_object_or_404(crop_queryset_for_organization(current_organization), id=crop_id)
                # 作物名は登録済み作物から自動取得
                variety = crop.name
                planting_date = datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else timezone.now().date()
                expected_harvest_date = planting_date + timedelta(days=int(expected_harvest_days)) if expected_harvest_days else None
                
                # 既存の作物があれば収穫済みにする
                if current_crop:
                    current_crop.harvest_date = timezone.now().date()
                    current_crop.save()
                
                # 新しい作物を作成
                ShelfCrop.objects.create(
                    plot=plot,
                    variety=variety,
                    organization=current_organization or plot.organization,
                    level=level,
                    planting_date=planting_date,
                    expected_harvest_date=expected_harvest_date
                )
                
                messages.success(request, f'レベル{level}に「{variety}」を植えました')
        
        elif action == 'harvest' and current_crop:
            # 収穫する
            current_crop.harvest_date = timezone.now().date()
            current_crop.save()
            messages.success(request, f'レベル{level}の「{current_crop.variety}」を収穫しました')
        
        return redirect('cultivation:section_detail', section_id=section.id)
    
    # 利用可能な作物リストを取得
    available_crops = crop_queryset_for_organization(current_organization)
    
    context = {
        'section': section,
        'plot': plot,
        'level': level,
        'current_crop': current_crop,
        'available_crops': available_crops,
    }
    return render(request, 'cultivation/section_crop_manage.html', context)

@login_required(login_url='/login/')
def log_create(request, plan_id):
    """栽培ログ作成"""
    plan = get_object_or_404(CultivationPlan, id=plan_id)
    
    if request.method == 'POST':
        form = CultivationLogForm(request.POST, request.FILES)
        if form.is_valid():
            log = form.save(commit=False)
            log.plan = plan
            log.save()
            messages.success(request, f'{plan.section.name}の栽培ログを記録しました')
            return redirect('cultivation:section_detail', section_id=plan.section.id)
    else:
        form = CultivationLogForm()
    
    context = {
        'form': form,
        'plan': plan,
        'section': plan.section,
    }
    return render(request, 'cultivation/log_form.html', context)

@login_required(login_url='/login/')
def section_edit(request, section_id):
    """区画編集"""
    section = get_object_or_404(CultivationSection, id=section_id)
    
    if request.method == 'POST':
        form = CultivationSectionForm(request.POST, instance=section)
        if form.is_valid():
            form.save()
            messages.success(request, f'{section.name}の区画情報を更新しました')
            return redirect('cultivation:section_detail', section_id=section.id)
    else:
        form = CultivationSectionForm(instance=section)
    
    context = {
        'form': form,
        'section': section,
        'is_create': False,
    }
    return render(request, 'cultivation/section_form.html', context)

@login_required(login_url='/login/')
def section_delete(request, section_id):
    """区画削除"""
    section = get_object_or_404(CultivationSection, id=section_id)
    layout = section.layout
    
    if request.method == 'POST':
        section_name = section.name
        section.delete()
        messages.success(request, f'{section_name}の区画を削除しました')
        return redirect('cultivation:layout_detail', layout_id=layout.id)
    
    # 削除される関連データをカウント
    plans_count = section.plans.count()
    logs_count = CultivationLog.objects.filter(plan__section=section).count()
    
    context = {
        'section': section,
        'layout': layout,
        'plans_count': plans_count,
        'logs_count': logs_count,
    }
    return render(request, 'cultivation/section_confirm_delete.html', context)

@login_required(login_url='/login/')
def section_create(request, layout_id):
    """区画作成"""
    layout = get_object_or_404(CultivationLayout, id=layout_id)
    
    # 既存区画の位置情報を取得
    existing_sections = layout.sections.all()
    occupied_positions = [(s.row, s.column) for s in existing_sections]
    
    # グリッドの最大サイズを取得
    max_row = existing_sections.aggregate(models.Max('row'))['row__max'] or 0
    max_column = existing_sections.aggregate(models.Max('column'))['column__max'] or 0
    
    # 次に推奨される位置を計算
    suggested_positions = []
    for row in range(1, max_row + 3):  # 現在の最大行+2まで
        for column in range(1, max_column + 3):  # 現在の最大列+2まで
            if (row, column) not in occupied_positions:
                suggested_positions.append((row, column))
                if len(suggested_positions) >= 5:  # 最大5つの提案
                    break
        if len(suggested_positions) >= 5:
            break
    
    if request.method == 'POST':
        form = CultivationSectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.layout = layout
            try:
                section.save()
                messages.success(request, f'{section.name}の区画を作成しました')
                return redirect('cultivation:layout_detail', layout_id=layout.id)
            except Exception as e:
                messages.error(request, f'区画の作成に失敗しました: {str(e)}')
    else:
        # 初期値として最初の推奨位置を設定
        initial_data = {}
        if suggested_positions:
            initial_data['row'] = suggested_positions[0][0]
            initial_data['column'] = suggested_positions[0][1]
        form = CultivationSectionForm(initial=initial_data)
    
    context = {
        'form': form,
        'layout': layout,
        'is_create': True,
        'existing_sections': existing_sections,
        'occupied_positions': occupied_positions,
        'suggested_positions': suggested_positions,
        'max_row': max_row,
        'max_column': max_column,
    }
    return render(request, 'cultivation/section_form.html', context)

@login_required(login_url='/login/')
def bulk_section_create(request, layout_id):
    """一括区画作成"""
    layout = get_object_or_404(CultivationLayout, id=layout_id)
    
    if request.method == 'POST':
        rows = int(request.POST.get('rows', 3))
        columns = int(request.POST.get('columns', 3))
        name_prefix = request.POST.get('name_prefix', '区画')
        
        created_count = 0
        errors = []
        
        for row in range(1, rows + 1):
            for column in range(1, columns + 1):
                section_name = f"{name_prefix}-{row}-{column}"
                
                # 既存の区画があるかチェック
                if not CultivationSection.objects.filter(layout=layout, row=row, column=column).exists():
                    try:
                        CultivationSection.objects.create(
                            layout=layout,
                            name=section_name,
                            row=row,
                            column=column
                        )
                        created_count += 1
                    except Exception as e:
                        errors.append(f"{row}行{column}列: {str(e)}")
        
        if created_count > 0:
            messages.success(request, f'{created_count}個の区画を作成しました')
        
        if errors:
            messages.warning(request, f'一部の区画で作成に失敗しました: {", ".join(errors)}')
        
        return redirect('cultivation:layout_detail', layout_id=layout.id)
    
    # 既存区画の情報を取得
    existing_sections = layout.sections.all()
    max_row = existing_sections.aggregate(models.Max('row'))['row__max'] or 0
    max_column = existing_sections.aggregate(models.Max('column'))['column__max'] or 0
    
    context = {
        'layout': layout,
        'max_row': max_row,
        'max_column': max_column,
        'existing_count': existing_sections.count(),
    }
    return render(request, 'cultivation/bulk_section_create.html', context)

@login_required(login_url='/login/')
def plot_grid_view(request):
    """棚区画のグリッド表示"""
    from .models import Plot, CultivationSection

    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    # レイアウトフィルタパラメータを取得
    layout_id = request.GET.get('layout')
    display_param = request.GET.get('display', 'auto')

    # 組織に基づいてプロットをフィルタリングするヘルパー
    def filter_plots_by_org(plots_qs):
        if not is_global_admin(request.user) and current_organization:
            return plots_qs.filter(organization=current_organization)
        return plots_qs

    # display パラメータで表示タイプを決定
    if display_param == 'plots':
        # 強制的に棚区画を表示
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                # 組織チェック
                if not is_global_admin(request.user) and current_organization:
                    if layout.organization != current_organization:
                        messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                        return redirect('cultivation:cultivation_top')
                plots = Plot.objects.filter(layout=layout)
            except Exception as e:
                layout = None
                plots = filter_plots_by_org(Plot.objects.all())
        else:
            plots = filter_plots_by_org(Plot.objects.all())
            layout = None
        display_type = 'plots'
    elif display_param == 'sections' or (layout_id and display_param == 'auto'):
        # 栽培区画を表示
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                # 組織チェック
                if not is_global_admin(request.user) and current_organization:
                    if layout.organization != current_organization:
                        messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                        return redirect('cultivation:cultivation_top')
                sections = layout.sections.all()

                # auto モードの場合、区画がない場合は棚区画を表示
                if display_param == 'auto' and not sections.exists():
                    plots = Plot.objects.filter(layout=layout)
                    display_type = 'plots'
                else:
                    display_type = 'sections'
            except:
                plots = filter_plots_by_org(Plot.objects.all())
                display_type = 'plots'
                layout = None
        else:
            plots = filter_plots_by_org(Plot.objects.all())
            display_type = 'plots'
            layout = None
    else:
        # デフォルトは棚区画
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                # 組織チェック
                if not is_global_admin(request.user) and current_organization:
                    if layout.organization != current_organization:
                        messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                        return redirect('cultivation:cultivation_top')
                plots = Plot.objects.filter(layout=layout)
            except:
                layout = None
                plots = filter_plots_by_org(Plot.objects.all())
        else:
            plots = filter_plots_by_org(Plot.objects.all())
            layout = None
        display_type = 'plots'
    
    # 表示モードを取得（デフォルトはgrid）
    view_mode = request.GET.get('mode', 'grid')
    
    # データタイプに応じてグリッドサイズを取得
    if display_type == 'sections':
        max_x = sections.aggregate(models.Max('column'))['column__max'] or 0
        max_y = sections.aggregate(models.Max('row'))['row__max'] or 0
        # セクション用グリッドを作成（Noneで初期化）
        grid = [[None for _ in range(max_x + 1)] for _ in range(max_y + 1)]
    else:
        max_x = plots.aggregate(models.Max('x_position'))['x_position__max'] or 0
        max_y = plots.aggregate(models.Max('y_position'))['y_position__max'] or 0
        # プロット用グリッドを作成（Noneで初期化）
        grid = [[None for _ in range(max_x + 1)] for _ in range(max_y + 1)]
    
    # 統計情報を初期化
    if display_type == 'sections':
        total_items = sections.count()
    else:
        total_items = plots.count()
    
    growing_count = 0
    harvest_ready_count = 0
    empty_count = 0
    overdue_count = 0
    
    # レベル別の統計
    level_stats = {}
    
    # データタイプに応じて処理を分岐
    if display_type == 'sections':
        # 栽培区画の処理
        for section in sections:
            # 最新の栽培計画を取得
            latest_plan = section.plans.order_by('-created_at').first()
            
            if latest_plan and latest_plan.crop and not latest_plan.harvest_date_actual:
                if latest_plan.is_harvest_ready():
                    harvest_ready_count += 1
                else:
                    growing_count += 1
            else:
                empty_count += 1
            
            # グリッドに配置
            grid[section.row][section.column] = {
                'section': section,
                'plan': latest_plan,
                'crop': {
                    'id': latest_plan.crop.id,
                    'name': latest_plan.crop.name,
                    'color': latest_plan.crop.color if hasattr(latest_plan.crop, 'color') else '#808080'
                } if latest_plan and latest_plan.crop else None,
                'type': 'section'
            }
    else:
        # 各Plotをグリッドに配置し、統計を計算
        for plot in plots:
            # すべてのレベルの作物を取得
            crops_by_level = plot.get_crops_by_level()
            
            # レベル統計を更新
            for level in range(1, plot.levels + 1):
                if level not in level_stats:
                    level_stats[level] = {'total': 0, 'growing': 0, 'harvest_ready': 0, 'empty': 0, 'overdue': 0}
                
                level_crops = crops_by_level.get(level, [])
                level_stats[level]['total'] += 1
                
                if level_crops:
                    for crop in level_crops:
                        if crop.days_until_harvest() is not None:
                            if crop.days_until_harvest() <= 0:
                                if crop.days_overdue() > 0:
                                    level_stats[level]['overdue'] += 1
                                    overdue_count += 1
                                else:
                                    level_stats[level]['harvest_ready'] += 1
                                    harvest_ready_count += 1
                            else:
                                level_stats[level]['growing'] += 1
                                growing_count += 1
                        else:
                            level_stats[level]['growing'] += 1
                            growing_count += 1
                else:
                    level_stats[level]['empty'] += 1
                    empty_count += 1
            
            # 最新の作物情報を取得（第1レベル優先）
            current_crop = None
            if crops_by_level.get(1):
                current_crop = crops_by_level[1][0]
            elif any(crops_by_level.values()):
                # 他のレベルから最初の作物を取得
                for level_crops in crops_by_level.values():
                    if level_crops:
                        current_crop = level_crops[0]
                        break
            
            # Convert crops_by_level to serializable format
            serializable_crops_by_level = {}
            for level, level_crops in crops_by_level.items():
                serializable_crops_by_level[level] = [
                    {
                        'id': crop.id,
                        'variety': crop.variety,
                        'planting_date': crop.planting_date.isoformat() if crop.planting_date else None,
                        'expected_harvest_date': crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None,
                        'days_until_harvest': crop.days_until_harvest(),
                        'progress_percentage': crop.growth_progress_percentage()
                    } for crop in level_crops
                ]
            
            grid[plot.y_position][plot.x_position] = {
                'plot': plot,
                'crop': {
                    'id': current_crop.id,
                    'variety': current_crop.variety,
                    'planting_date': current_crop.planting_date.isoformat() if current_crop.planting_date else None,
                    'expected_harvest_date': current_crop.expected_harvest_date.isoformat() if current_crop.expected_harvest_date else None,
                    'days_until_harvest': current_crop.days_until_harvest(),
                    'progress_percentage': current_crop.growth_progress_percentage()
                } if current_crop else None,
                'crops_by_level': serializable_crops_by_level,
                'level_count': plot.levels,
                'status_color': plot.get_status_color()
            }
    
    # 2D平面図用の配置データを作成
    floor_plan_data = []
    plot_details = {}
    if view_mode == 'floor_plan':
        if display_type == 'sections':
            # 栽培区画の2D平面図表示
            for section in sections:
                latest_plan = section.plans.order_by('-created_at').first()
                
                # 区画の状況を判定
                section_status = 'empty'
                if latest_plan and latest_plan.crop and not latest_plan.harvest_date_actual:
                    if latest_plan.is_harvest_ready():
                        section_status = 'harvest_ready'
                    else:
                        section_status = 'growing'
                
                # 区画の詳細情報を保存
                plot_details[section.name] = {
                    'crop_history': [],
                    'utilization_rate': 100 if latest_plan and latest_plan.crop else 0,
                    'productivity_stats': {}
                }
                
                # SVG座標計算（60px基準単位）
                svg_x = 50 + (section.column - 1) * 80
                svg_y = 50 + (section.row - 1) * 80
                svg_width = 70
                svg_height = 70
                svg_text_x = svg_x + svg_width / 2
                svg_text_y = svg_y + svg_height / 2
                
                # 区画の色を取得
                status_colors = {
                    'empty': '#e8f5e9',
                    'growing': '#e3f2fd',
                    'harvest_ready': '#fff3e0',
                    'overdue': '#ffcdd2'
                }
                
                floor_plan_data.append({
                    'section': {
                        'id': section.id,
                        'name': section.name,
                        'row': section.row,
                        'column': section.column,
                    },
                    'crop': {
                        'id': latest_plan.crop.id,
                        'name': latest_plan.crop.name,
                    } if latest_plan and latest_plan.crop else None,
                    'status': section_status,
                    'color': status_colors[section_status],
                    'section_id': f"{section.name}",
                    'type': 'section',
                    # SVG描画用の座標
                    'svg_x': svg_x,
                    'svg_y': svg_y,
                    'svg_width': svg_width,
                    'svg_height': svg_height,
                    'svg_text_x': svg_text_x,
                    'svg_text_y': svg_text_y,
                })
        else:
            # 棚区画の2D平面図表示
            plots_data = []
            for plot in plots:
                crops_by_level = plot.get_crops_by_level()
                
                # 各棚の詳細情報を保存
                crop_history = plot.get_crop_history(5)
                crop_history_data = []
                for crop in crop_history:
                    crop_history_data.append({
                        'variety': crop.variety,
                        'planting_date': crop.planting_date.isoformat() if crop.planting_date else None,
                        'expected_harvest_date': crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None,
                        'level': crop.level
                    })
                
                plot_details[plot.shelf_number] = {
                    'crop_history': crop_history_data,
                    'utilization_rate': plot.get_utilization_rate(),
                    'productivity_stats': plot.get_productivity_stats()
                }
                
                # SVG座標計算（保存された位置を使用、なければデフォルト位置）
                if hasattr(plot, 'svg_x') and plot.svg_x is not None and plot.svg_y is not None:
                    svg_x = plot.svg_x
                    svg_y = plot.svg_y
                else:
                    svg_x = 50 + plot.x_position * (plot.width * 30 + 15)
                    svg_y = 50 + plot.y_position * (plot.depth * 30 + 15)
                    # 初期位置を保存
                    plot.svg_x = svg_x
                    plot.svg_y = svg_y
                    plot.save()
                svg_width = plot.width * 30
                svg_height = plot.depth * 30
                
                # 共通ヘルパー関数を使用してレベル別の詳細情報を取得
                level_details = get_plot_level_details(plot)
                
                # SVG表示用の追加情報を設定
                for level_info in level_details:
                    level = level_info['level']
                    level_height = plot.base_height + (plot.height_per_level * (level - 1))
                    level_rect_y = svg_y + (level - 1) * 18
                    
                    level_info['rect_y'] = level_rect_y
                    level_info['level_height'] = level_height
                
                # 3D座標を計算・更新
                plot.update_3d_position_if_needed()
                
                plots_data.append({
                    'id': plot.id,
                    'plot': {
                        'id': plot.id,
                        'levels': plot.levels,
                        'shelf_number': plot.shelf_number,
                        'x_position': plot.x_position,
                        'y_position': plot.y_position,
                        'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
                    },
                    'shelf_number': plot.shelf_number,
                    'levels': plot.levels,
                    'level_details': level_details,
                    'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
                    'x_pos': plot.x_position * (plot.width + 0.5),  # 実際の位置（メートル）
                    'y_pos': plot.y_position * (plot.depth + 0.5),  # 実際の位置（メートル）
                    'width': plot.width,
                    'depth': plot.depth,
                    'svg_x': svg_x,
                    'svg_y': svg_y,
                    'svg_width': svg_width,
                    'svg_height': svg_height,
                    'threejs_x': plot.threejs_x,
                    'threejs_y': plot.threejs_y,
                    'threejs_z': plot.threejs_z,
                })
            
            floor_plan_data = {'plots': plots_data}
    
    import json

    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            return str(obj)

    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data, cls=SafeEncoder)
    except Exception as e:
        print(f"ERROR: Failed to serialize floor_plan_data: {e}")
        floor_plan_data_json = '{"plots":[]}'

    try:
        plot_details_json = json.dumps(plot_details, cls=SafeEncoder)
    except Exception as e:
        print(f"ERROR: Failed to serialize plot_details: {e}")
        plot_details_json = '{}'
    
    context = {
        'grid': grid,
        'max_x': max_x,
        'max_y': max_y,
        'view_mode': view_mode,
        'floor_plan_data': floor_plan_data,
        'floor_plan_data_json': floor_plan_data_json,
        'plot_details': plot_details,
        'plot_details_json': plot_details_json,
        'layout_id': layout_id,
        'selected_layout': layout if layout_id else None,
        'display_type': display_type,
        'statistics': {
            'total_items': total_items,
            'growing_count': growing_count,
            'harvest_ready_count': harvest_ready_count,
            'empty_count': empty_count,
            'overdue_count': overdue_count,
            'level_stats': level_stats if display_type == 'plots' else {}
        }
    }
    
    # 3D表示用に棚データも準備（セクション表示の場合でも）
    plots_floor_plan_data = None
    if display_type == 'sections' and view_mode == 'floor_plan' and layout:
        # レイアウト専用の棚データを3D表示用に準備
        layout_plots = Plot.objects.filter(layout=layout)
        plots_floor_plan_data = {'plots': []}
        
        for plot in layout_plots:
            crops_by_level = plot.get_crops_by_level()
            
            # レベル別の詳細情報を取得
            level_details = []
            for level in range(1, plot.levels + 1):
                level_crops = crops_by_level.get(level, [])
                level_info = {
                    'level': level,
                    'status': 'empty',
                    'crop_name': '空き',
                    'crop': None,
                    'days_until_harvest': None,
                    'progress_percentage': None,
                }
                
                if level_crops:
                    crop = level_crops[0]
                    level_info['crop_id'] = crop.id
                    level_info['crop_name'] = crop.variety
                    level_info['planting_date'] = crop.planting_date.isoformat() if crop.planting_date else None
                    level_info['expected_harvest_date'] = crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None
                    
                    if crop.days_until_harvest() is not None:
                        level_info['days_until_harvest'] = crop.days_until_harvest()
                        level_info['progress_percentage'] = crop.growth_progress_percentage()
                        
                        if crop.days_overdue() > 0:
                            level_info['status'] = 'overdue'
                        elif crop.days_until_harvest() <= 0:
                            level_info['status'] = 'harvest_ready'
                        else:
                            level_info['status'] = 'growing'
                
                level_details.append(level_info)
            
            # SVG座標の計算（保存された位置を使用、なければデフォルト位置）
            if hasattr(plot, 'svg_x') and plot.svg_x is not None and plot.svg_y is not None:
                svg_x = plot.svg_x
                svg_y = plot.svg_y
            else:
                svg_x = 50 + plot.x_position * (plot.width * 30 + 15)
                svg_y = 50 + plot.y_position * (plot.depth * 30 + 15)
                # 初期位置を保存
                plot.svg_x = svg_x
                plot.svg_y = svg_y
                plot.save()
            svg_width = plot.width * 30
            svg_height = plot.depth * 30
            
            # 3D座標を計算・更新
            plot.update_3d_position_if_needed()
            
            plots_floor_plan_data['plots'].append({
                'id': plot.id,
                'shelf_number': plot.shelf_number,
                'levels': plot.levels,
                'level_details': level_details,
                'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
                'svg_x': svg_x,
                'svg_y': svg_y,
                'svg_width': svg_width,
                'svg_height': svg_height,
                'plot': {
                    'id': plot.id,
                    'shelf_number': plot.shelf_number,
                    'x_position': plot.x_position,
                    'y_position': plot.y_position,
                    'levels': plot.levels,
                    'width': plot.width,
                    'depth': plot.depth,
                    'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None
                },
                'threejs_x': plot.threejs_x,
                'threejs_y': plot.threejs_y,
                'threejs_z': plot.threejs_z,
            })
    
    # コンテキストに棚データを追加
    if plots_floor_plan_data:
        context['plots_floor_plan_data'] = plots_floor_plan_data
        import math as _math
        class _SafeEnc(json.JSONEncoder):
            def default(self, obj):
                return str(obj)
            def iterencode(self, o, _one_shot=False):
                return super().iterencode(o, _one_shot=_one_shot)
        try:
            context['plots_floor_plan_data_json'] = json.dumps(plots_floor_plan_data, cls=_SafeEnc)
        except Exception as e:
            print(f"ERROR: Failed to serialize plots_floor_plan_data: {e}")
            context['plots_floor_plan_data_json'] = '{"plots":[]}'
    
    # テンプレートを選択（平面図は統合済み）
    if view_mode == 'floor_plan':
        template_name = 'cultivation/plot_floor_plan.html'
    else:
        template_name = 'cultivation/plot_grid.html'
    
    return render(request, template_name, context)

@user_passes_test(is_admin_user, login_url='/login/')
def plot_detail_view(request, plot_id):
    """棚区画の詳細表示"""
    from .models import Plot

    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    plot = get_object_or_404(Plot, id=plot_id)

    # 組織チェック：グローバル管理者でない場合、自組織の棚のみ表示可能
    if not is_global_admin(request.user) and current_organization:
        if plot.organization != current_organization:
            messages.error(request, 'この棚にアクセスする権限がありません。')
            return redirect('cultivation:cultivation_top')

    crops = plot.shelf_crops.all()
    current_crop = crops.first() if crops.exists() else None

    context = {
        'plot': plot,
        'crops': crops,
        'current_crop': current_crop,
    }
    return render(request, 'cultivation/plot_detail.html', context)

@user_passes_test(is_admin_user, login_url='/login/')
def crop_image_upload_view(request, crop_id):
    """作物画像のアップロード"""
    from .models import ShelfCrop, CropImage
    crop = get_object_or_404(ShelfCrop, id=crop_id)
    
    if request.method == 'POST':
        image = request.FILES.get('image')
        notes = request.POST.get('notes', '')
        
        if image:
            CropImage.objects.create(
                crop=crop,
                image=image,
                capture_date=timezone.now(),
                notes=notes
            )
            messages.success(request, '画像をアップロードしました')
            return redirect('cultivation:plot_detail', plot_id=crop.plot.id)
        else:
            messages.error(request, '画像を選択してください')
    
    context = {
        'crop': crop,
    }
    return render(request, 'cultivation/crop_image_upload.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def plot_create(request):
    """棚区画の新規作成"""
    from .models import Plot, CultivationLayout

    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    if request.method == 'POST':
        form = PlotForm(request.POST)
        if form.is_valid():
            plot = form.save(commit=False)
            plot.organization = current_organization  # 組織を自動設定

            # レイアウトが指定されていない場合、デフォルトレイアウトに割り当て
            if not plot.layout:
                default_layout, created = CultivationLayout.objects.get_or_create(
                    name="デフォルトレイアウト",
                    organization=current_organization,
                    defaults={'description': '棚区画管理で作成された棚の既定レイアウト'}
                )
                plot.layout = default_layout

            plot.save()
            messages.success(request, f'棚区画「{plot.shelf_number}」を作成しました')
            return redirect('cultivation:plot_management')
    else:
        form = PlotForm()
    
    context = {
        'form': form,
        'title': '棚区画の新規作成',
        'is_create': True,
    }
    return render(request, 'cultivation/plot_form.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def plot_edit(request, plot_id):
    """棚区画の編集"""
    from .models import Plot
    plot = get_object_or_404(Plot, id=plot_id)
    
    if request.method == 'POST':
        form = PlotForm(request.POST, instance=plot)
        if form.is_valid():
            plot = form.save()
            messages.success(request, f'棚区画「{plot.shelf_number}」を更新しました')
            return redirect('cultivation:plot_detail', plot_id=plot.id)
    else:
        form = PlotForm(instance=plot)
    
    context = {
        'form': form,
        'plot': plot,
        'title': f'棚区画「{plot.shelf_number}」の編集',
        'is_create': False,
    }
    return render(request, 'cultivation/plot_form.html', context)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@user_passes_test(is_admin_user, login_url='/login/')
def plot_update_position(request, plot_id):
    """棚区画の位置更新（AJAX）"""
    import json
    import logging
    from django.http import JsonResponse
    from .models import Plot
    
    logger = logging.getLogger(__name__)
    logger.info(f"plot_update_position called for plot_id: {plot_id}")
    
    if request.method != 'POST':
        logger.error("Non-POST request received")
        return JsonResponse({'success': False, 'error': 'POST method required'})
    
    try:
        logger.info(f"Request body: {request.body}")
        plot = get_object_or_404(Plot, id=plot_id)
        logger.info(f"Found plot: {plot}")
        
        data = json.loads(request.body)
        logger.info(f"Parsed data: {data}")
        
        svg_x = float(data.get('svg_x', 0))
        svg_y = float(data.get('svg_y', 0))
        logger.info(f"Coordinates: x={svg_x}, y={svg_y}")
        
        # 座標の範囲チェック
        if svg_x < 0 or svg_x > 800 or svg_y < 0 or svg_y > 600:
            logger.error(f"Coordinates out of range: x={svg_x}, y={svg_y}")
            return JsonResponse({'success': False, 'error': '座標が範囲外です'})
        
        # 保存前の値をログ
        logger.info(f"Before save: plot.svg_x={plot.svg_x}, plot.svg_y={plot.svg_y}")
        
        plot.svg_x = svg_x
        plot.svg_y = svg_y
        
        # 2D位置から3D位置を自動計算
        threejs_x = (svg_x - 400) / 100  # SVG座標を3D座標に変換
        threejs_z = (svg_y - 300) / 100  # SVG座標を3D座標に変換
        threejs_y = 0.0  # Y座標（高さ）は0に固定
        
        plot.threejs_x = threejs_x
        plot.threejs_y = threejs_y
        plot.threejs_z = threejs_z
        
        plot.save()
        
        # 保存後の値をログ
        plot.refresh_from_db()
        logger.info(f"After save: plot.svg_x={plot.svg_x}, plot.svg_y={plot.svg_y}")
        logger.info(f"3D coordinates updated: x={plot.threejs_x}, y={plot.threejs_y}, z={plot.threejs_z}")
        
        return JsonResponse({
            'success': True,
            'plot_id': plot.id,
            'new_x': svg_x,
            'new_y': svg_y,
            'threejs_x': plot.threejs_x,
            'threejs_y': plot.threejs_y,
            'threejs_z': plot.threejs_z
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except ValueError as e:
        logger.error(f"Value error: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid coordinates'})
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@user_passes_test(is_admin_user, login_url='/login/')
def plot_delete(request, plot_id):
    """棚区画の削除"""
    from .models import Plot
    try:
        plot = Plot.objects.get(id=plot_id)
    except Plot.DoesNotExist:
        messages.error(request, f'棚区画ID {plot_id} が見つかりません。既に削除されている可能性があります。')
        return redirect('cultivation:plot_management')
    
    if request.method == 'POST':
        shelf_number = plot.shelf_number
        plot.delete()
        messages.success(request, f'棚区画「{shelf_number}」を削除しました')
        return redirect('cultivation:plot_management')
    
    context = {
        'plot': plot,
    }
    return render(request, 'cultivation/plot_confirm_delete.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_create(request, plot_id):
    """作物の新規作成"""
    from .models import Plot, ShelfCrop
    plot = get_object_or_404(Plot, id=plot_id)

    current_organization = get_current_organization(request)

    if request.method == 'POST':
        form = ShelfCropForm(request.POST)
        if form.is_valid():
            crop = form.save(commit=False)
            crop.plot = plot
            crop.organization = current_organization or plot.organization  # 組織を自動設定
            crop.save()
            messages.success(request, f'作物「{crop.variety}」を棚「{plot.shelf_number}」に追加しました')
            return redirect('cultivation:plot_detail', plot_id=plot.id)
    else:
        form = ShelfCropForm()
    
    context = {
        'form': form,
        'plot': plot,
        'title': f'棚「{plot.shelf_number}」に作物を追加',
        'is_create': True,
    }
    return render(request, 'cultivation/crop_form.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_edit(request, crop_id):
    """作物の編集"""
    from .models import ShelfCrop
    try:
        crop = get_object_or_404(ShelfCrop, id=crop_id)
    except ShelfCrop.DoesNotExist:
        messages.error(request, f'作物ID {crop_id} が見つかりません。既に削除されている可能性があります。')
        return redirect('cultivation:plot_management')
    
    if request.method == 'POST':
        form = ShelfCropForm(request.POST, instance=crop)
        if form.is_valid():
            crop = form.save()
            messages.success(request, f'作物「{crop.variety}」を更新しました')
            return redirect('cultivation:plot_detail', plot_id=crop.plot.id)
    else:
        form = ShelfCropForm(instance=crop)
    
    context = {
        'form': form,
        'crop': crop,
        'plot': crop.plot,
        'title': f'作物「{crop.variety}」の編集',
        'is_create': False,
    }
    return render(request, 'cultivation/crop_form.html', context)


@login_required(login_url='/login/')
def visual_section_create(request, layout_id):
    """視覚的区画作成"""
    layout = get_object_or_404(CultivationLayout, id=layout_id)
    
    if request.method == 'POST':
        import json
        positions_json = request.POST.get('positions', '[]')
        name_prefix = request.POST.get('name_prefix', '区画')
        
        try:
            positions = json.loads(positions_json)
        except json.JSONDecodeError:
            messages.error(request, '無効なデータが送信されました。')
            return redirect('cultivation:visual_section_create', layout_id=layout.id)
        
        # 既存区画の位置を取得
        existing_positions = set()
        for section in layout.sections.all():
            existing_positions.add((section.row, section.column))
        
        # 新規区画を作成
        created_count = 0
        for position in positions:
            row, column = map(int, position.split(','))
            if (row, column) not in existing_positions:
                CultivationSection.objects.create(
                    layout=layout,
                    name=f"{name_prefix}-{row}-{column}",
                    row=row,
                    column=column
                )
                created_count += 1
        
        messages.success(request, f'{created_count}個の区画を作成しました。')
        return redirect('cultivation:layout_detail', layout_id=layout.id)
    
    # 既存区画のデータをJSON形式で準備
    existing_sections = []
    for section in layout.sections.all():
        existing_sections.append({
            'id': section.id,
            'name': section.name,
            'row': section.row,
            'column': section.column
        })
    
    import json
    context = {
        'layout': layout,
        'existing_sections': json.dumps(existing_sections),
    }
    return render(request, 'cultivation/visual_section_create.html', context)


# 作物名管理機能
@user_passes_test(is_admin_user, login_url='/login/')
def crop_list(request):
    """作物名一覧表示"""
    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    if is_global_admin(request.user):
        crops = Crop.objects.select_related('organization').all().order_by('organization__name', 'name')
    else:
        crops = crop_queryset_for_organization(current_organization).select_related('organization')
    
    # 検索機能
    search_query = request.GET.get('search', '')
    if search_query:
        crops = crops.filter(name__icontains=search_query)
    
    # 各作物の使用状況を取得
    for crop in crops:
        usage_count = CultivationPlan.objects.filter(crop=crop).count()
        crop.usage_count = usage_count
    
    context = {
        'crops': crops,
        'search_query': search_query,
        'show_organization': is_global_admin(request.user),
    }
    return render(request, 'cultivation/crop_list.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_create_form(request):
    """作物名新規作成"""
    current_organization = get_current_organization(request)
    if not current_organization:
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    if request.method == 'POST':
        form = CropForm(request.POST)
        if form.is_valid():
            crop = form.save(commit=False)
            crop.organization = current_organization
            crop.save()
            messages.success(request, f'作物「{crop.name}」を追加しました')
            return redirect('cultivation:crop_list')
    else:
        form = CropForm()
    
    context = {
        'form': form,
        'title': '新しい作物を追加',
        'is_create': True,
    }
    return render(request, 'cultivation/crop_form.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_edit_form(request, crop_id):
    """作物名編集"""
    current_organization = get_current_organization(request)
    crops = Crop.objects.all() if is_global_admin(request.user) else crop_queryset_for_organization(current_organization)
    try:
        crop = get_object_or_404(crops, id=crop_id)
    except Crop.DoesNotExist:
        messages.error(request, f'作物ID {crop_id} が見つかりません。既に削除されている可能性があります。')
        return redirect('cultivation:crop_list')
    
    if request.method == 'POST':
        form = CropForm(request.POST, instance=crop)
        if form.is_valid():
            crop = form.save()
            messages.success(request, f'作物「{crop.name}」を更新しました')
            return redirect('cultivation:crop_list')
    else:
        form = CropForm(instance=crop)
    
    context = {
        'form': form,
        'crop': crop,
        'title': f'作物「{crop.name}」の編集',
        'is_create': False,
    }
    return render(request, 'cultivation/crop_form.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_delete(request, crop_id):
    """作物名削除"""
    current_organization = get_current_organization(request)
    crops = Crop.objects.all() if is_global_admin(request.user) else crop_queryset_for_organization(current_organization)
    crop = get_object_or_404(crops, id=crop_id)
    
    # 使用状況を確認
    usage_count = CultivationPlan.objects.filter(crop=crop).count()
    
    if request.method == 'POST':
        if usage_count > 0:
            messages.error(request, f'作物「{crop.name}」は{usage_count}件の栽培計画で使用されているため削除できません')
        else:
            crop_name = crop.name
            crop.delete()
            messages.success(request, f'作物「{crop_name}」を削除しました')
        return redirect('cultivation:crop_list')
    
    context = {
        'crop': crop,
        'usage_count': usage_count,
    }
    return render(request, 'cultivation/crop_confirm_delete.html', context)


# OCR関連のビューとインポート
import os
import tempfile
from django.conf import settings
from django.http import JsonResponse
from .ocr_utils import DocumentOCR, LayoutGenerator, OCRValidator
from .layout_visualizer import LayoutVisualizer
from .forms import OCRLayoutForm
from django.views.decorators.http import require_http_methods


@user_passes_test(is_admin_user, login_url='/login/')
# ===== 新しいOCRワークフロー =====

@login_required(login_url='/login/')
def layout_create_ocr_step1(request):
    """OCRレイアウト作成 - ステップ1: 画像アップロード"""
    return render(request, 'cultivation/layout_create_ocr_step1.html')

@login_required(login_url='/login/')
def layout_create_ocr_step2(request):
    """OCRレイアウト作成 - ステップ2: 画像カット"""
    return render(request, 'cultivation/layout_create_ocr_step2.html')

@login_required(login_url='/login/')
def layout_create_ocr_step3(request):
    """OCRレイアウト作成 - ステップ3: OCR読み取り"""
    return render(request, 'cultivation/layout_create_ocr_step3.html')

@require_http_methods(["POST"])
def ocr_process_step3(request):
    """ステップ3でのOCR処理API"""
    try:
        import json
        from django.http import JsonResponse
        
        data = json.loads(request.body)
        image_data = data.get('image_data')
        confidence_threshold = data.get('confidence_threshold', 60)
        preprocess = data.get('preprocess', True)
        language = data.get('language', 'jpn')
        
        if not image_data:
            return JsonResponse({'success': False, 'error': '画像データが見つかりません。'})
        
        # Base64データから画像を復元
        import base64
        import io
        from PIL import Image
        
        # Base64ヘッダーを除去
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # 画像データをデコード
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # OCR処理を実行
        result = process_image_with_ocr(image, confidence_threshold, preprocess, language)
        
        return JsonResponse({
            'success': True,
            'extracted_text': result.get('text', ''),
            'confidence': result.get('confidence', 0),
            'detected_sections': result.get('sections', []),
            'suggested_layout': result.get('suggested_layout', {}),
            'processing_time': result.get('processing_time', 0)
        })
        
    except Exception as e:
        import traceback
        print(f"OCR処理エラー: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': f'OCR処理中にエラーが発生しました: {str(e)}'
        })

@require_http_methods(["POST"])
def ocr_create_layout(request):
    """OCR結果からレイアウトを作成"""
    try:
        import json
        from django.http import JsonResponse
        from .models import CultivationLayout, CultivationSection
        
        layout_name = request.POST.get('layout_name')
        layout_description = request.POST.get('layout_description', '')
        total_rows = int(request.POST.get('total_rows', 4))
        total_columns = int(request.POST.get('total_columns', 6))
        shelf_levels = int(request.POST.get('shelf_levels', 4))
        auto_generate = request.POST.get('auto_generate_sections') == 'on'
        
        ocr_result_data = request.POST.get('ocr_result_data')
        detected_sections_data = request.POST.get('detected_sections_data')
        
        if not layout_name:
            return JsonResponse({'success': False, 'error': 'レイアウト名が必要です。'})
        
        # レイアウトを作成
        layout = CultivationLayout.objects.create(
            name=layout_name,
            description=f"{layout_description}\n\n[OCR自動生成]\n作成日時: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            total_rows=total_rows,
            total_columns=total_columns,
            shelf_levels=shelf_levels,
            created_by=request.user,
            layout_type='grid'
        )
        
        # OCR結果をメタデータとして保存
        if ocr_result_data:
            layout.metadata = {
                'ocr_result': json.loads(ocr_result_data),
                'detected_sections': json.loads(detected_sections_data) if detected_sections_data else [],
                'creation_method': 'ocr_workflow'
            }
            layout.save()
        
        # 自動でセクション生成
        if auto_generate:
            sections_created = 0
            detected_sections = json.loads(detected_sections_data) if detected_sections_data else []
            
            # 検出されたセクションがある場合はそれを使用
            if detected_sections:
                for i, section_data in enumerate(detected_sections[:total_rows * total_columns]):
                    row = i // total_columns + 1
                    column = i % total_columns + 1
                    
                    CultivationSection.objects.create(
                        layout=layout,
                        name=section_data.get('text', f'セクション{i+1}'),
                        row=row,
                        column=column,
                        is_active=True,
                        metadata={
                            'ocr_confidence': section_data.get('confidence', 0),
                            'ocr_detected': True
                        }
                    )
                    sections_created += 1
            
            # 不足分は自動生成
            for i in range(sections_created, total_rows * total_columns):
                row = i // total_columns + 1
                column = i % total_columns + 1
                
                CultivationSection.objects.create(
                    layout=layout,
                    name=f'{layout_name}_R{row}C{column}',
                    row=row,
                    column=column,
                    is_active=True
                )
        
        return JsonResponse({
            'success': True,
            'layout_id': layout.id,
            'redirect_url': f'/cultivation/layouts/{layout.id}/',
            'message': f'レイアウト「{layout_name}」が正常に作成されました。'
        })
        
    except Exception as e:
        import traceback
        print(f"レイアウト作成エラー: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'レイアウト作成中にエラーが発生しました: {str(e)}'
        })

def process_image_with_ocr(image, confidence_threshold=60, preprocess=True, language='jpn'):
    """画像をOCR処理する"""
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageFilter
        import time
        import re
        
        start_time = time.time()
        
        # 前処理
        if preprocess:
            # コントラスト調整
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # シャープネス調整
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # ノイズ除去
            image = image.filter(ImageFilter.MedianFilter())
        
        # OCR実行
        custom_config = f'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー１２３４５６７８９０'
        
        # テキスト抽出
        text = pytesseract.image_to_string(
            image, 
            lang=language, 
            config=custom_config
        ).strip()
        
        # 詳細データ取得（信頼度付き）
        data = pytesseract.image_to_data(
            image, 
            lang=language, 
            config=custom_config, 
            output_type=pytesseract.Output.DICT
        )
        
        # 信頼度でフィルタリング
        filtered_text_parts = []
        detected_sections = []
        
        for i in range(len(data['text'])):
            if int(data['conf'][i]) >= confidence_threshold and data['text'][i].strip():
                filtered_text_parts.append(data['text'][i])
                
                # セクション情報として保存
                detected_sections.append({
                    'text': data['text'][i].strip(),
                    'confidence': int(data['conf'][i]),
                    'x': data['left'][i],
                    'y': data['top'][i],
                    'width': data['width'][i],
                    'height': data['height'][i]
                })
        
        # テキストをフィルタ済みのものに更新
        if filtered_text_parts:
            text = '\n'.join(filtered_text_parts)
        
        # レイアウト提案を生成
        suggested_layout = suggest_layout_from_text(text, detected_sections)
        
        processing_time = time.time() - start_time
        
        return {
            'text': text,
            'confidence': sum(section['confidence'] for section in detected_sections) / max(len(detected_sections), 1),
            'sections': detected_sections,
            'suggested_layout': suggested_layout,
            'processing_time': round(processing_time, 2)
        }
        
    except Exception as e:
        print(f"OCR処理エラー: {e}")
        return {
            'text': '',
            'confidence': 0,
            'sections': [],
            'suggested_layout': {'rows': 4, 'columns': 6, 'levels': 4},
            'processing_time': 0,
            'error': str(e)
        }

def suggest_layout_from_text(text, sections):
    """テキストからレイアウト構成を推測"""
    import re
    
    # デフォルト値
    suggested = {'rows': 4, 'columns': 6, 'levels': 4}
    
    try:
        # 数字パターンを探す
        numbers = re.findall(r'\d+', text)
        if numbers:
            nums = [int(n) for n in numbers if 1 <= int(n) <= 20]
            if nums:
                # 最も頻出する数字を使用
                from collections import Counter
                counter = Counter(nums)
                most_common = counter.most_common(3)
                
                if len(most_common) >= 2:
                    suggested['rows'] = most_common[0][0]
                    suggested['columns'] = most_common[1][0]
                if len(most_common) >= 3:
                    suggested['levels'] = most_common[2][0]
        
        # セクション数からも推測
        section_count = len(sections)
        if section_count > 0:
            # 適切な行列数を計算
            import math
            sqrt_sections = int(math.sqrt(section_count))
            if sqrt_sections > 0:
                suggested['rows'] = min(sqrt_sections + 1, 10)
                suggested['columns'] = min(math.ceil(section_count / suggested['rows']), 10)
    
    except Exception as e:
        print(f"レイアウト推測エラー: {e}")
    
    return suggested

# ===== 既存のOCRビュー =====

@login_required(login_url='/login/')
def layout_create_with_ocr(request):
    """旧OCR作成 → 新OCRワークフロー(step1)に統合済み"""
    return redirect('cultivation:layout_create_ocr_step1')


@login_required(login_url='/login/')
def ocr_preview(request):
    """OCR結果のプレビュー表示"""
    # 権限チェック
    if not is_admin_user(request.user):
        return JsonResponse({'success': False, 'error': 'この機能を使用するには管理者権限が必要です。'}, status=403)
    
    if request.method == 'POST' and request.FILES.get('ocr_file'):
        uploaded_file = request.FILES['ocr_file']
        confidence_threshold = int(request.POST.get('ocr_confidence_threshold', 70))
        
        try:
            # OCR処理（プレビューのみ）
            result = process_ocr_file_preview(uploaded_file, confidence_threshold)
            
            if result.get('success'):
                # 品質検証
                validator = OCRValidator()
                validation = validator.validate_ocr_result(result)
                
                # プレビュー用のデータを構築
                sections = []
                total_confidence = 0
                count = 0
                
                # OCR結果から区画情報を抽出
                pages = result.get('pages', [])
                for page in pages:
                    shelf_info_list = page.get('shelf_info', [])
                    for shelf_info in shelf_info_list:
                        shelf_number = shelf_info.get('shelf_number', '')
                        confidence = shelf_info.get('confidence', 0)
                        position = shelf_info.get('position', {})
                        
                        if shelf_number:
                            sections.append({
                                'shelf_number': shelf_number,
                                'confidence': confidence,
                                'position': position
                            })
                            total_confidence += confidence
                            count += 1
                
                # 平均信頼度を計算
                avg_confidence = total_confidence / count if count > 0 else 0
                
                # グリッドサイズを推定
                max_x = max_y = 0
                for section in sections:
                    pos = section.get('position', {})
                    max_x = max(max_x, pos.get('grid_x', 0))
                    max_y = max(max_y, pos.get('grid_y', 0))
                
                grid_size = f"{max_x + 1}x{max_y + 1}" if max_x > 0 or max_y > 0 else "未定"
                
                # SVGレイアウト図を生成（簡易版）
                layout_svg = f'<svg width="600" height="400" viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg">'
                layout_svg += '<rect width="600" height="400" fill="#f9f9f9" stroke="#ddd" stroke-width="1"/>'
                
                # 区画を描画
                cell_width = 580 / (max_x + 1) if max_x > 0 else 100
                cell_height = 380 / (max_y + 1) if max_y > 0 else 100
                
                for section in sections[:50]:  # 最大50個まで表示
                    pos = section.get('position', {})
                    x = pos.get('grid_x', 0) * cell_width + 10
                    y = pos.get('grid_y', 0) * cell_height + 10
                    
                    # 信頼度に応じた色
                    confidence = section.get('confidence', 0)
                    color = '#4caf50' if confidence > 80 else '#ff9800' if confidence > 60 else '#f44336'
                    
                    layout_svg += f'<rect x="{x}" y="{y}" width="{cell_width - 5}" height="{cell_height - 5}" '
                    layout_svg += f'fill="#e3f2fd" stroke="{color}" stroke-width="2" rx="4" ry="4"/>'
                    layout_svg += f'<text x="{x + cell_width/2}" y="{y + cell_height/2}" '
                    layout_svg += f'text-anchor="middle" dominant-baseline="middle" font-size="12">'
                    layout_svg += f'{section["shelf_number"]}</text>'
                
                layout_svg += '</svg>'
                
                # レスポンスデータ
                response_data = {
                    'success': True,
                    'sections': sections,
                    'sections_count': len(sections),
                    'average_confidence': avg_confidence,
                    'grid_size': grid_size,
                    'layout_svg': layout_svg,
                    'validation': validation
                }
                
                return JsonResponse(response_data)
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', '不明なエラー')
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'ファイルが指定されていません'})


def process_ocr_file(uploaded_file, layout, confidence_threshold, user=None):
    """アップロードされたファイルのOCR処理"""
    temp_file_path = None
    try:
        # OCR設定取得
        ocr_settings = getattr(settings, 'OCR_SETTINGS', {})
        temp_dir = ocr_settings.get('TEMP_DIR', os.path.join(settings.MEDIA_ROOT, 'temp_ocr'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 一時ファイルとして保存
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=f".{uploaded_file.name.split('.')[-1]}", 
            dir=temp_dir
        ) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # OCR処理実行
        ocr = DocumentOCR()
        ocr_result = ocr.process_uploaded_file(temp_file_path)
        
        if ocr_result['success']:
            # レイアウト生成
            generator = LayoutGenerator()
            layout_result = generator.generate_layout_from_ocr(
                ocr_result, 
                layout.name, 
                created_by=user
            )
            
            return layout_result
        else:
            return ocr_result
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # 一時ファイル削除
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass


def process_ocr_file_preview(uploaded_file, confidence_threshold=60):
    """OCRプレビュー処理（レイアウト作成なし）"""
    temp_file_path = None
    try:
        # OCR設定取得
        ocr_settings = getattr(settings, 'OCR_SETTINGS', {})
        temp_dir = ocr_settings.get('TEMP_DIR', os.path.join(settings.MEDIA_ROOT, 'temp_ocr'))
        os.makedirs(temp_dir, exist_ok=True)
        
        # 一時ファイルとして保存
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=f".{uploaded_file.name.split('.')[-1]}", 
            dir=temp_dir
        ) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # OCR処理実行
        ocr = DocumentOCR()
        # 信頼度閾値を動的に設定
        original_threshold = ocr.ocr_settings.get('DEFAULT_CONFIDENCE_THRESHOLD', 60)
        ocr.ocr_settings['DEFAULT_CONFIDENCE_THRESHOLD'] = confidence_threshold
        
        result = ocr.process_uploaded_file(temp_file_path)
        
        # 元の閾値に戻す
        ocr.ocr_settings['DEFAULT_CONFIDENCE_THRESHOLD'] = original_threshold
        
        return result
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        # 一時ファイル削除
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass


@user_passes_test(is_admin_user, login_url='/login/')
def layout_preview_with_layout(request, layout_id):
    """OCR処理結果からレイアウト図を表示するビュー"""
    layout = get_object_or_404(CultivationLayout, id=layout_id)
    
    try:
        # OCR処理が既に実行されているかチェック
        if not layout.import_file:
            messages.warning(request, 'このレイアウトにはOCR処理用のファイルが関連付けられていません。')
            return redirect('cultivation:layout_detail', layout_id=layout.id)
        
        # OCR処理を実行
        ocr_result = process_ocr_file_preview(layout.import_file, confidence_threshold=60)
        
        if not ocr_result.get('success'):
            messages.error(request, f'OCR処理に失敗しました: {ocr_result.get("error", "不明なエラー")}')
            return redirect('cultivation:layout_detail', layout_id=layout.id)
        
        # レイアウト情報を準備
        layout_data = {
            'name': layout.name,
            'description': layout.description,
            'created_at': layout.created_at,
            'created_by': layout.created_by
        }
        
        # LayoutVisualizerを使用してSVGレイアウト図を生成
        try:
            visualizer = LayoutVisualizer(layout_data, ocr_result)
            svg_content = visualizer.generate_svg()
            layout_statistics = visualizer.get_layout_statistics()
            export_data = visualizer.export_layout_data()
        except Exception as e:
            messages.error(request, f'レイアウト図の生成に失敗しました: {str(e)}')
            return redirect('cultivation:layout_detail', layout_id=layout.id)
        
        # 統計情報の計算
        total_sections = layout_statistics['total_sections']
        avg_confidence = layout_statistics['avg_confidence']
        confidence_distribution = layout_statistics['confidence_distribution']
        grid_size = layout_statistics['grid_size']
        
        # 既存の区画数と比較
        existing_sections = layout.sections.count()
        sections_difference = total_sections - existing_sections
        
        # 品質検証
        validator = OCRValidator()
        validation_result = validator.validate_ocr_result(ocr_result)
        
        # コンテキストを構築
        context = {
            'layout': layout,
            'svg_content': svg_content,
            'statistics': {
                'total_sections': total_sections,
                'avg_confidence': avg_confidence,
                'confidence_distribution': confidence_distribution,
                'grid_size': grid_size,
                'existing_sections': existing_sections,
                'sections_difference': sections_difference,
            },
            'validation_result': validation_result,
            'export_data': export_data,
            'ocr_result': ocr_result,
            'layout_data': layout_data,
        }
        
        return render(request, 'cultivation/layout_preview_with_layout.html', context)
        
    except Exception as e:
        messages.error(request, f'レイアウト図の生成処理中にエラーが発生しました: {str(e)}')
        return redirect('cultivation:layout_detail', layout_id=layout.id)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_create_for_level(request, plot_id, level):
    """特定レベルへの作物の新規作成"""
    from .models import Plot, ShelfCrop
    plot = get_object_or_404(Plot, id=plot_id)
    current_organization = get_current_organization(request) or plot.organization
    
    # レベルが有効な範囲内かチェック
    if level < 1 or level > plot.levels:
        messages.error(request, f'レベル{level}は無効です。')
        return redirect('cultivation:plot_management')
    
    # 既存の作物をチェック（収穫予定日が過去でない作物）
    from django.utils import timezone
    existing_crop = ShelfCrop.objects.filter(
        plot=plot, 
        level=level, 
        expected_harvest_date__gt=timezone.now().date()
    ).first()
    if existing_crop:
        messages.warning(request, f'レベル{level}には既に作物「{existing_crop.variety}」が存在します。')
        return redirect('cultivation:plot_management')
    
    if request.method == 'POST':
        crop_id = request.POST.get('crop_id')
        sowing_date = request.POST.get('sowing_date') or None
        pre_planting_date = request.POST.get('pre_planting_date') or None
        planting_date = request.POST.get('planting_date') or None
        expected_harvest_date = request.POST.get('expected_harvest_date') or None
        plate_count = request.POST.get('plate_count') or 0
        notes = request.POST.get('notes', '')

        if crop_id:
            try:
                selected_crop = crop_queryset_for_organization(current_organization).get(id=crop_id)
                variety = selected_crop.name

                ShelfCrop.objects.create(
                    plot=plot,
                    level=level,
                    variety=variety,
                    organization=current_organization or plot.organization,
                    sowing_date=sowing_date,
                    pre_planting_date=pre_planting_date,
                    planting_date=planting_date,
                    expected_harvest_date=expected_harvest_date,
                    plate_count=int(plate_count),
                    notes=notes,
                )
                messages.success(request, f'作物「{variety}」を棚「{plot.shelf_number}」の{level}段に追加しました')
                return redirect('cultivation:plot_management')
            except Crop.DoesNotExist:
                messages.error(request, '選択された作物が見つかりません。')
        else:
            messages.error(request, '作物を選択してください。')

        # バリデーション失敗時は入力値を保持して再表示
        form_data = request.POST

    else:
        form_data = {}

    # 利用可能な作物を取得
    available_crops = crop_queryset_for_organization(current_organization)

    context = {
        'plot': plot,
        'level': level,
        'title': f'棚「{plot.shelf_number}」の{level}段に作物を追加',
        'is_create': True,
        'available_crops': available_crops,
        'form_data': form_data,
    }
    return render(request, 'cultivation/crop_form.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_delete_from_level(request, crop_id):
    """特定レベルから作物を削除"""
    from .models import ShelfCrop
    crop = get_object_or_404(ShelfCrop, id=crop_id)
    
    if request.method == 'POST':
        plot = crop.plot
        level = crop.level
        variety = crop.variety
        crop.delete()
        messages.success(request, f'棚「{plot.shelf_number}」のレベル{level}から作物「{variety}」を削除しました')
        return redirect('cultivation:plot_management')
    
    context = {
        'crop': crop,
    }
    return render(request, 'cultivation/crop_confirm_delete.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def schedule_view(request):
    """栽培スケジュール管理画面（全体）"""
    from .models import ShelfCrop, CultivationSchedule, CropProcess, CultivationLayout, Plot
    from datetime import datetime, timedelta

    # クエリパラメータから日付範囲を取得（デフォルトは今日から60日間）
    today = datetime.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=60)).strftime('%Y-%m-%d'))

    # レイアウト一覧を取得
    layouts = CultivationLayout.objects.all()

    # スケジュール一覧を取得（日付範囲でフィルタ）
    schedules = CultivationSchedule.objects.filter(
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related(
        'shelf_crop', 'shelf_crop__plot', 'process'
    )

    # 追加フィルタを適用
    plot_id = request.GET.get('plot_id')
    crop_name = request.GET.get('crop_name')
    process_id = request.GET.get('process_id')

    if plot_id:
        schedules = schedules.filter(shelf_crop__plot_id=plot_id)
    if crop_name:
        schedules = schedules.filter(shelf_crop__variety__icontains=crop_name)
    if process_id:
        schedules = schedules.filter(process_id=process_id)

    schedules = schedules.order_by('shelf_crop__plot__shelf_number', 'shelf_crop__level', 'start_date')

    # 工程マスターを取得
    processes = CropProcess.objects.all().order_by('display_order')

    # 棚作物一覧を取得（収穫済みでないもの）
    shelf_crops = ShelfCrop.objects.filter(
        harvest_date__isnull=True
    ).select_related('plot').order_by('plot__shelf_number', 'level')

    # フィルタ用の棚リストを取得（重複なし）
    plots = Plot.objects.filter(
        shelf_crops__harvest_date__isnull=True
    ).distinct().order_by('shelf_number')

    context = {
        'layouts': layouts,
        'schedules': schedules,
        'processes': processes,
        'shelf_crops': shelf_crops,
        'plots': plots,
        'start_date': start_date,
        'end_date': end_date,
        'filter_type': 'all',
    }
    return render(request, 'cultivation/schedule_view.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def schedule_view_layout(request, layout_id):
    """栽培スケジュール管理画面（レイアウト別）"""
    from .models import ShelfCrop, CultivationSchedule, CropProcess, CultivationLayout, Plot
    from datetime import datetime, timedelta

    layout = get_object_or_404(CultivationLayout, id=layout_id)

    # クエリパラメータから日付範囲を取得
    today = datetime.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=60)).strftime('%Y-%m-%d'))

    # レイアウト一覧を取得（フィルタ用）
    layouts = CultivationLayout.objects.all()

    # このレイアウトのスケジュールを取得
    schedules = CultivationSchedule.objects.filter(
        shelf_crop__plot__layout=layout,
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related(
        'shelf_crop', 'shelf_crop__plot', 'process'
    )

    # 追加フィルタを適用
    plot_id = request.GET.get('plot_id')
    crop_name = request.GET.get('crop_name')
    process_id = request.GET.get('process_id')

    if plot_id:
        schedules = schedules.filter(shelf_crop__plot_id=plot_id)
    if crop_name:
        schedules = schedules.filter(shelf_crop__variety__icontains=crop_name)
    if process_id:
        schedules = schedules.filter(process_id=process_id)

    schedules = schedules.order_by('shelf_crop__plot__shelf_number', 'shelf_crop__level', 'start_date')

    # 工程マスターを取得
    processes = CropProcess.objects.all().order_by('display_order')

    # このレイアウトの棚作物一覧を取得
    shelf_crops = ShelfCrop.objects.filter(
        plot__layout=layout,
        harvest_date__isnull=True
    ).select_related('plot').order_by('plot__shelf_number', 'level')

    # フィルタ用の棚リストを取得（重複なし）
    plots = Plot.objects.filter(
        layout=layout,
        shelf_crops__harvest_date__isnull=True
    ).distinct().order_by('shelf_number')

    context = {
        'layouts': layouts,
        'current_layout': layout,
        'schedules': schedules,
        'processes': processes,
        'shelf_crops': shelf_crops,
        'plots': plots,
        'start_date': start_date,
        'end_date': end_date,
        'filter_type': 'layout',
    }
    return render(request, 'cultivation/schedule_view.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def schedule_view_plot(request, plot_id):
    """栽培スケジュール管理画面（棚別）"""
    from .models import ShelfCrop, CultivationSchedule, CropProcess, Plot, CultivationLayout
    from datetime import datetime, timedelta

    plot = get_object_or_404(Plot, id=plot_id)

    # クエリパラメータから日付範囲を取得
    today = datetime.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=60)).strftime('%Y-%m-%d'))

    # レイアウト一覧を取得（フィルタ用）
    layouts = CultivationLayout.objects.all()

    # この棚のスケジュールを取得
    schedules = CultivationSchedule.objects.filter(
        shelf_crop__plot=plot,
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related(
        'shelf_crop', 'shelf_crop__plot', 'process'
    )

    # 追加フィルタを適用
    crop_name = request.GET.get('crop_name')
    process_id = request.GET.get('process_id')

    if crop_name:
        schedules = schedules.filter(shelf_crop__variety__icontains=crop_name)
    if process_id:
        schedules = schedules.filter(process_id=process_id)

    schedules = schedules.order_by('shelf_crop__level', 'start_date')

    # 工程マスターを取得
    processes = CropProcess.objects.all().order_by('display_order')

    # この棚の作物一覧を取得
    shelf_crops = ShelfCrop.objects.filter(
        plot=plot,
        harvest_date__isnull=True
    ).select_related('plot').order_by('level')

    # フィルタ用の棚リストを取得（この棚のみ）
    plots = [plot]

    context = {
        'layouts': layouts,
        'current_plot': plot,
        'schedules': schedules,
        'processes': processes,
        'shelf_crops': shelf_crops,
        'plots': plots,
        'start_date': start_date,
        'end_date': end_date,
        'filter_type': 'plot',
    }
    return render(request, 'cultivation/schedule_view.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def schedule_templates(request):
    """栽培テンプレート管理画面"""
    from .models import CropTemplate, Crop, CropProcess
    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # すべてのテンプレートを取得
    templates = CropTemplate.objects.all().prefetch_related(
        'processes', 'processes__process'
    ).select_related('crop').order_by('crop__name', 'name')
    if not is_global_admin(request.user):
        templates = templates.filter(Q(crop__organization=current_organization) | Q(crop__organization__isnull=True))

    # 作物マスターを取得（テンプレート作成用）
    crops = Crop.objects.all().order_by('name') if is_global_admin(request.user) else crop_queryset_for_organization(current_organization)

    # 工程マスターを取得（テンプレート作成用）
    processes = CropProcess.objects.all().order_by('display_order')
    if not is_global_admin(request.user):
        processes = processes.filter(Q(organization=current_organization) | Q(organization__isnull=True))

    context = {
        'templates': templates,
        'crops': crops,
        'processes': processes,
    }
    return render(request, 'cultivation/schedule_templates.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def schedule_export_pdf(request):
    """スケジュールをPDFでエクスポート"""
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from .models import ShelfCrop, CultivationSchedule, CropProcess, CultivationLayout
    from datetime import datetime, timedelta
    import tempfile

    # クエリパラメータから日付範囲を取得
    today = datetime.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=60)).strftime('%Y-%m-%d'))
    layout_id = request.GET.get('layout_id')
    plot_id = request.GET.get('plot_id')

    # スケジュール一覧を取得
    schedules = CultivationSchedule.objects.filter(
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related('shelf_crop', 'shelf_crop__plot', 'process')

    # フィルタを適用
    if layout_id:
        schedules = schedules.filter(shelf_crop__plot__layout_id=layout_id)
    if plot_id:
        schedules = schedules.filter(shelf_crop__plot_id=plot_id)

    schedules = schedules.order_by('shelf_crop__plot__shelf_number', 'shelf_crop__level', 'start_date')

    # 工程マスターを取得
    processes = CropProcess.objects.all().order_by('display_order')

    # 棚作物一覧を取得
    shelf_crops = ShelfCrop.objects.filter(
        harvest_date__isnull=True
    ).select_related('plot').order_by('plot__shelf_number', 'level')

    if layout_id:
        shelf_crops = shelf_crops.filter(plot__layout_id=layout_id)
    if plot_id:
        shelf_crops = shelf_crops.filter(plot_id=plot_id)

    # PDFタイトル
    title = "栽培スケジュール"
    if layout_id:
        layout = CultivationLayout.objects.get(id=layout_id)
        title += f" - {layout.name}"
    elif plot_id:
        from .models import Plot
        plot = Plot.objects.get(id=plot_id)
        title += f" - {plot.shelf_number}"

    # HTMLテンプレートをレンダリング
    context = {
        'title': title,
        'start_date': start_date,
        'end_date': end_date,
        'schedules': schedules,
        'processes': processes,
        'shelf_crops': shelf_crops,
        'export_date': today.strftime('%Y年%m月%d日'),
    }

    html_string = render_to_string('cultivation/schedule_pdf_template.html', context)

    # PDFを生成
    html = HTML(string=html_string)
    pdf_file = html.write_pdf()

    # HTTPレスポンスとして返す
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="schedule_{today.strftime("%Y%m%d")}.pdf"'

    return response


@login_required
def gantt_chart_view(request, layout_id=None):
    """棚ベースのガントチャート表示"""
    from .models import ShelfCrop, CultivationSchedule, CropProcess, CultivationLayout, Plot, ProcessSchedule
    from datetime import datetime, timedelta
    from shift_management.views import get_current_organization
    from shift_management.utils import is_global_admin

    # 組織フィルタリング
    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # クエリパラメータから日付範囲を取得（デフォルトは今日から90日間）
    today = datetime.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=90)).strftime('%Y-%m-%d'))

    # レイアウト一覧を取得
    if is_global_admin(request.user):
        layouts = CultivationLayout.objects.all()
    elif current_organization:
        layouts = CultivationLayout.objects.filter(organization=current_organization)
    else:
        layouts = CultivationLayout.objects.none()

    current_layout = None
    if layout_id:
        current_layout = get_object_or_404(CultivationLayout, id=layout_id)
        # 組織チェック：グローバル管理者でない場合、自組織のレイアウトのみ表示可能
        if not is_global_admin(request.user) and current_organization:
            if current_layout.organization != current_organization:
                messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                return redirect('cultivation:cultivation_top')

    # 棚一覧を取得（組織またはレイアウトでフィルタ）
    if current_layout:
        plots = Plot.objects.filter(layout=current_layout, is_active=True)
    elif current_organization:
        plots = Plot.objects.filter(organization=current_organization, is_active=True)
    else:
        plots = Plot.objects.filter(is_active=True)

    plots = plots.order_by('shelf_number')

    # 工程マスターを取得（組織でフィルタ）
    from django.db.models import Q
    if current_organization:
        processes = CropProcess.objects.filter(
            Q(organization=current_organization) | Q(organization__isnull=True)
        ).order_by('display_order')
    else:
        processes = CropProcess.objects.all().order_by('display_order')

    # 棚作物一覧を取得（ガントチャート用のデータ準備）
    if current_layout:
        shelf_crops = ShelfCrop.objects.filter(
            plot__layout=current_layout,
            harvest_date__isnull=True
        ).select_related('plot').order_by('plot__shelf_number', 'level')
    elif current_organization:
        shelf_crops = ShelfCrop.objects.filter(
            organization=current_organization,
            harvest_date__isnull=True
        ).select_related('plot').order_by('plot__shelf_number', 'level')
    else:
        shelf_crops = ShelfCrop.objects.filter(
            harvest_date__isnull=True
        ).select_related('plot').order_by('plot__shelf_number', 'level')

    # スケジュール一覧を取得（日付範囲でフィルタ）
    schedules_qs = CultivationSchedule.objects.filter(
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related('shelf_crop', 'shelf_crop__plot', 'process')

    if current_layout:
        schedules_qs = schedules_qs.filter(shelf_crop__plot__layout=current_layout)
    elif current_organization:
        schedules_qs = schedules_qs.filter(shelf_crop__organization=current_organization)

    schedules = schedules_qs.order_by('shelf_crop__plot__shelf_number', 'shelf_crop__level', 'start_date')

    # ガントチャート用のデータを構築
    # 縦軸: 棚 + レベル（段）の組み合わせ
    gantt_rows = []
    for plot in plots:
        for level in range(1, plot.levels + 1):
            row_id = f"plot-{plot.id}-level-{level}"
            gantt_rows.append({
                'id': row_id,
                'plot_id': plot.id,
                'level': level,
                'name': f"{plot.shelf_number} {level}段",
                'shelf_number': plot.shelf_number,
            })

    # ガントチャート用のタスクデータを構築
    gantt_tasks = []
    for crop in shelf_crops:
        # 作物自体を1つのタスクとして表示
        row_id = f"plot-{crop.plot.id}-level-{crop.level}"
        task = {
            'id': f"crop-{crop.id}",
            'type': 'crop',
            'name': crop.variety,
            'row_id': row_id,
            'plot_id': crop.plot.id,
            'level': crop.level,
            'start': crop.planting_date.strftime('%Y-%m-%d') if crop.planting_date else today.strftime('%Y-%m-%d'),
            'end': crop.expected_harvest_date.strftime('%Y-%m-%d') if crop.expected_harvest_date else (today + timedelta(days=30)).strftime('%Y-%m-%d'),
            'color': '#4CAF50',  # デフォルト緑色
            'progress': crop.growth_progress_percentage() or 0,
        }
        gantt_tasks.append(task)

    # スケジュール（工程）をタスクとして追加
    for schedule in schedules:
        row_id = f"plot-{schedule.shelf_crop.plot.id}-level-{schedule.shelf_crop.level}"
        task = {
            'id': f"schedule-{schedule.id}",
            'type': 'schedule',
            'name': f"{schedule.shelf_crop.variety} - {schedule.process.name}",
            'row_id': row_id,
            'plot_id': schedule.shelf_crop.plot.id,
            'level': schedule.shelf_crop.level,
            'start': schedule.start_date.strftime('%Y-%m-%d'),
            'end': schedule.end_date.strftime('%Y-%m-%d'),
            'color': schedule.process.color,
            'progress': 100 if schedule.is_completed else 50,
            'process_id': schedule.process.id,
            'process_name': schedule.process.name,
            'shelf_crop_id': schedule.shelf_crop.id,
        }
        gantt_tasks.append(task)

    # ProcessSchedule（新しい工程スケジュール）をタスクとして追加
    process_schedules_qs = ProcessSchedule.objects.filter(
        end_date__gte=start_date,
        start_date__lte=end_date
    ).select_related('plot', 'process')

    if current_layout:
        process_schedules_qs = process_schedules_qs.filter(plot__layout=current_layout)
    elif current_organization:
        process_schedules_qs = process_schedules_qs.filter(organization=current_organization)

    process_schedules = process_schedules_qs.order_by('plot__shelf_number', 'level', 'start_date')

    for ps in process_schedules:
        row_id = f"plot-{ps.plot.id}-level-{ps.level or 1}"
        task = {
            'id': f"process-schedule-{ps.id}",
            'type': 'process-schedule',
            'name': f"{ps.group_name or ''} {ps.process.name}".strip(),
            'row_id': row_id,
            'plot_id': ps.plot.id,
            'level': ps.level or 1,
            'start': ps.start_date.strftime('%Y-%m-%d'),
            'end': ps.end_date.strftime('%Y-%m-%d'),
            'color': ps.process.color,
            'progress': 50,
            'process_id': ps.process.id,
            'process_name': ps.process.name,
            'parent_schedule_id': ps.parent_schedule_id,
            'is_linked': ps.is_linked,
        }
        gantt_tasks.append(task)

    context = {
        'layouts': layouts,
        'current_layout': current_layout,
        'plots': plots,
        'processes': processes,
        'shelf_crops': shelf_crops,
        'schedules': schedules,
        'start_date': start_date,
        'end_date': end_date,
        'gantt_rows': json.dumps(gantt_rows, ensure_ascii=False),
        'gantt_tasks': json.dumps(gantt_tasks, ensure_ascii=False),
    }
    return render(request, 'cultivation/gantt_chart.html', context)


# ============================================================
# 棚割りグリッド
# ============================================================

def _build_shelf_grid(plots, today):
    """
    棚割りグリッドのデータ構造を構築する。

    返す構造:
    {
      level: [
        { 'plot': Plot, 'crop': ShelfCrop|None, 'status': str,
          'is_today': bool, 'today_types': list[str] },
        ...  # plots の順番に対応
      ],
      ...
    }
    plot_list: plots と同じ順番のリスト（テンプレートで列ヘッダー用）
    """
    from .models import ShelfCrop

    if not plots:
        return {}, []

    max_levels = max(p.levels for p in plots)
    plot_list = list(plots)
    plot_ids = [p.id for p in plot_list]

    # 未収穫のShelfCropを一括取得
    crops_qs = ShelfCrop.objects.filter(
        plot_id__in=plot_ids,
        harvest_date__isnull=True,
    ).select_related('plot')

    # (plot_id, level) → ShelfCrop のマップを作成
    crop_map = {}
    for crop in crops_qs:
        key = (crop.plot_id, crop.level)
        # 同じ (plot, level) に複数ある場合は最新を使用
        if key not in crop_map or crop.created_at > crop_map[key].created_at:
            crop_map[key] = crop

    grid = {}
    for level in range(1, max_levels + 1):
        row = []
        for plot in plot_list:
            if level > plot.levels:
                # この棚はこの段数を持たない
                row.append({'plot': plot, 'crop': None, 'status': 'no_level',
                            'is_today': False, 'today_types': []})
                continue

            crop = crop_map.get((plot.id, level))
            if crop:
                status = crop.get_growth_status()
                today_info = crop.is_today_action()
                is_today = today_info['any']
                today_types = [k.replace('is_', '').replace('_today', '')
                               for k, v in today_info.items() if v and k != 'any']
            else:
                status = 'empty'
                is_today = False
                today_types = []

            row.append({
                'plot': plot,
                'crop': crop,
                'status': status,
                'is_today': is_today,
                'today_types': today_types,
            })
        grid[level] = row

    return grid, plot_list


def _get_today_actions(plots, today):
    """今日が作業日の ShelfCrop を収集してリストで返す"""
    from .models import ShelfCrop
    from django.db.models import Q

    crops = ShelfCrop.objects.filter(
        plot__in=plots,
        harvest_date__isnull=True,
    ).filter(
        Q(sowing_date=today) |
        Q(pre_planting_date=today) |
        Q(planting_date=today) |
        Q(expected_harvest_date=today)
    ).select_related('plot').order_by('plot__shelf_number', 'level')

    actions = []
    type_labels = {
        'sowing': '播種日',
        'pre_planting': '仮植日',
        'planting': '定植日',
        'harvest': '収穫予定日',
    }
    for crop in crops:
        for action_type, label in type_labels.items():
            date_field = {
                'sowing': crop.sowing_date,
                'pre_planting': crop.pre_planting_date,
                'planting': crop.planting_date,
                'harvest': crop.expected_harvest_date,
            }[action_type]
            if date_field == today:
                actions.append({
                    'type': action_type,
                    'label': label,
                    'crop': crop,
                    'plot_name': crop.plot.shelf_number,
                    'level': crop.level,
                    'variety': crop.variety,
                    'plate_count': crop.plate_count,
                })
    return actions


@login_required(login_url='/login/')
def shelf_grid_view(request, layout_id=None):
    """棚割りグリッド表示 - タンク別タブ、段×レーンのマス目で状態を一覧表示"""
    from datetime import date as date_type, timedelta

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    today = date_type.today()

    # タンク（レイアウト）一覧
    if is_global_admin(request.user):
        layouts = CultivationLayout.objects.all().order_by('name')
    elif current_organization:
        layouts = CultivationLayout.objects.filter(
            organization=current_organization
        ).order_by('name')
    else:
        layouts = CultivationLayout.objects.none()

    # 表示するタンクを決定
    current_layout = None
    if layout_id:
        current_layout = get_object_or_404(CultivationLayout, id=layout_id)
        if not is_global_admin(request.user) and current_organization:
            if current_layout.organization != current_organization:
                messages.error(request, 'このレイアウトにアクセスする権限がありません。')
                return redirect('cultivation:shelf_grid')
    elif layouts.exists():
        current_layout = layouts.first()

    # レーン（棚）を取得
    if current_layout:
        plots = Plot.objects.filter(
            layout=current_layout, is_active=True
        ).order_by('y_position', 'x_position', 'shelf_number')
    else:
        plots = Plot.objects.none()

    grid, plot_list = _build_shelf_grid(plots, today)
    today_actions = _get_today_actions(plots, today)

    max_levels = max((p.levels for p in plot_list), default=0)

    # ── 日付検索 ──
    DATE_FIELD_MAP = {
        'sowing':   'sowing_date',
        'pre':      'pre_planting_date',
        'planting': 'planting_date',
        'harvest':  'expected_harvest_date',
    }
    search_field   = request.GET.get('sf', '')
    search_from    = request.GET.get('sd_from', '')
    search_to      = request.GET.get('sd_to', '')
    search_results = None

    if search_field and search_field in DATE_FIELD_MAP:
        db_field = DATE_FIELD_MAP[search_field]
        # 組織スコープの作物を対象
        if is_global_admin(request.user):
            qs = ShelfCrop.objects.filter(harvest_date__isnull=True)
        elif current_organization:
            qs = ShelfCrop.objects.filter(
                harvest_date__isnull=True,
                organization=current_organization,
            )
        else:
            qs = ShelfCrop.objects.none()

        # 日付フィルター
        if search_from:
            try:
                qs = qs.filter(**{f'{db_field}__gte': search_from})
            except Exception:
                pass
        if search_to:
            try:
                qs = qs.filter(**{f'{db_field}__lte': search_to})
            except Exception:
                pass
        if not search_from and not search_to:
            # 期間未指定は今日以降30日
            qs = qs.filter(**{f'{db_field}__gte': today,
                               f'{db_field}__lte': today + timedelta(days=30)})

        qs = qs.select_related('plot', 'plot__layout').order_by(db_field, 'plot__shelf_number', 'level')

        search_results = []
        for crop in qs:
            days = crop.days_until_harvest()
            status = crop.get_growth_status()
            display_status = 'overdue' if (days is not None and days < 0) else status
            search_results.append({
                'crop':   crop,
                'plot':   crop.plot,
                'level':  crop.level,
                'status': display_status,
                'days':   days,
                'date_val': getattr(crop, db_field),
            })

    context = {
        'layouts': layouts,
        'current_layout': current_layout,
        'plot_list': plot_list,
        'grid': grid,
        'level_range': range(1, max_levels + 1),
        'today_actions': today_actions,
        'today': today,
        # 検索
        'search_field':   search_field,
        'search_from':    search_from,
        'search_to':      search_to,
        'search_results': search_results,
        'date_field_map': DATE_FIELD_MAP,
    }
    return render(request, 'cultivation/shelf_grid.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def lane_master_settings(request, layout_id=None):
    """レーンマスター設定 — レイアウトごとに全レーンを一覧編集・一括追加"""
    from django.forms import modelformset_factory

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    # レイアウト一覧
    if is_global_admin(request.user):
        layouts = CultivationLayout.objects.all().order_by('name')
    else:
        layouts = CultivationLayout.objects.filter(organization=current_organization).order_by('name')

    # 選択中レイアウト
    current_layout = None
    if layout_id:
        current_layout = get_object_or_404(CultivationLayout, id=layout_id)
    elif layouts.exists():
        current_layout = layouts.first()

    plots = (
        Plot.objects.filter(layout=current_layout).order_by('shelf_number')
        if current_layout else Plot.objects.none()
    )

    PlotFormSet = modelformset_factory(Plot, form=PlotInlineForm, extra=0, can_delete=True)

    formset = PlotFormSet(queryset=plots)
    bulk_form = BulkAddLanesForm()
    formset_errors = False

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_lanes':
            formset = PlotFormSet(request.POST, queryset=plots)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'レーン設定を保存しました')
                if current_layout:
                    return redirect('cultivation:lane_master_settings_layout', layout_id=current_layout.id)
                return redirect('cultivation:lane_master_settings')
            else:
                formset_errors = True

        elif action == 'bulk_add':
            bulk_form = BulkAddLanesForm(request.POST)
            if bulk_form.is_valid() and current_layout:
                prefix = bulk_form.cleaned_data['prefix_text']
                start = bulk_form.cleaned_data['start_number']
                count = bulk_form.cleaned_data['count']
                levels = bulk_form.cleaned_data['levels']
                max_plates = bulk_form.cleaned_data['max_plates']

                org = current_organization or current_layout.organization
                # 既存の最大 x_position を取得して連番で割り当て
                existing_max_x = Plot.objects.filter(layout=current_layout).aggregate(
                    mx=models.Max('x_position')
                )['mx'] or 0

                created = 0
                skipped = 0
                next_x = existing_max_x + 1
                for i in range(start, start + count):
                    shelf_number = f"{prefix}{i}"
                    if not Plot.objects.filter(layout=current_layout, shelf_number=shelf_number).exists():
                        Plot.objects.create(
                            layout=current_layout,
                            shelf_number=shelf_number,
                            levels=levels,
                            max_plates=max_plates,
                            organization=org,
                            x_position=next_x,
                            y_position=0,
                        )
                        next_x += 1
                        created += 1
                    else:
                        skipped += 1

                msg = f'{created}本のレーンを追加しました'
                if skipped:
                    msg += f'（{skipped}本はすでに存在するためスキップ）'
                messages.success(request, msg)
                return redirect('cultivation:lane_master_settings_layout', layout_id=current_layout.id)

        elif action == 'delete_lane':
            plot_id = request.POST.get('plot_id')
            plot = get_object_or_404(Plot, id=plot_id)
            name = plot.shelf_number
            plot.delete()
            messages.success(request, f'レーン「{name}」を削除しました')
            if current_layout:
                return redirect('cultivation:lane_master_settings_layout', layout_id=current_layout.id)
            return redirect('cultivation:lane_master_settings')

    context = {
        'layouts': layouts,
        'current_layout': current_layout,
        'formset': formset,
        'bulk_form': bulk_form,
        'formset_errors': formset_errors,
        'plots_count': plots.count(),
    }
    return render(request, 'cultivation/lane_master_settings.html', context)


# ─────────────────────────────────────────────
#  棚グリッド セル API
# ─────────────────────────────────────────────

def _build_cell_data(plot, level, crop, today):
    """セルの表示用JSONデータを構築するヘルパー"""
    from datetime import date as date_type
    if today is None:
        today = date_type.today()

    if crop is None:
        return {
            'plot_id': plot.id,
            'level': level,
            'status': 'empty',
            'has_crop': False,
            'max_plates': plot.max_plates,
            'shelf_number': plot.shelf_number,
        }

    status = crop.get_growth_status()
    days = crop.days_until_harvest()
    today_info = crop.is_today_action()
    display_status = 'overdue' if (days is not None and days < 0) else status

    fmt = lambda d: d.strftime('%m/%d') if d else ''
    pct = min(100, round(crop.plate_count / plot.max_plates * 100)) if plot.max_plates > 0 else 0

    return {
        'plot_id': plot.id,
        'level': level,
        'shelf_number': plot.shelf_number,
        'status': display_status,
        'has_crop': True,
        'max_plates': plot.max_plates,
        'crop_id': crop.id,
        'variety': crop.variety,
        'plate_count': crop.plate_count,
        'sowing_date': fmt(crop.sowing_date),
        'pre_planting_date': fmt(crop.pre_planting_date),
        'planting_date': fmt(crop.planting_date),
        'expected_harvest_date': fmt(crop.expected_harvest_date),
        'days_until_harvest': days,
        'is_today': today_info['any'],
        'today_types': [k for k, v in today_info.items() if v and k != 'any'],
        'pct': pct,
        'pct_class': 'full' if pct >= 100 else ('warn' if pct >= 80 else ''),
    }


def _generate_alerts_for_org(organization, today):
    """組織の今日のアラートを生成（既存は上書き）"""
    A = CultivationAlert

    # 今日すでに生成済みなら何もしない
    if A.objects.filter(organization=organization, alert_date=today).exists():
        return

    crops = ShelfCrop.objects.filter(
        organization=organization,
        harvest_date__isnull=True,
    ).select_related('plot')

    new_alerts = []
    for crop in crops:
        base = dict(
            organization=organization,
            alert_date=today,
            variety=crop.variety,
            shelf_number=crop.plot.shelf_number if crop.plot else '',
            level=crop.level,
            shelf_crop=crop,
        )

        # 収穫遅延
        if crop.expected_harvest_date and crop.expected_harvest_date < today:
            days = (today - crop.expected_harvest_date).days
            new_alerts.append(A(
                alert_type=A.TYPE_OVERDUE,
                priority=A.PRIORITY_HIGH,
                overdue_days=days,
                message=f"{crop.variety}（{crop.plot.shelf_number} {crop.level}段）が {days}日 収穫遅延",
                **base,
            ))
        # 本日収穫予定
        elif crop.expected_harvest_date == today:
            new_alerts.append(A(
                alert_type=A.TYPE_HARVEST_TODAY,
                priority=A.PRIORITY_HIGH,
                message=f"{crop.variety}（{crop.plot.shelf_number} {crop.level}段）本日収穫予定",
                **base,
            ))
        # 本日定植
        if crop.planting_date == today:
            new_alerts.append(A(
                alert_type=A.TYPE_PLANTING_TODAY,
                message=f"{crop.variety}（{crop.plot.shelf_number} {crop.level}段）本日定植予定",
                **base,
            ))
        # 本日播種
        if crop.sowing_date == today:
            new_alerts.append(A(
                alert_type=A.TYPE_SOWING_TODAY,
                message=f"{crop.variety}（{crop.plot.shelf_number} {crop.level}段）本日播種予定",
                **base,
            ))
        # 本日仮植
        if crop.pre_planting_date == today:
            new_alerts.append(A(
                alert_type=A.TYPE_PRE_TODAY,
                message=f"{crop.variety}（{crop.plot.shelf_number} {crop.level}段）本日仮植予定",
                **base,
            ))

    if new_alerts:
        A.objects.bulk_create(new_alerts, ignore_conflicts=True)


@login_required
def alert_list(request):
    """栽培アラート一覧"""
    from datetime import date as date_type

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    today = date_type.today()

    # 今日のアラートを生成
    if current_organization:
        _generate_alerts_for_org(current_organization, today)

    # 既読にする（POST）
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'read_all':
            CultivationAlert.objects.filter(
                organization=current_organization, is_read=False
            ).update(is_read=True)
        elif action == 'read_one':
            alert_id = request.POST.get('alert_id')
            CultivationAlert.objects.filter(
                id=alert_id, organization=current_organization
            ).update(is_read=True)
        return redirect('cultivation:alert_list')

    # 表示フィルター
    show = request.GET.get('show', 'unread')  # unread / all
    qs = CultivationAlert.objects.filter(organization=current_organization)
    if show == 'unread':
        qs = qs.filter(is_read=False)
    qs = qs.order_by('-priority', '-alert_date', 'alert_type')[:100]

    unread_count = CultivationAlert.objects.filter(
        organization=current_organization, is_read=False
    ).count()

    context = {
        'alerts': qs,
        'unread_count': unread_count,
        'show': show,
        'today': today,
    }
    return render(request, 'cultivation/alert_list.html', context)


@login_required
def alert_unread_count_api(request):
    """未読アラート件数をJSONで返す（ナビバー用）"""
    from django.http import JsonResponse
    from datetime import date as date_type

    current_organization = get_current_organization(request)
    if not current_organization:
        return JsonResponse({'count': 0})

    today = date_type.today()
    _generate_alerts_for_org(current_organization, today)

    count = CultivationAlert.objects.filter(
        organization=current_organization, is_read=False
    ).count()
    return JsonResponse({'count': count})


@login_required
def kpi_dashboard(request):
    """KPI ダッシュボード — 品種×月の収穫目標 vs 実績"""
    from datetime import date as date_type
    from django.db.models import Sum, Q

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    today = date_type.today()
    year  = int(request.GET.get('year',  today.year))
    month = int(request.GET.get('month', today.month))

    # 前後月ナビ用
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # 組織スコープ
    if is_global_admin(request.user):
        org_filter_target = {}
        org_filter_crop   = {}
    else:
        org_filter_target = {'organization': current_organization}
        org_filter_crop   = {'organization': current_organization}

    # 目標一覧
    targets_qs = HarvestTarget.objects.filter(
        year=year, month=month, **org_filter_target
    )
    targets = {t.crop_name: t for t in targets_qs}

    # 実績: 当月に収穫日のある ShelfCrop を品種ごとに集計
    actuals_qs = ShelfCrop.objects.filter(
        harvest_date__year=year,
        harvest_date__month=month,
        harvest_quantity__isnull=False,
        **org_filter_crop,
    ).values('variety').annotate(
        total=Sum('harvest_quantity'),
        count=models.Count('id'),
    )
    actuals = {row['variety']: row for row in actuals_qs}

    # 収穫件数（量なし含む）
    harvested_qs = ShelfCrop.objects.filter(
        harvest_date__year=year,
        harvest_date__month=month,
        **org_filter_crop,
    ).values('variety').annotate(count=models.Count('id'))
    harvested_counts = {row['variety']: row['count'] for row in harvested_qs}

    # 品種リストを統合（目標あり or 実績あり）
    all_varieties = sorted(set(list(targets.keys()) + list(actuals.keys()) + list(harvested_counts.keys())))

    rows = []
    total_target = 0
    total_actual = 0
    for variety in all_varieties:
        t = targets.get(variety)
        a = actuals.get(variety)
        target_qty  = float(t.target_quantity) if t else None
        actual_qty  = float(a['total']) if a else 0.0
        harvest_cnt = harvested_counts.get(variety, 0)
        unit = t.unit if t else (a and 'kg' or 'kg')

        if target_qty:
            pct = min(200, round(actual_qty / target_qty * 100))
            total_target += target_qty
            total_actual += actual_qty
        else:
            pct = None

        rows.append({
            'variety':     variety,
            'target_qty':  target_qty,
            'actual_qty':  actual_qty,
            'harvest_cnt': harvest_cnt,
            'unit':        unit,
            'pct':         pct,
            'has_target':  t is not None,
        })

    # 登録済み品種サジェスト（目標入力フォーム用）
    known_varieties = list(
        crop_queryset_for_organization(current_organization).values_list('name', flat=True).order_by('name')
    )

    # POST: 目標を保存
    if request.method == 'POST':
        crop_name   = request.POST.get('crop_name', '').strip()
        target_qty  = request.POST.get('target_quantity', '').strip()
        unit        = request.POST.get('unit', 'kg').strip() or 'kg'
        p_year      = int(request.POST.get('year',  year))
        p_month     = int(request.POST.get('month', month))
        org         = current_organization

        if crop_name and target_qty and org:
            try:
                qty = float(target_qty)
                HarvestTarget.objects.update_or_create(
                    organization=org,
                    crop_name=crop_name,
                    year=p_year,
                    month=p_month,
                    defaults={'target_quantity': qty, 'unit': unit},
                )
                messages.success(request, f'{crop_name} {p_year}/{p_month:02d} の目標を保存しました')
            except ValueError:
                messages.error(request, '目標量は数値で入力してください')
            except Exception:
                messages.error(request, '目標の保存中にエラーが発生しました')
        return redirect(f"{request.path}?year={p_year}&month={p_month}")

    context = {
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'rows': rows,
        'total_target': total_target,
        'total_actual': total_actual,
        'total_pct': round(total_actual / total_target * 100) if total_target else None,
        'known_varieties': known_varieties,
        'today': today,
    }
    return render(request, 'cultivation/kpi_dashboard.html', context)


@login_required
def variety_master_api(request):
    """品種マスタ一覧をJSON返却（セルモーダルの自動補完・標準日数取得用）"""
    from django.http import JsonResponse
    try:
        current_organization = get_current_organization(request)
        crops = crop_queryset_for_organization(current_organization)
        data = [
            {
                'name': c.name,
                'days_to_pre_planting': c.days_to_pre_planting,
                'days_to_planting': c.days_to_planting,
                'days_to_harvest': c.days_to_harvest,
            }
            for c in crops
        ]
        return JsonResponse({'varieties': data})
    except Exception:
        return JsonResponse({'varieties': []}, status=500)


@login_required
def cell_api(request, plot_id, level):
    """棚グリッドセルのAjax API
    GET  → セルデータをJSON返却
    POST → action: create / update / harvest
    """
    from django.http import JsonResponse
    from datetime import date as date_type

    plot = get_object_or_404(Plot, id=plot_id)
    today = date_type.today()

    if request.method == 'GET':
        crop = ShelfCrop.objects.filter(
            plot=plot, level=level, harvest_date__isnull=True
        ).order_by('-planting_date').first()

        data = _build_cell_data(plot, level, crop, today)
        if crop:
            # モーダルフォーム用に ISO 形式の日付も返す
            data['crop_form'] = {
                'variety': crop.variety,
                'sowing_date': crop.sowing_date.isoformat() if crop.sowing_date else '',
                'pre_planting_date': crop.pre_planting_date.isoformat() if crop.pre_planting_date else '',
                'planting_date': crop.planting_date.isoformat() if crop.planting_date else '',
                'expected_harvest_date': crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else '',
                'plate_count': crop.plate_count,
            }
        return JsonResponse({'success': True, 'cell': data})

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': '不正なリクエスト'}, status=400)

    action = body.get('action', 'update')

    # ── 収穫済みにする ──
    if action == 'harvest':
        crop = ShelfCrop.objects.filter(
            plot=plot, level=level, harvest_date__isnull=True
        ).first()
        if not crop:
            return JsonResponse({'success': False, 'error': '対象の作物が見つかりません'}, status=404)
        crop.harvest_date = today
        qty = body.get('harvest_quantity')
        if qty not in (None, ''):
            try:
                crop.harvest_quantity = float(qty)
            except (ValueError, TypeError):
                pass
        unit = (body.get('harvest_unit') or '').strip()
        if unit:
            crop.harvest_unit = unit
        crop.save()
        return JsonResponse({'success': True, 'cell': _build_cell_data(plot, level, None, today)})

    # ── 日付パース ──
    def parse_date(val):
        val = (val or '').strip()
        if not val:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(val, '%Y-%m-%d').date()
        except ValueError:
            return None

    variety = (body.get('variety') or '').strip()
    if not variety:
        return JsonResponse({'success': False, 'error': '品種名を入力してください'}, status=400)

    plate_count = int(body.get('plate_count') or 0)
    sowing_date = parse_date(body.get('sowing_date'))
    pre_planting_date = parse_date(body.get('pre_planting_date'))
    planting_date = parse_date(body.get('planting_date'))
    expected_harvest_date = parse_date(body.get('expected_harvest_date'))

    # ── 新規作成 ──
    if action == 'create':
        crop = ShelfCrop(
            plot=plot,
            level=level,
            variety=variety,
            plate_count=plate_count,
            sowing_date=sowing_date,
            pre_planting_date=pre_planting_date,
            planting_date=planting_date,
            expected_harvest_date=expected_harvest_date,
        )
        crop.save()
        return JsonResponse({'success': True, 'cell': _build_cell_data(plot, level, crop, today)})

    # ── 更新 ──
    if action == 'update':
        crop = ShelfCrop.objects.filter(
            plot=plot, level=level, harvest_date__isnull=True
        ).order_by('-planting_date').first()
        if not crop:
            return JsonResponse({'success': False, 'error': '対象の作物が見つかりません'}, status=404)
        crop.variety = variety
        crop.plate_count = plate_count
        crop.sowing_date = sowing_date
        crop.pre_planting_date = pre_planting_date
        crop.planting_date = planting_date
        crop.expected_harvest_date = expected_harvest_date
        crop.save()
        return JsonResponse({'success': True, 'cell': _build_cell_data(plot, level, crop, today)})

    return JsonResponse({'success': False, 'error': '不明なアクション'}, status=400)


# ─────────────────────────────────────────────
# ⑥ 月次収穫レポート
# ─────────────────────────────────────────────

def _build_monthly_report_context(request, year, month):
    """月次レポートのコンテキストデータを組み立てる共通ヘルパー"""
    from datetime import date
    from calendar import monthrange
    from django.db.models import Sum, Count

    current_organization = get_current_organization(request)
    global_admin = is_global_admin(request.user)

    _, last_day = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, last_day)

    org_sc_filter = {} if global_admin else {'organization': current_organization}

    # ── 品種別収穫実績 ──
    harvested_qs = (
        ShelfCrop.objects
        .filter(harvest_date__range=[month_start, month_end], **org_sc_filter)
        .values('variety', 'harvest_unit')
        .annotate(total_qty=Sum('harvest_quantity'), count=Count('id'))
        .order_by('variety')
    )
    actuals = {row['variety']: row for row in harvested_qs}

    # ── KPI 目標 ──
    org_ht_filter = {} if global_admin else {'organization': current_organization}
    targets = {
        t.crop_name: t
        for t in HarvestTarget.objects.filter(year=year, month=month, **org_ht_filter)
    }

    all_varieties = sorted(set(actuals.keys()) | set(targets.keys()))
    rows = []
    total_actual = 0.0
    total_target = 0.0
    achieved_count = 0
    for variety in all_varieties:
        a = actuals.get(variety)
        t = targets.get(variety)
        actual_qty   = float(a['total_qty'] or 0) if a else 0.0
        harvest_count = a['count'] if a else 0
        unit         = (a['harvest_unit'] if a else None) or (t.unit if t else 'kg')
        target_qty   = float(t.target_quantity) if t else None
        pct          = round(actual_qty / target_qty * 100, 1) if target_qty else None
        if pct is not None and pct >= 100:
            achieved_count += 1
        total_actual += actual_qty
        if target_qty:
            total_target += target_qty
        rows.append({
            'variety':       variety,
            'actual_qty':    actual_qty,
            'target_qty':    target_qty,
            'unit':          unit,
            'harvest_count': harvest_count,
            'pct':           pct,
        })

    overall_pct = round(total_actual / total_target * 100, 1) if total_target > 0 else None

    # ── 棚稼働率 ──
    org_plot_filter = {} if global_admin else {'layout__organization': current_organization}
    total_levels = sum(
        p.levels for p in Plot.objects.filter(**org_plot_filter).only('levels')
    )
    active_levels = ShelfCrop.objects.filter(
        harvest_date__isnull=True, **org_sc_filter
    ).values('plot_id', 'level').distinct().count()
    empty_levels  = max(total_levels - active_levels, 0)
    occupancy     = round(active_levels / total_levels * 100, 1) if total_levels > 0 else 0.0

    # ── アラート集計（当月） ──
    org_alert_filter = {} if global_admin else {'organization': current_organization}
    alert_qs = (
        CultivationAlert.objects
        .filter(alert_date__range=[month_start, month_end], **org_alert_filter)
        .values('alert_type')
        .annotate(count=Count('id'))
        .order_by('alert_type')
    )
    type_label = dict(CultivationAlert.TYPE_CHOICES)
    alert_summary = [
        {'label': type_label.get(row['alert_type'], row['alert_type']), 'count': row['count']}
        for row in alert_qs
    ]
    total_alerts = sum(r['count'] for r in alert_summary)

    # prev / next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    today = date.today()
    return {
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'rows': rows,
        'total_actual':   round(total_actual, 2),
        'total_target':   round(total_target, 2) if total_target > 0 else None,
        'overall_pct':    overall_pct,
        'achieved_count': achieved_count,
        'total_varieties': len(rows),
        'total_levels':   total_levels,
        'active_levels':  active_levels,
        'empty_levels':   empty_levels,
        'occupancy':      occupancy,
        'alert_summary':  alert_summary,
        'total_alerts':   total_alerts,
        'current_organization': current_organization,
        'export_date': today.strftime('%Y年%m月%d日'),
    }


@login_required
def monthly_report(request):
    """月次収穫レポート（画面）"""
    from datetime import date
    today = date.today()
    try:
        year  = int(request.GET.get('year',  today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect_to_organization_select(request)

    context = _build_monthly_report_context(request, year, month)
    return render(request, 'cultivation/monthly_report.html', context)


@login_required
def monthly_report_pdf(request):
    """月次収穫レポート（PDF出力）"""
    from datetime import date
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from weasyprint import HTML

    today = date.today()
    try:
        year  = int(request.GET.get('year',  today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month

    current_organization = get_current_organization(request)
    if not current_organization and not is_global_admin(request.user):
        return HttpResponse('組織が選択されていません', status=403)

    context = _build_monthly_report_context(request, year, month)
    html_string = render_to_string('cultivation/monthly_report_pdf_template.html', context)
    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename  = f'harvest_report_{year}{month:02d}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
