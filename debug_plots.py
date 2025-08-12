#!/usr/bin/env python
"""
Plot と Layout の関係をデバッグするスクリプト
"""
import os
import sys
import django

# Django設定
sys.path.append('/Users/kuwatataiga/wakakusa-shift-1')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.base')
django.setup()

from cultivation.models import Plot, CultivationLayout, ShelfCrop

print("=== Plot と Layout の関係 ===")
print()

# 全レイアウトを表示
layouts = CultivationLayout.objects.all()
print(f"総レイアウト数: {layouts.count()}")
for layout in layouts:
    print(f"  - Layout {layout.id}: {layout.name}")
    plots = Plot.objects.filter(layout=layout)
    print(f"    棚数: {plots.count()}")
    for plot in plots:
        crops_count = ShelfCrop.objects.filter(plot=plot, harvest_date__isnull=True).count()
        print(f"      - Plot {plot.id}: {plot.shelf_number} (作物数: {crops_count})")

print()

# レイアウトに割り当てられていない棚
unassigned_plots = Plot.objects.filter(layout__isnull=True)
print(f"未割り当て棚数: {unassigned_plots.count()}")
for plot in unassigned_plots:
    crops_count = ShelfCrop.objects.filter(plot=plot, harvest_date__isnull=True).count()
    print(f"  - Plot {plot.id}: {plot.shelf_number} (作物数: {crops_count})")

print()

# 全作物の状況
all_crops = ShelfCrop.objects.filter(harvest_date__isnull=True)
print(f"活動中の作物数: {all_crops.count()}")
for crop in all_crops:
    layout_name = crop.plot.layout.name if crop.plot.layout else "未割り当て"
    print(f"  - 作物 {crop.id}: {crop.variety} (棚: {crop.plot.shelf_number}, レイアウト: {layout_name})")