from django.core.management.base import BaseCommand
from cultivation.models import Plot

class Command(BaseCommand):
    help = '既存の棚の3D座標を初期化する'

    def handle(self, *args, **options):
        plots = Plot.objects.all()
        updated_count = 0
        
        for plot in plots:
            # 現在の3D座標がデフォルト値（全て0）の場合のみ更新
            if plot.threejs_x == 0.0 and plot.threejs_y == 0.0 and plot.threejs_z == 0.0:
                x, y, z = plot.calculate_default_3d_position()
                plot.threejs_x = x
                plot.threejs_y = y
                plot.threejs_z = z
                plot.save()
                updated_count += 1
                self.stdout.write(
                    f'Updated 3D position for {plot.shelf_number}: ({x:.1f}, {y:.1f}, {z:.1f})'
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated 3D positions for {updated_count} plots'
            )
        )