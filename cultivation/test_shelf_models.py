from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from cultivation.models import Plot, ShelfCrop, CropImage
import tempfile
from PIL import Image
import io

class PlotModelTest(TestCase):
    def setUp(self):
        self.plot = Plot.objects.create(
            shelf_number="A-1",
            x_position=1,
            y_position=2,
            levels=3
        )
    
    def test_plot_creation(self):
        self.assertEqual(self.plot.shelf_number, "A-1")
        self.assertEqual(self.plot.x_position, 1)
        self.assertEqual(self.plot.y_position, 2)
        self.assertEqual(self.plot.levels, 3)
    
    def test_plot_str(self):
        self.assertEqual(str(self.plot), "A-1 (1, 2)")
    
    def test_plot_unique_position(self):
        # 同じ位置に別の棚を作成しようとするとエラーになるべき
        with self.assertRaises(Exception):
            Plot.objects.create(
                shelf_number="A-2",
                x_position=1,
                y_position=2,
                levels=2
            )

class ShelfCropModelTest(TestCase):
    def setUp(self):
        self.plot = Plot.objects.create(
            shelf_number="B-1",
            x_position=2,
            y_position=3,
            levels=4
        )
        self.crop = ShelfCrop.objects.create(
            variety="レタス",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timedelta(days=30),
            plot=self.plot
        )
    
    def test_shelf_crop_creation(self):
        self.assertEqual(self.crop.variety, "レタス")
        self.assertEqual(self.crop.plot, self.plot)
        self.assertIsNotNone(self.crop.planting_date)
        self.assertIsNotNone(self.crop.expected_harvest_date)
    
    def test_shelf_crop_str(self):
        self.assertEqual(str(self.crop), f"レタス - B-1")
    
    def test_days_until_harvest(self):
        days = self.crop.days_until_harvest()
        self.assertIsInstance(days, int)
        self.assertGreaterEqual(days, 29)  # 約30日後に設定したので

class CropImageModelTest(TestCase):
    def setUp(self):
        self.plot = Plot.objects.create(
            shelf_number="C-1",
            x_position=3,
            y_position=4,
            levels=2
        )
        self.crop = ShelfCrop.objects.create(
            variety="トマト",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timedelta(days=60),
            plot=self.plot
        )
        
        # テスト用画像を作成
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, 'JPEG')
        image_io.seek(0)
        
        self.crop_image = CropImage.objects.create(
            crop=self.crop,
            image=SimpleUploadedFile("test.jpg", image_io.read(), content_type="image/jpeg"),
            capture_date=timezone.now(),
            notes="テスト画像"
        )
    
    def test_crop_image_creation(self):
        self.assertEqual(self.crop_image.crop, self.crop)
        self.assertIsNotNone(self.crop_image.image)
        self.assertIsNotNone(self.crop_image.capture_date)
        self.assertEqual(self.crop_image.notes, "テスト画像")
    
    def test_crop_image_str(self):
        expected = f"トマト - {self.crop_image.capture_date.strftime('%Y-%m-%d %H:%M')}"
        self.assertEqual(str(self.crop_image), expected)