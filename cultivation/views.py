from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db import models
from django.utils import timezone
from django.core.paginator import Paginator
import json
from .models import CultivationLayout, CultivationSection, CultivationPlan, CultivationLog, Crop, Plot, ShelfCrop
from .forms import CultivationLayoutForm, CultivationPlanForm, CultivationLogForm, PlotForm, ShelfCropForm, CultivationSectionForm, CropImageForm, CropForm
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
            'crop_id': None,
            'days_until_harvest': None,
            'progress_percentage': None,
            'planting_date': None,
            'expected_harvest_date': None,
        }
        
        if level_crops:
            crop = level_crops[0]  # 最新の作物
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
            else:
                level_info['status'] = 'growing'
        
        # レベルごとの色を設定
        status_colors = {
            'empty': '#e8f5e9',
            'growing': '#e3f2fd',
            'harvest_ready': '#fff3e0',
            'overdue': '#ffcdd2'
        }
        level_info['color'] = status_colors[level_info['status']]
        
        level_details.append(level_info)
    
    return level_details

# Create your views here.

def is_admin_user(user):
    """管理者権限をチェックする関数"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def cultivation_top(request):
    """栽培計画トップページ"""
    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect('shift_management:organization_select')

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
            
            print(f"DEBUG cultivation_top: Layout '{layout.name}' has {plots_count} plots (reverse FK) vs {direct_count} plots (direct query)")
            
            # 直接クエリの結果を使用
            plots = direct_plots
            plots_count = direct_count
            
        except AttributeError:
            plots = []
            plots_count = 0
            print(f"DEBUG cultivation_top: Layout '{layout.name}' has no plots attribute")
        
        # 作物統計を初期化
        active_crops_count = 0
        harvest_ready_count = 0
        empty_levels_count = 0
        levels_count = 0
        overdue_count = 0
        
        for plot in plots:
            levels_count += plot.levels
            print(f"DEBUG: Processing plot {plot.shelf_number} in layout {layout.name}")
            
            # 共通ヘルパー関数を使用してレベル詳細を取得
            level_details = get_plot_level_details(plot)
            print(f"DEBUG: Plot {plot.shelf_number} level details: {[{l['level']: l['status']} for l in level_details]}")
            
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
        layout.total_levels = levels_count
        layout.active_crops_count = active_crops_count
        layout.harvest_ready_count = harvest_ready_count
        layout.empty_levels_count = empty_levels_count
        layout.overdue_count = overdue_count
        
        print(f"DEBUG: Layout '{layout.name}' final stats: plots={plots_count}, levels={levels_count}, active={active_crops_count}, harvest_ready={harvest_ready_count}, empty={empty_levels_count}, overdue={overdue_count}")
        
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

def layout_list(request):
    """栽培レイアウト一覧ページ"""
    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect('shift_management:organization_select')

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
            
            print(f"DEBUG layout_list: Layout '{layout.name}' has {plots_count} plots (reverse FK) vs {direct_count} plots (direct query)")
            
            # 直接クエリの結果を使用
            plots = direct_plots
            plots_count = direct_count
            
        except AttributeError:
            plots = []
            plots_count = 0
            print(f"DEBUG layout_list: Layout '{layout.name}' has no plots attribute")
        
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
            print(f"DEBUG layout_list: Processing plot {plot.shelf_number} in layout {layout.name}")
            
            # 共通ヘルパー関数を使用してレベル詳細を取得
            level_details = get_plot_level_details(plot)
            print(f"DEBUG layout_list: Plot {plot.shelf_number} level details: {[{l['level']: l['status']} for l in level_details]}")
            
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
        
        print(f"DEBUG: Layout '{layout.name}' final stats: plots={plots_count}, levels={total_levels}, active={active_crops_count}, harvest_ready={harvest_ready_count}, empty={empty_levels_count}, overdue={overdue_count}")
    
    context = {
        'layouts': layouts,
        'total_layouts': layouts.count(),
    }
    return render(request, 'cultivation/layout_list.html', context)

def layout_create(request):
    """改良されたレイアウト作成"""
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect('shift_management:organization_select')

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

def layout_create_simple(request):
    """シンプルなレイアウト作成（従来版）"""
    if request.method == 'POST':
        form = CultivationLayoutForm(request.POST, request.FILES)
        if form.is_valid():
            layout = form.save()
            messages.success(request, f'レイアウト「{layout.name}」を作成しました')
            return redirect('cultivation:layout_detail', layout_id=layout.id)
    else:
        form = CultivationLayoutForm()
    
    context = {
        'form': form,
    }
    return render(request, 'cultivation/layout_form.html', context)

def layout_detail(request, layout_id):
    """レイアウト詳細表示 - 区画または棚区画2D/3D平面図を表示"""
    # layout_idをクエリパラメータとして設定し、plot_grid_viewを呼び出す
    request.GET = request.GET.copy()
    request.GET['layout'] = layout_id
    request.GET['mode'] = 'floor_plan'
    
    # 表示タイプを決定（棚区画を優先）
    try:
        layout = get_object_or_404(CultivationLayout, id=layout_id)
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

def layout_floor_plan(request, layout_id):
    """レイアウトの2D平面図表示（plot_grid_viewをラップ）"""
    # layout_idをクエリパラメータとして設定し、plot_grid_viewを呼び出す
    request.GET = request.GET.copy()
    request.GET['layout'] = layout_id
    request.GET['mode'] = 'floor_plan'
    return plot_grid_view(request)

def plot_management(request):
    """棚区画管理の一元化ページ"""
    from .models import Plot, CultivationLayout
    from collections import defaultdict

    # 組織フィルタリングを適用
    current_organization = get_current_organization(request)

    if not current_organization and not is_global_admin(request.user):
        messages.info(request, '組織を選択してください。')
        return redirect('shift_management:organization_select')

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
    
    # レイアウト別の棚集計
    layouts_with_plots = defaultdict(list)
    uncategorized_plots_count = 0
    for plot in Plot.objects.select_related('layout').all():
        if plot.layout:
            layouts_with_plots[plot.layout].append(plot)
        else:
            layouts_with_plots['未分類'].append(plot)
            uncategorized_plots_count += 1
    
    # 統計情報の計算
    total_plots = plots.count()
    all_plots_count = Plot.objects.count()  # 全棚数（フィルタ無し）
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
                if level_info['status'] == 'overdue':
                    overdue_count += 1
                elif level_info['status'] == 'harvest_ready':
                    harvest_ready_count += 1
                elif level_info['status'] == 'growing':
                    growing_count += 1
        
        if not plot_has_crops:
            empty_count += 1
        
        # 棚全体のステータスを決定
        plot_status = 'empty'
        if any(level['status'] == 'overdue' for level in level_details):
            plot_status = 'overdue'
        elif any(level['status'] == 'harvest_ready' for level in level_details):
            plot_status = 'harvest_ready'
        elif any(level['status'] == 'growing' for level in level_details):
            plot_status = 'growing'
        
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
            'level_details': item['level_details'],
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
            print(f"DEBUG: Using saved position for plot {plot.id}: x={svg_x}, y={svg_y}")
        else:
            svg_x = 50 + (plot.x_position - 1) * 120 
            svg_y = 50 + (plot.y_position - 1) * 80
            print(f"DEBUG: Using default position for plot {plot.id}: x={svg_x}, y={svg_y}")
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
                level_info['crop_id'] = crop.id
                level_info['crop_name'] = crop.variety
                
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
                'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            },
            'shelf_number': plot.shelf_number,
            'levels': plot.levels,
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
    
    import json
    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data)
    except (TypeError, ValueError) as e:
        print(f"ERROR in plot_floor_plan_with_layout: Failed to serialize floor_plan_data: {e}")
        floor_plan_data_json = json.dumps({})
    
    context = {
        'floor_plan_data': floor_plan_data,
        'floor_plan_data_json': floor_plan_data_json,
        'statistics': statistics,
        'display_type': 'plots',
        'selected_layout': selected_layout,  # レイアウト指定
    }
    
    return render(request, 'cultivation/plot_floor_plan.html', context)

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
            print(f"DEBUG: Using saved position for plot {plot.id}: x={svg_x}, y={svg_y}")
        else:
            svg_x = 50 + (plot.x_position - 1) * 120 
            svg_y = 50 + (plot.y_position - 1) * 80
            print(f"DEBUG: Using default position for plot {plot.id}: x={svg_x}, y={svg_y}")
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
                level_info['crop_id'] = crop.id
                level_info['crop_name'] = crop.variety
                
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
                'layout_id': plot.layout_id if hasattr(plot, 'layout_id') and plot.layout_id else None,
            },
            'shelf_number': plot.shelf_number,
            'levels': plot.levels,
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
    
    import json
    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data)
    except (TypeError, ValueError) as e:
        print(f"ERROR in plot_floor_plan: Failed to serialize floor_plan_data: {e}")
        floor_plan_data_json = json.dumps({})
    
    context = {
        'floor_plan_data': floor_plan_data,
        'floor_plan_data_json': floor_plan_data_json,
        'statistics': statistics,
        'display_type': 'plots',
        'selected_layout': None,  # 全レイアウト表示
    }
    
    return render(request, 'cultivation/plot_floor_plan.html', context)

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

def plan_create(request, section_id):
    """栽培計画作成"""
    section = get_object_or_404(CultivationSection, id=section_id)
    
    if request.method == 'POST':
        form = CultivationPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.section = section
            plan.save()
            messages.success(request, f'{section.name}の栽培計画を作成しました')
            return redirect('cultivation:section_detail', section_id=section.id)
    else:
        form = CultivationPlanForm()
    
    context = {
        'form': form,
        'section': section,
        'is_create': True,
    }
    return render(request, 'cultivation/plan_form.html', context)

def plan_edit(request, plan_id):
    """栽培計画編集"""
    plan = get_object_or_404(CultivationPlan, id=plan_id)
    
    if request.method == 'POST':
        form = CultivationPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, f'{plan.section.name}の栽培計画を更新しました')
            return redirect('cultivation:section_detail', section_id=plan.section.id)
    else:
        form = CultivationPlanForm(instance=plan)
    
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
                
                crop = get_object_or_404(Crop, id=crop_id)
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
                    crop=crop,
                    variety=variety,
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
    available_crops = Crop.objects.all()
    
    context = {
        'section': section,
        'plot': plot,
        'level': level,
        'current_crop': current_crop,
        'available_crops': available_crops,
    }
    return render(request, 'cultivation/section_crop_manage.html', context)

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
    
    # レイアウトフィルタパラメータを取得
    layout_id = request.GET.get('layout')
    display_param = request.GET.get('display', 'auto')
    
    # display パラメータで表示タイプを決定
    if display_param == 'plots':
        # 強制的に棚区画を表示
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                plots = Plot.objects.filter(layout=layout)
            except Exception as e:
                layout = None
                plots = Plot.objects.all()
        else:
            plots = Plot.objects.all()
            layout = None
        display_type = 'plots'
    elif display_param == 'sections' or (layout_id and display_param == 'auto'):
        # 栽培区画を表示
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                sections = layout.sections.all()
                
                # auto モードの場合、区画がない場合は棚区画を表示
                if display_param == 'auto' and not sections.exists():
                    plots = Plot.objects.filter(layout=layout)
                    display_type = 'plots'
                else:
                    display_type = 'sections'
            except:
                plots = Plot.objects.all()
                display_type = 'plots'
                layout = None
        else:
            plots = Plot.objects.all()
            display_type = 'plots'
            layout = None
    else:
        # デフォルトは棚区画
        if layout_id:
            try:
                layout = get_object_or_404(CultivationLayout, id=layout_id)
                plots = Plot.objects.filter(layout=layout)
            except:
                layout = None
                plots = Plot.objects.all()
        else:
            plots = Plot.objects.all()
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
                    print(f"DEBUG2: Using saved position for plot {plot.id}: x={svg_x}, y={svg_y}")
                else:
                    svg_x = 50 + plot.x_position * (plot.width * 30 + 15)
                    svg_y = 50 + plot.y_position * (plot.depth * 30 + 15)
                    print(f"DEBUG2: Using default position for plot {plot.id}: x={svg_x}, y={svg_y}")
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
    
    # JSONシリアライゼーションを安全に実行
    try:
        floor_plan_data_json = json.dumps(floor_plan_data)
    except (TypeError, ValueError) as e:
        print(f"ERROR: Failed to serialize floor_plan_data: {e}")
        print(f"ERROR: Data type: {type(floor_plan_data)}")
        if isinstance(floor_plan_data, dict):
            for key, value in floor_plan_data.items():
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    print(f"ERROR: Problem in key '{key}': {type(value)}")
                    if isinstance(value, list):
                        for i, item in enumerate(value):
                            try:
                                json.dumps(item)
                            except (TypeError, ValueError):
                                print(f"ERROR: Problem in list item {i}: {type(item)}")
                                if isinstance(item, dict):
                                    for k, v in item.items():
                                        try:
                                            json.dumps(v)
                                        except (TypeError, ValueError):
                                            print(f"ERROR: Problem in '{k}': {type(v)} = {str(v)[:100]}")
        floor_plan_data_json = json.dumps({})
    
    try:
        plot_details_json = json.dumps(plot_details)
    except (TypeError, ValueError) as e:
        print(f"ERROR: Failed to serialize plot_details: {e}")
        plot_details_json = json.dumps({})
    
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
                print(f"DEBUG3: Using saved position for plot {plot.id}: x={svg_x}, y={svg_y}")
            else:
                svg_x = 50 + plot.x_position * (plot.width * 30 + 15)
                svg_y = 50 + plot.y_position * (plot.depth * 30 + 15)
                print(f"DEBUG3: Using default position for plot {plot.id}: x={svg_x}, y={svg_y}")
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
        try:
            context['plots_floor_plan_data_json'] = json.dumps(plots_floor_plan_data)
        except (TypeError, ValueError) as e:
            print(f"ERROR: Failed to serialize plots_floor_plan_data: {e}")
            context['plots_floor_plan_data_json'] = json.dumps({'plots': []})
    
    # テンプレートを選択
    if view_mode == 'floor_plan':
        if display_type == 'sections':
            template_name = 'cultivation/layout_floor_plan.html'  # 栽培区画専用
        else:
            template_name = 'cultivation/plot_floor_plan.html'    # 棚区画専用
    else:
        template_name = 'cultivation/plot_grid.html'
    
    return render(request, template_name, context)

@user_passes_test(is_admin_user, login_url='/login/')
def plot_detail_view(request, plot_id):
    """棚区画の詳細表示"""
    from .models import Plot
    plot = get_object_or_404(Plot, id=plot_id)
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
        return redirect('shift_management:organization_select')

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
    crops = Crop.objects.all().order_by('name')
    
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
    }
    return render(request, 'cultivation/crop_list.html', context)


@user_passes_test(is_admin_user, login_url='/login/')
def crop_create_form(request):
    """作物名新規作成"""
    if request.method == 'POST':
        form = CropForm(request.POST)
        if form.is_valid():
            crop = form.save()
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
    try:
        crop = get_object_or_404(Crop, id=crop_id)
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
    crop = get_object_or_404(Crop, id=crop_id)
    
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

def layout_create_ocr_step1(request):
    """OCRレイアウト作成 - ステップ1: 画像アップロード"""
    return render(request, 'cultivation/layout_create_ocr_step1.html')

def layout_create_ocr_step2(request):
    """OCRレイアウト作成 - ステップ2: 画像カット"""
    return render(request, 'cultivation/layout_create_ocr_step2.html')

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

def layout_create_with_ocr(request):
    """OCR機能付きレイアウト作成"""
    if request.method == 'POST':
        form = OCRLayoutForm(request.POST, request.FILES)
        if form.is_valid():
            layout = form.save(commit=False)
            layout.created_by = request.user
            layout.save()
            
            ocr_file = form.cleaned_data.get('ocr_file')
            auto_generate = form.cleaned_data.get('auto_generate_sections')
            confidence_threshold = form.cleaned_data.get('ocr_confidence_threshold')
            
            if ocr_file and auto_generate:
                # OCR処理実行
                result = process_ocr_file(ocr_file, layout, confidence_threshold, request.user)
                
                if result['success']:
                    messages.success(
                        request, 
                        f"レイアウトを作成し、{result['sections_count']}個の区画を自動生成しました。"
                    )
                else:
                    messages.warning(
                        request, 
                        f"レイアウトは作成されましたが、OCR処理でエラーが発生しました: {result['error']}"
                    )
            else:
                messages.success(request, "レイアウトを作成しました。")
            
            return redirect('cultivation:layout_detail', layout_id=layout.id)
    else:
        form = OCRLayoutForm()
    
    context = {
        'form': form,
        'title': 'OCR機能付きレイアウト作成'
    }
    return render(request, 'cultivation/layout_create_ocr.html', context)


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
        planting_date = request.POST.get('planting_date')
        expected_harvest_date = request.POST.get('expected_harvest_date')
        notes = request.POST.get('notes', '')
        
        if crop_id and planting_date and expected_harvest_date:
            try:
                selected_crop = Crop.objects.get(id=crop_id)
                # 作物名は登録済み作物から自動取得
                variety = selected_crop.name
                
                current_organization = get_current_organization(request)
                ShelfCrop.objects.create(
                    plot=plot,
                    level=level,
                    variety=variety,
                    organization=current_organization or plot.organization,  # 組織を自動設定
                    planting_date=planting_date,
                    expected_harvest_date=expected_harvest_date,
                    notes=notes
                )
                messages.success(request, f'作物「{variety}」を棚「{plot.shelf_number}」のレベル{level}に追加しました')
                return redirect('cultivation:plot_management')
            except Crop.DoesNotExist:
                messages.error(request, '選択された作物が見つかりません。')
        else:
            messages.error(request, '必要な項目を入力してください。')
    
    # 利用可能な作物を取得
    available_crops = Crop.objects.all().order_by('name')
    
    context = {
        'plot': plot,
        'level': level,
        'title': f'棚「{plot.shelf_number}」のレベル{level}に作物を追加',
        'is_create': True,
        'available_crops': available_crops,
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

    # すべてのテンプレートを取得
    templates = CropTemplate.objects.all().prefetch_related(
        'processes', 'processes__process'
    ).select_related('crop').order_by('crop__name', 'name')

    # 作物マスターを取得（テンプレート作成用）
    crops = Crop.objects.all().order_by('name')

    # 工程マスターを取得（テンプレート作成用）
    processes = CropProcess.objects.all().order_by('display_order')

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