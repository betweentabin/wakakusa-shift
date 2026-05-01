"""
cultivation アプリのAPI Views
"""
from datetime import timedelta, date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q

from .models import (
    CropProcess,
    CultivationSchedule,
    CropTemplate,
    CropTemplateProcess,
    ShelfCrop,
    ProcessSchedule,
    LaneConfig,
    HolidayConfig,
    Holiday,
    Plot
)
from .api_serializers import (
    CropProcessSerializer,
    CultivationScheduleSerializer,
    CropTemplateSerializer,
    ScheduleCreateFromTemplateSerializer,
    ShelfCropWithSchedulesSerializer,
    ShelfCropSerializer,
    ProcessScheduleSerializer,
    ProcessScheduleMoveSerializer,
    LaneConfigSerializer,
    HolidayConfigSerializer,
    HolidaySerializer
)
from shift_management.utils import get_current_organization


class CropProcessViewSet(viewsets.ModelViewSet):
    """
    栽培工程マスターのViewSet
    """
    queryset = CropProcess.objects.all()
    serializer_class = CropProcessSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """組織でフィルタリング"""
        queryset = super().get_queryset()
        organization = get_current_organization(self.request)

        if organization:
            # 組織固有 or 共通（organization=null）の工程を取得
            queryset = queryset.filter(
                Q(organization=organization) | Q(organization__isnull=True)
            )

        # アクティブなもののみ
        queryset = queryset.filter(is_active=True)

        return queryset.order_by('display_order')

    def perform_create(self, serializer):
        """作成時に組織を設定"""
        organization = get_current_organization(self.request)
        serializer.save(organization=organization)


class CultivationScheduleViewSet(viewsets.ModelViewSet):
    """
    栽培スケジュールのViewSet
    """
    queryset = CultivationSchedule.objects.all().select_related(
        'shelf_crop', 'shelf_crop__plot', 'process'
    )
    serializer_class = CultivationScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """クエリパラメータでフィルタリング"""
        queryset = super().get_queryset()

        # 開始日・終了日でフィルタ
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(end_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)

        # 棚IDでフィルタ
        plot_id = self.request.query_params.get('plot_id')
        if plot_id:
            queryset = queryset.filter(shelf_crop__plot_id=plot_id)

        # 作物IDでフィルタ（ShelfCropのvarietyで部分一致）
        crop_name = self.request.query_params.get('crop_name')
        if crop_name:
            queryset = queryset.filter(shelf_crop__variety__icontains=crop_name)

        # 工程IDでフィルタ
        process_id = self.request.query_params.get('process_id')
        if process_id:
            queryset = queryset.filter(process_id=process_id)

        # レイアウトIDでフィルタ
        layout_id = self.request.query_params.get('layout_id')
        if layout_id:
            queryset = queryset.filter(shelf_crop__plot__layout_id=layout_id)

        return queryset.order_by('start_date', 'shelf_crop')


class CropTemplateViewSet(viewsets.ModelViewSet):
    """
    栽培テンプレートのViewSet
    """
    queryset = CropTemplate.objects.all().prefetch_related(
        'processes', 'processes__process'
    )
    serializer_class = CropTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """クエリパラメータでフィルタリング"""
        queryset = super().get_queryset()

        # 作物IDでフィルタ
        crop_id = self.request.query_params.get('crop_id')
        if crop_id:
            queryset = queryset.filter(crop_id=crop_id)

        return queryset.order_by('crop__name', 'name')


class ShelfCropViewSet(viewsets.ModelViewSet):
    """
    棚作物のViewSet（ガントチャート用）
    """
    queryset = ShelfCrop.objects.all().select_related('plot', 'organization')
    serializer_class = ShelfCropSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """クエリパラメータでフィルタリング"""
        queryset = super().get_queryset()

        # 棚IDでフィルタ
        plot_id = self.request.query_params.get('plot_id')
        if plot_id:
            queryset = queryset.filter(plot_id=plot_id)

        # レイアウトIDでフィルタ
        layout_id = self.request.query_params.get('layout_id')
        if layout_id:
            queryset = queryset.filter(plot__layout_id=layout_id)

        # 組織IDでフィルタ
        organization_id = self.request.query_params.get('organization_id')
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        # 収穫済みを除外（デフォルト）
        include_harvested = self.request.query_params.get('include_harvested', 'false')
        if include_harvested.lower() != 'true':
            queryset = queryset.filter(harvest_date__isnull=True)

        return queryset.order_by('plot__shelf_number', 'level')

    def perform_create(self, serializer):
        """作成時に組織を自動設定"""
        plot = serializer.validated_data.get('plot')
        organization = plot.organization if plot else None
        serializer.save(organization=organization)


# カスタムアクション: テンプレートからスケジュールを作成
@action(detail=False, methods=['post'], url_path='from-template')
def create_schedule_from_template(request):
    """
    テンプレートからスケジュールを自動生成するカスタムアクション
    """
    serializer = ScheduleCreateFromTemplateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # バリデート済みデータを取得
    shelf_crop_id = serializer.validated_data['shelf_crop_id']
    template_id = serializer.validated_data['template_id']
    start_date = serializer.validated_data['start_date']

    # ShelfCropとTemplateを取得
    try:
        shelf_crop = ShelfCrop.objects.get(id=shelf_crop_id)
        template = CropTemplate.objects.prefetch_related('processes__process').get(id=template_id)
    except (ShelfCrop.DoesNotExist, CropTemplate.DoesNotExist) as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_404_NOT_FOUND
        )

    # テンプレートの工程からスケジュールを作成
    created_schedules = []

    for template_process in template.processes.all():
        # 開始日と終了日を計算
        schedule_start = start_date + timedelta(days=template_process.start_offset_days)
        schedule_end = schedule_start + timedelta(days=template_process.duration_days - 1)

        # スケジュールを作成
        schedule = CultivationSchedule.objects.create(
            shelf_crop=shelf_crop,
            process=template_process.process,
            start_date=schedule_start,
            end_date=schedule_end,
            notes=f"テンプレート「{template.name}」から自動生成"
        )
        created_schedules.append(schedule)

    # 作成したスケジュールをシリアライズして返す
    result_serializer = CultivationScheduleSerializer(created_schedules, many=True)

    return Response({
        'message': f'{len(created_schedules)}件のスケジュールを作成しました。',
        'schedules': result_serializer.data
    }, status=status.HTTP_201_CREATED)


# ==========================================
# ガントチャート機能用ViewSet
# ==========================================

class ProcessScheduleViewSet(viewsets.ModelViewSet):
    """
    工程スケジュール（ガントチャートの帯）のViewSet
    """
    queryset = ProcessSchedule.objects.all().select_related(
        'organization', 'plot', 'process', 'parent_schedule'
    )
    serializer_class = ProcessScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """組織と日付範囲でフィルタリング"""
        queryset = super().get_queryset()
        organization = get_current_organization(self.request)

        if organization:
            queryset = queryset.filter(organization=organization)

        # 開始日・終了日でフィルタ
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(end_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)

        # 棚IDでフィルタ
        plot_id = self.request.query_params.get('plot_id')
        if plot_id:
            queryset = queryset.filter(plot_id=plot_id)

        # レイアウトIDでフィルタ
        layout_id = self.request.query_params.get('layout_id')
        if layout_id:
            queryset = queryset.filter(plot__layout_id=layout_id)

        # 段でフィルタ
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        return queryset.order_by('plot__shelf_number', 'level', 'start_date')

    def perform_create(self, serializer):
        """作成時に組織を自動設定"""
        organization = get_current_organization(self.request)
        serializer.save(organization=organization)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """スケジュールを移動（連携する子スケジュールも移動）"""
        schedule = self.get_object()
        serializer = ProcessScheduleMoveSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        days_offset = serializer.validated_data['days_offset']
        move_children = serializer.validated_data.get('move_children', True)

        schedule.move_schedule(days_offset, move_children=move_children)

        result_serializer = ProcessScheduleSerializer(schedule)
        return Response(result_serializer.data)


class LaneConfigViewSet(viewsets.ModelViewSet):
    """
    レーン設定のViewSet
    """
    queryset = LaneConfig.objects.all().select_related('organization', 'plot')
    serializer_class = LaneConfigSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # レーン設定は全件取得するためページネーション無効

    def get_queryset(self):
        """組織でフィルタリング"""
        queryset = super().get_queryset()
        organization = get_current_organization(self.request)

        if organization:
            queryset = queryset.filter(organization=organization)

        # 棚IDでフィルタ
        plot_id = self.request.query_params.get('plot_id')
        if plot_id:
            queryset = queryset.filter(plot_id=plot_id)

        return queryset.order_by('plot__shelf_number', 'level')

    def perform_create(self, serializer):
        """作成時に組織を自動設定"""
        organization = get_current_organization(self.request)
        serializer.save(organization=organization)


class HolidayConfigViewSet(viewsets.ModelViewSet):
    """
    休日設定のViewSet
    """
    queryset = HolidayConfig.objects.all().prefetch_related('holidays')
    serializer_class = HolidayConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """組織でフィルタリング"""
        queryset = super().get_queryset()
        organization = get_current_organization(self.request)

        if organization:
            queryset = queryset.filter(organization=organization)

        return queryset

    def perform_create(self, serializer):
        """作成時に組織を自動設定"""
        organization = get_current_organization(self.request)
        serializer.save(organization=organization)


class HolidayViewSet(viewsets.ModelViewSet):
    """
    個別休日のViewSet
    """
    queryset = Holiday.objects.all().select_related('holiday_config')
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """休日設定でフィルタリング"""
        queryset = super().get_queryset()

        holiday_config_id = self.request.query_params.get('holiday_config_id')
        if holiday_config_id:
            queryset = queryset.filter(holiday_config_id=holiday_config_id)

        # 組織でフィルタ
        organization = get_current_organization(self.request)
        if organization:
            queryset = queryset.filter(holiday_config__organization=organization)

        return queryset.order_by('date')


class GanttDataAPIView(APIView):
    """
    ガントチャート表示用の統合データAPI
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """ガントチャートに必要な全データを取得"""
        organization = get_current_organization(request)

        if not organization:
            return Response(
                {'error': '組織が選択されていません'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 日付範囲を取得（デフォルトは今月）
        from datetime import datetime
        import calendar

        today = date.today()
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = today.replace(day=1)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = today.replace(day=last_day)

        # レイアウトIDでフィルタ（オプション）
        layout_id = request.query_params.get('layout_id')

        # 棚（レーン）データを取得
        plots_queryset = Plot.objects.filter(
            organization=organization,
            is_active=True
        )
        if layout_id:
            plots_queryset = plots_queryset.filter(layout_id=layout_id)

        plots = plots_queryset.order_by('shelf_number')

        # レーンデータを構築（棚+段の組み合わせ）
        lanes = []
        for plot in plots:
            for level in range(1, plot.levels + 1):
                lanes.append({
                    'id': f"{plot.id}-{level}",
                    'plot_id': plot.id,
                    'plot_name': plot.shelf_number,
                    'level': level,
                    'label': f"{plot.shelf_number} - {level}段"
                })

        # スケジュールを取得
        schedules = ProcessSchedule.objects.filter(
            organization=organization,
            end_date__gte=start_date,
            start_date__lte=end_date
        ).select_related('process', 'plot')

        if layout_id:
            schedules = schedules.filter(plot__layout_id=layout_id)

        # 工程マスタを取得
        processes = CropProcess.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True),
            is_active=True
        ).order_by('display_order')

        # 休日設定を取得
        try:
            holiday_config = HolidayConfig.objects.prefetch_related('holidays').get(
                organization=organization
            )
        except HolidayConfig.DoesNotExist:
            holiday_config = None

        # レスポンスを構築
        return Response({
            'lanes': lanes,
            'schedules': ProcessScheduleSerializer(schedules, many=True).data,
            'processes': CropProcessSerializer(processes, many=True).data,
            'holiday_config': HolidayConfigSerializer(holiday_config).data if holiday_config else None,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        })
