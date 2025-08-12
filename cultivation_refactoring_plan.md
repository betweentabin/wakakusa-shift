# Cultivation アプリ リファクタリング計画書

## 作成日: 2025-07-14

## 現状分析サマリー

### 主要な問題点

1. **重複したコード**
   - 2つの異なる作物管理システム（`Crop`と`ShelfCrop`）が存在
   - 19箇所で同じ`if request.method == 'POST':`パターンが繰り返されている
   - フォームウィジェットの定義が26回繰り返されている

2. **マジックナンバーとハードコード値**
   - カラーコード: `#808080`, `#ffc107`, `#28a745`
   - 文字数制限: 100文字（名前フィールド）
   - 栽培期間上限: 365日
   - 画像サイズ: 50px, 100px, 500px

3. **パフォーマンス問題**
   - N+1クエリ問題が複数箇所で発生
   - 統計情報が毎回再計算されている
   - prefetch_relatedやselect_relatedが未使用

4. **コード構成の問題**
   - views.pyが716行と巨大
   - ビジネスロジックとビューロジックが混在
   - 抽象化が不足（ベースクラスなし）

## リファクタリング実施計画

### フェーズ1: 基盤整備（優先度: 高）

#### 1.1 定数の抽出
```python
# cultivation/constants.py
class Colors:
    DEFAULT_GRAY = "#808080"
    DEFAULT_YELLOW = "#ffc107" 
    DEFAULT_GREEN = "#28a745"
    
class Limits:
    NAME_MAX_LENGTH = 100
    MAX_CULTIVATION_DAYS = 365
    GRID_SUGGESTION_COUNT = 5
    
class ImageSizes:
    THUMBNAIL = 50
    PREVIEW = 100
    LARGE = 500
```

#### 1.2 ベースモデルの作成
```python
# cultivation/models/base.py
class TimestampedModel(models.Model):
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    
    class Meta:
        abstract = True

class NamedModel(models.Model):
    name = models.CharField("名前", max_length=100)
    
    class Meta:
        abstract = True
```

### フェーズ2: モデル層のリファクタリング（優先度: 高）

#### 2.1 作物管理の統合
- `Crop`と`ShelfCrop`を統合して単一のモデルに
- タイプフィールドで栽培方法を区別

```python
class CropType(models.TextChoices):
    FIELD = 'field', '露地栽培'
    HYDROPONIC = 'hydroponic', '水耕栽培'

class Crop(TimestampedModel, NamedModel):
    type = models.CharField("栽培タイプ", max_length=20, choices=CropType.choices)
    variety = models.CharField("品種", max_length=100)
    cultivation_days = models.IntegerField("栽培日数")
    # 他のフィールド...
```

### フェーズ3: ビュー層のリファクタリング（優先度: 高）

#### 3.1 クラスベースビューへの移行
```python
# cultivation/views/base.py
class CultivationBaseView:
    @method_decorator(user_passes_test(is_admin_user))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class CultivationCreateView(CultivationBaseView, CreateView):
    def form_valid(self, form):
        messages.success(self.request, f"{self.model._meta.verbose_name}を作成しました")
        return super().form_valid(form)
```

#### 3.2 クエリ最適化
```python
# N+1問題の解決例
layouts = CultivationLayout.objects.prefetch_related(
    'sections__plans__crop'
).annotate(
    sections_count=Count('sections'),
    active_plans_count=Count('sections__plans', filter=Q(
        sections__plans__harvest_date_actual__isnull=True
    ))
)
```

### フェーズ4: フォーム層の改善（優先度: 中）

#### 4.1 フォームミックスインの作成
```python
# cultivation/forms/mixins.py
class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = self.get_css_class_for_field(field)
            field.widget.attrs['class'] = css_class
```

### フェーズ5: サービス層の導入（優先度: 中）

#### 5.1 統計サービス
```python
# cultivation/services/statistics.py
class CultivationStatisticsService:
    @staticmethod
    @cache_result(timeout=300)  # 5分キャッシュ
    def get_layout_statistics(layout):
        return {
            'total_sections': layout.sections.count(),
            'active_plans': ...,
            'harvest_ready': ...
        }
```

### フェーズ6: ファイル構造の再編成（優先度: 低）

```
cultivation/
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── crop.py
│   ├── layout.py
│   └── log.py
├── views/
│   ├── __init__.py
│   ├── base.py
│   ├── crop.py
│   ├── layout.py
│   └── mixins.py
├── forms/
│   ├── __init__.py
│   ├── mixins.py
│   └── forms.py
├── services/
│   ├── __init__.py
│   ├── statistics.py
│   └── import_export.py
├── constants.py
└── utils.py
```

## 実装順序

1. **即座に実施可能な改善**（1日）
   - 定数の抽出
   - 明らかなN+1クエリの修正
   - 重複コードの関数化

2. **モデル層の改善**（2-3日）
   - ベースモデルの作成
   - 作物モデルの統合
   - マイグレーションの作成

3. **ビュー層の改善**（3-4日）
   - クラスベースビューへの段階的移行
   - パーミッションの統一
   - クエリの最適化

4. **フォーム・テンプレートの改善**（2日）
   - フォームミックスインの作成
   - テンプレートの共通化

5. **サービス層の導入**（2日）
   - 統計サービスの実装
   - インポート/エクスポートサービス

## 期待される効果

1. **コード量の削減**: 約30-40%のコード削減
2. **パフォーマンス向上**: クエリ数を50%以上削減
3. **保守性の向上**: 責任の分離により変更が容易に
4. **拡張性の向上**: 新機能追加が簡単に
5. **バグの削減**: 重複コードの削除によりバグ発生箇所が減少

## リスクと対策

1. **データ移行リスク**
   - 対策: 段階的な移行とテストの充実

2. **後方互換性**
   - 対策: 旧URLの維持とリダイレクト

3. **学習コスト**
   - 対策: 段階的な移行とドキュメント整備

## 成功指標

- [ ] 重複コードが90%以上削減される
- [ ] ページロード時のクエリ数が50%以上削減される
- [ ] 単体テストカバレッジが80%以上になる
- [ ] 新機能追加時間が50%短縮される