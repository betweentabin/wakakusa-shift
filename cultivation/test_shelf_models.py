from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from cultivation.models import Plot, ShelfCrop, CropImage, CultivationLayout
from shift_management.models import Organization
import tempfile
from PIL import Image
import io


def make_org():
    return Organization.objects.create(name="テスト組織")


def make_layout(org):
    return CultivationLayout.objects.create(name="テストレイアウト", organization=org)


class PlotModelTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot = Plot.objects.create(
            shelf_number="A-1",
            x_position=1,
            y_position=2,
            levels=3,
            layout=self.layout,
            organization=self.org,
        )

    def test_plot_creation(self):
        self.assertEqual(self.plot.shelf_number, "A-1")
        self.assertEqual(self.plot.x_position, 1)
        self.assertEqual(self.plot.y_position, 2)
        self.assertEqual(self.plot.levels, 3)

    def test_plot_str(self):
        # __str__ は "A-1 (1, 2) - 3段" 形式
        self.assertIn("A-1", str(self.plot))

    def test_plot_unique_position(self):
        # 同じレイアウト・同じ座標に別の棚を作成しようとするとエラー
        with self.assertRaises(Exception):
            Plot.objects.create(
                shelf_number="A-2",
                x_position=1,
                y_position=2,
                levels=2,
                layout=self.layout,
                organization=self.org,
            )


class ShelfCropModelTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot = Plot.objects.create(
            shelf_number="B-1",
            x_position=2,
            y_position=3,
            levels=4,
            layout=self.layout,
            organization=self.org,
        )
        self.crop = ShelfCrop.objects.create(
            variety="レタス",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timedelta(days=30),
            plot=self.plot,
            organization=self.org,
        )

    def test_shelf_crop_creation(self):
        self.assertEqual(self.crop.variety, "レタス")
        self.assertEqual(self.crop.plot, self.plot)
        self.assertIsNotNone(self.crop.planting_date)
        self.assertIsNotNone(self.crop.expected_harvest_date)

    def test_shelf_crop_str(self):
        self.assertIn("レタス", str(self.crop))
        self.assertIn("B-1", str(self.crop))

    def test_days_until_harvest(self):
        days = self.crop.days_until_harvest()
        self.assertIsInstance(days, int)
        self.assertGreaterEqual(days, 29)

    def test_get_growth_status_planted(self):
        # planting_date が今日以前 → planted
        self.assertEqual(self.crop.get_growth_status(), 'planted')

    def test_get_growth_status_sowing(self):
        crop = ShelfCrop.objects.create(
            variety="ほうれん草",
            sowing_date=timezone.now().date(),
            plot=self.plot,
            organization=self.org,
        )
        self.assertEqual(crop.get_growth_status(), 'sowing')

    def test_get_growth_status_harvest_ready(self):
        crop = ShelfCrop.objects.create(
            variety="収穫テスト",
            expected_harvest_date=timezone.now().date() - timedelta(days=1),
            plot=self.plot,
            organization=self.org,
        )
        self.assertEqual(crop.get_growth_status(), 'harvest_ready')

    def test_get_growth_status_harvested(self):
        self.crop.harvest_date = timezone.now().date()
        self.crop.save()
        self.assertEqual(self.crop.get_growth_status(), 'harvested')


class CropImageModelTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot = Plot.objects.create(
            shelf_number="C-1",
            x_position=3,
            y_position=4,
            levels=2,
            layout=self.layout,
            organization=self.org,
        )
        self.crop = ShelfCrop.objects.create(
            variety="トマト",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timedelta(days=60),
            plot=self.plot,
            organization=self.org,
        )

        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, 'JPEG')
        image_io.seek(0)

        self.crop_image = CropImage.objects.create(
            crop=self.crop,
            image=SimpleUploadedFile("test.jpg", image_io.read(), content_type="image/jpeg"),
            capture_date=timezone.now(),
            notes="テスト画像",
        )

    def test_crop_image_creation(self):
        self.assertEqual(self.crop_image.crop, self.crop)
        self.assertIsNotNone(self.crop_image.image)
        self.assertIsNotNone(self.crop_image.capture_date)
        self.assertEqual(self.crop_image.notes, "テスト画像")

    def test_crop_image_str(self):
        self.assertIn("トマト", str(self.crop_image))
