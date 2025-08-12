from django.core.management.base import BaseCommand
from cultivation.models import CultivationSection, Plot


class Command(BaseCommand):
    help = '既存の区画に対して棚を作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には作成せず、作成予定の棚を表示のみ',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # 棚が関連付けられていない区画を取得
        sections_without_plots = CultivationSection.objects.filter(plot__isnull=True)
        
        if not sections_without_plots.exists():
            self.stdout.write(
                self.style.SUCCESS('すべての区画に既に棚が関連付けられています。')
            )
            return
        
        self.stdout.write(f'棚が未関連付けの区画数: {sections_without_plots.count()}')
        
        created_count = 0
        for section in sections_without_plots:
            shelf_number = f"棚-{section.name}"
            
            if dry_run:
                self.stdout.write(f'[DRY RUN] 作成予定: {shelf_number} (区画: {section.name})')
            else:
                plot = Plot.objects.create(
                    layout=section.layout,
                    section=section,
                    shelf_number=shelf_number,
                    x_position=section.column,
                    y_position=section.row,
                    levels=3,  # デフォルトで3段
                    width=1.2,
                    depth=0.6,
                    height_per_level=0.4,
                    base_height=0.8,
                    svg_x=50 + (section.column - 1) * 120,
                    svg_y=50 + (section.row - 1) * 80
                )
                self.stdout.write(f'作成完了: {plot.shelf_number} (区画: {section.name})')
                created_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN完了: {sections_without_plots.count()}個の棚を作成予定')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'完了: {created_count}個の棚を作成しました')
            )