from django.core.management.base import BaseCommand
from cultivation.models import Plot, CultivationLayout

class Command(BaseCommand):
    help = 'Assign unassigned plots to layouts'

    def add_arguments(self, parser):
        parser.add_argument('--layout-id', type=int, help='Layout ID to assign plots to')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        layout_id = options['layout_id']
        
        # 未割り当ての棚を取得
        unassigned_plots = Plot.objects.filter(layout__isnull=True)
        self.stdout.write(f"未割り当て棚数: {unassigned_plots.count()}")
        
        if unassigned_plots.count() == 0:
            self.stdout.write("全ての棚が既にレイアウトに割り当てられています。")
            return
        
        # レイアウトを選択
        if layout_id:
            try:
                target_layout = CultivationLayout.objects.get(id=layout_id)
                self.stdout.write(f"指定されたレイアウト: {target_layout.name}")
            except CultivationLayout.DoesNotExist:
                self.stdout.write(f"レイアウトID {layout_id} が見つかりません。")
                return
        else:
            # デフォルトレイアウトを作成または取得
            target_layout, created = CultivationLayout.objects.get_or_create(
                name="デフォルトレイアウト",
                defaults={'description': '自動作成されたデフォルトレイアウト'}
            )
            if created:
                self.stdout.write(f"新しいレイアウトを作成しました: {target_layout.name}")
            else:
                self.stdout.write(f"既存のデフォルトレイアウトを使用: {target_layout.name}")
        
        # 棚を割り当て
        for plot in unassigned_plots:
            if dry_run:
                self.stdout.write(f"[DRY-RUN] Plot {plot.id} ({plot.shelf_number}) を {target_layout.name} に割り当て予定")
            else:
                plot.layout = target_layout
                plot.save()
                self.stdout.write(f"Plot {plot.id} ({plot.shelf_number}) を {target_layout.name} に割り当てました")
        
        if dry_run:
            self.stdout.write("\n--dry-run フラグが指定されているため、実際の変更は行われませんでした。")
            self.stdout.write("実際に実行するには --dry-run を外してコマンドを再実行してください。")
        else:
            self.stdout.write(f"\n{unassigned_plots.count()} 個の棚を {target_layout.name} に割り当てました。")