"""
cultivation アプリ用のカスタムテンプレートフィルター
"""
from django import template

register = template.Library()


@register.filter
def filter_by_shelf_crop(schedules, shelf_crop_id):
    """
    スケジュールリストを特定の ShelfCrop ID でフィルタリング

    使用例:
        {% with crop_schedules=schedules|filter_by_shelf_crop:crop.id %}
    """
    if not schedules:
        return []
    return [schedule for schedule in schedules if schedule.shelf_crop_id == shelf_crop_id]


@register.filter
def filter_by_process(schedules, process_id):
    """
    スケジュールリストを特定の工程 ID でフィルタリング

    使用例:
        {% with process_schedules=schedules|filter_by_process:process.id %}
    """
    if not schedules:
        return []
    return [schedule for schedule in schedules if schedule.process_id == process_id]


@register.filter
def filter_active(schedules):
    """
    アクティブなスケジュールのみにフィルタリング

    使用例:
        {% with active_schedules=schedules|filter_active %}
    """
    if not schedules:
        return []
    return [schedule for schedule in schedules if schedule.is_active()]


@register.filter
def filter_completed(schedules):
    """
    完了したスケジュールのみにフィルタリング

    使用例:
        {% with completed_schedules=schedules|filter_completed %}
    """
    if not schedules:
        return []
    return [schedule for schedule in schedules if schedule.is_completed]


@register.filter
def get_item(dictionary, key):
    """辞書からキーで値を取得する。棚割りグリッドのテンプレートで使用。

    使用例:
        {% with row=grid|get_item:level %}
    """
    return dictionary.get(key)
