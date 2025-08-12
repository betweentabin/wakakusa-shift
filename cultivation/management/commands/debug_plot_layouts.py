from django.core.management.base import BaseCommand
from cultivation.models import Plot, CultivationLayout, ShelfCrop

class Command(BaseCommand):
    help = 'Debug plot and layout relationships'

    def handle(self, *args, **options):
        self.stdout.write("=== Plot と Layout の関係 ===")
        self.stdout.write("")

        # 全レイアウトを表示
        layouts = CultivationLayout.objects.all()
        self.stdout.write(f"総レイアウト数: {layouts.count()}")
        for layout in layouts:
            self.stdout.write(f"  - Layout {layout.id}: {layout.name}")
            plots = Plot.objects.filter(layout=layout)
            self.stdout.write(f"    棚数: {plots.count()}")
            for plot in plots:
                crops_count = ShelfCrop.objects.filter(plot=plot, harvest_date__isnull=True).count()
                self.stdout.write(f"      - Plot {plot.id}: {plot.shelf_number} (作物数: {crops_count})")

        self.stdout.write("")

        # レイアウトに割り当てられていない棚
        unassigned_plots = Plot.objects.filter(layout__isnull=True)
        self.stdout.write(f"未割り当て棚数: {unassigned_plots.count()}")
        for plot in unassigned_plots:
            crops_count = ShelfCrop.objects.filter(plot=plot, harvest_date__isnull=True).count()
            self.stdout.write(f"  - Plot {plot.id}: {plot.shelf_number} (作物数: {crops_count})")

        self.stdout.write("")

        # 全作物の状況
        all_crops = ShelfCrop.objects.filter(harvest_date__isnull=True)
        self.stdout.write(f"活動中の作物数: {all_crops.count()}")
        for crop in all_crops:
            layout_name = crop.plot.layout.name if crop.plot.layout else "未割り当て"
            self.stdout.write(f"  - 作物 {crop.id}: {crop.variety} (棚: {crop.plot.shelf_number}, レイアウト: {layout_name})")