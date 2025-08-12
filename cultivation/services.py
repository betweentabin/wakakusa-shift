"""
Cultivation アプリケーションのサービス層
"""
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, Any, Optional

class CultivationStatisticsService:
    """栽培統計サービス"""
    
    CACHE_TIMEOUT = 300  # 5分
    
    @classmethod
    def get_overall_statistics(cls) -> Dict[str, Any]:
        """全体統計を取得"""
        cache_key = "cultivation_overall_stats"
        stats = cache.get(cache_key)
        
        if stats is None:
            from .models import CultivationLayout, CultivationSection, CultivationPlan
            
            stats = {
                'total_layouts': CultivationLayout.objects.count(),
                'total_sections': CultivationSection.objects.count(),
                'active_plans': CultivationPlan.objects.filter(
                    crop__isnull=False,
                    harvest_date_actual__isnull=True
                ).count(),
                'harvest_ready': CultivationPlan.objects.filter(
                    harvest_date_planned__lte=timezone.now().date(),
                    harvest_date_actual__isnull=True
                ).count(),
                'completed_harvests': CultivationPlan.objects.filter(
                    harvest_date_actual__isnull=False
                ).count()
            }
            
            cache.set(cache_key, stats, cls.CACHE_TIMEOUT)
        
        return stats
    
    @classmethod
    def get_layout_statistics(cls, layout_id: int) -> Dict[str, Any]:
        """レイアウト別統計を取得"""
        cache_key = f"cultivation_layout_stats_{layout_id}"
        stats = cache.get(cache_key)
        
        if stats is None:
            from .models import CultivationLayout
            
            try:
                layout = CultivationLayout.objects.get(id=layout_id)
                stats = layout.get_statistics()
                cache.set(cache_key, stats, cls.CACHE_TIMEOUT)
            except CultivationLayout.DoesNotExist:
                stats = {
                    'total_sections': 0,
                    'active_plans': 0,
                    'harvest_ready': 0
                }
        
        return stats
    
    @classmethod
    def clear_cache(cls, layout_id: Optional[int] = None):
        """キャッシュをクリア"""
        cache.delete("cultivation_overall_stats")
        if layout_id:
            cache.delete(f"cultivation_layout_stats_{layout_id}")

class CultivationPlanService:
    """栽培計画サービス"""
    
    @classmethod
    def get_harvest_ready_plans(cls, days_ahead: int = 0):
        """収穫可能な計画を取得"""
        from .models import CultivationPlan
        
        target_date = timezone.now().date() + timezone.timedelta(days=days_ahead)
        
        return CultivationPlan.objects.filter(
            harvest_date_planned__lte=target_date,
            harvest_date_actual__isnull=True,
            crop__isnull=False
        ).select_related('crop', 'section', 'section__layout')
    
    @classmethod
    def get_overdue_plans(cls):
        """期限切れの計画を取得"""
        from .models import CultivationPlan
        
        return CultivationPlan.objects.filter(
            harvest_date_planned__lt=timezone.now().date(),
            harvest_date_actual__isnull=True,
            crop__isnull=False
        ).select_related('crop', 'section', 'section__layout')
    
    @classmethod
    def bulk_harvest(cls, plan_ids: list, harvest_date: Optional[str] = None):
        """一括収穫処理"""
        from .models import CultivationPlan
        
        if harvest_date is None:
            harvest_date = timezone.now().date()
        
        plans = CultivationPlan.objects.filter(
            id__in=plan_ids,
            harvest_date_actual__isnull=True
        )
        
        updated_count = plans.update(harvest_date_actual=harvest_date)
        
        # キャッシュクリア
        CultivationStatisticsService.clear_cache()
        
        return updated_count

class CropRecommendationService:
    """作物推奨サービス"""
    
    @classmethod
    def get_seasonal_recommendations(cls, month: Optional[int] = None):
        """季節別推奨作物を取得"""
        from .models import Crop
        
        if month is None:
            month = timezone.now().month
        
        # 季節別の推奨作物マッピング（簡易版）
        seasonal_crops = {
            'spring': [3, 4, 5],  # 春
            'summer': [6, 7, 8],  # 夏
            'autumn': [9, 10, 11], # 秋
            'winter': [12, 1, 2]   # 冬
        }
        
        season = None
        for season_name, months in seasonal_crops.items():
            if month in months:
                season = season_name
                break
        
        # 実際の実装では、作物テーブルに季節情報を追加する
        # ここでは簡易的に全作物を返す
        return Crop.objects.all()[:10]
    
    @classmethod
    def get_companion_plants(cls, crop_id: int):
        """コンパニオンプランツを取得"""
        # 実際の実装では、作物間の相性データベースを参照
        # ここでは簡易的に実装
        from .models import Crop
        
        try:
            crop = Crop.objects.get(id=crop_id)
            # 同じタイプの作物を推奨として返す
            return Crop.objects.filter(
                type=crop.type
            ).exclude(id=crop_id)[:5]
        except Crop.DoesNotExist:
            return Crop.objects.none()

class ImportExportService:
    """インポート/エクスポートサービス"""
    
    @classmethod
    def export_cultivation_data(cls, layout_id: Optional[int] = None):
        """栽培データをエクスポート"""
        from .models import CultivationLayout, CultivationSection, CultivationPlan
        import json
        
        if layout_id:
            layouts = CultivationLayout.objects.filter(id=layout_id)
        else:
            layouts = CultivationLayout.objects.all()
        
        data = []
        for layout in layouts:
            layout_data = {
                'name': layout.name,
                'description': layout.description,
                'sections': []
            }
            
            for section in layout.sections.all():
                section_data = {
                    'name': section.name,
                    'row': section.row,
                    'column': section.column,
                    'description': section.description,
                    'plans': []
                }
                
                for plan in section.plans.all():
                    plan_data = {
                        'crop': plan.crop.name if plan.crop else None,
                        'sowing_date': plan.sowing_date.isoformat() if plan.sowing_date else None,
                        'planting_date': plan.planting_date.isoformat() if plan.planting_date else None,
                        'harvest_date_planned': plan.harvest_date_planned.isoformat() if plan.harvest_date_planned else None,
                        'harvest_date_actual': plan.harvest_date_actual.isoformat() if plan.harvest_date_actual else None,
                        'notes': plan.notes
                    }
                    section_data['plans'].append(plan_data)
                
                layout_data['sections'].append(section_data)
            
            data.append(layout_data)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @classmethod
    def import_cultivation_data(cls, data: str, user=None):
        """栽培データをインポート"""
        import json
        from .models import CultivationLayout, CultivationSection, CultivationPlan, Crop
        
        try:
            import_data = json.loads(data)
            imported_count = 0
            
            for layout_data in import_data:
                layout, created = CultivationLayout.objects.get_or_create(
                    name=layout_data['name'],
                    defaults={
                        'description': layout_data.get('description', ''),
                        'created_by': user
                    }
                )
                
                if created:
                    imported_count += 1
                
                for section_data in layout_data.get('sections', []):
                    section, created = CultivationSection.objects.get_or_create(
                        layout=layout,
                        row=section_data['row'],
                        column=section_data['column'],
                        defaults={
                            'name': section_data['name'],
                            'description': section_data.get('description', ''),
                            'created_by': user
                        }
                    )
                    
                    for plan_data in section_data.get('plans', []):
                        if plan_data.get('crop'):
                            crop, _ = Crop.objects.get_or_create(
                                name=plan_data['crop']
                            )
                            
                            plan = CultivationPlan.objects.create(
                                section=section,
                                crop=crop,
                                sowing_date=plan_data.get('sowing_date'),
                                planting_date=plan_data.get('planting_date'),
                                harvest_date_planned=plan_data.get('harvest_date_planned'),
                                harvest_date_actual=plan_data.get('harvest_date_actual'),
                                notes=plan_data.get('notes', ''),
                                created_by=user
                            )
                            imported_count += 1
            
            # キャッシュクリア
            CultivationStatisticsService.clear_cache()
            
            return imported_count
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"インポートデータの形式が正しくありません: {str(e)}")

class NotificationService:
    """通知サービス"""
    
    @classmethod
    def get_daily_notifications(cls):
        """日次通知を取得"""
        notifications = []
        
        # 収穫可能な作物
        harvest_ready = CultivationPlanService.get_harvest_ready_plans()
        if harvest_ready.exists():
            notifications.append({
                'type': 'harvest_ready',
                'title': '収穫可能な作物があります',
                'message': f'{harvest_ready.count()}件の作物が収穫可能です。',
                'level': 'success'
            })
        
        # 期限切れの作物
        overdue = CultivationPlanService.get_overdue_plans()
        if overdue.exists():
            notifications.append({
                'type': 'overdue',
                'title': '収穫期限を過ぎた作物があります',
                'message': f'{overdue.count()}件の作物が期限切れです。',
                'level': 'warning'
            })
        
        # 明日収穫予定の作物
        tomorrow_harvest = CultivationPlanService.get_harvest_ready_plans(days_ahead=1)
        if tomorrow_harvest.exists():
            notifications.append({
                'type': 'tomorrow_harvest',
                'title': '明日収穫予定の作物があります',
                'message': f'{tomorrow_harvest.count()}件の作物が明日収穫予定です。',
                'level': 'info'
            })
        
        return notifications