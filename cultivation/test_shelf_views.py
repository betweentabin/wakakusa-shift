from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from cultivation.models import Plot, ShelfCrop, CropImage
from PIL import Image
import io

class PlotGridViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # テスト用のPlotとCropを作成
        self.plot1 = Plot.objects.create(shelf_number="A-1", x_position=0, y_position=0, levels=3)
        self.plot2 = Plot.objects.create(shelf_number="A-2", x_position=1, y_position=0, levels=3)
        self.plot3 = Plot.objects.create(shelf_number="B-1", x_position=0, y_position=1, levels=2)
        
        self.crop1 = ShelfCrop.objects.create(
            variety="レタス",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=30),
            plot=self.plot1
        )
    
    def test_plot_grid_view_get(self):
        response = self.client.get(reverse('cultivation:plot_grid'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A-1")
        self.assertContains(response, "A-2")
        self.assertContains(response, "B-1")
        self.assertContains(response, "レタス")
    
    def test_plot_grid_view_grid_structure(self):
        response = self.client.get(reverse('cultivation:plot_grid'))
        self.assertEqual(response.status_code, 200)
        # グリッド構造が正しく生成されているか確認
        self.assertIn('grid', response.context)
        grid = response.context['grid']
        self.assertEqual(len(grid), 2)  # 2行
        self.assertEqual(len(grid[0]), 2)  # 各行2列

class PlotDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.plot = Plot.objects.create(shelf_number="C-1", x_position=2, y_position=2, levels=4)
        self.crop = ShelfCrop.objects.create(
            variety="トマト",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=60),
            plot=self.plot
        )
    
    def test_plot_detail_view(self):
        response = self.client.get(reverse('cultivation:plot_detail', args=[self.plot.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C-1")
        self.assertContains(response, "トマト")

class CropImageUploadViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.plot = Plot.objects.create(shelf_number="D-1", x_position=3, y_position=3, levels=2)
        self.crop = ShelfCrop.objects.create(
            variety="キュウリ",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=45),
            plot=self.plot
        )
    
    def test_image_upload_view_get(self):
        response = self.client.get(reverse('cultivation:crop_image_upload', args=[self.crop.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "画像アップロード")
    
    def test_image_upload_view_post(self):
        # テスト用画像を作成
        image = Image.new('RGB', (100, 100), color='green')
        image_io = io.BytesIO()
        image.save(image_io, 'JPEG')
        image_io.seek(0)
        
        response = self.client.post(
            reverse('cultivation:crop_image_upload', args=[self.crop.pk]),
            {
                'image': SimpleUploadedFile("test_upload.jpg", image_io.read(), content_type="image/jpeg"),
                'notes': 'テストアップロード'
            }
        )
        
        self.assertEqual(response.status_code, 302)  # リダイレクト
        self.assertEqual(CropImage.objects.filter(crop=self.crop).count(), 1)
        
        uploaded_image = CropImage.objects.get(crop=self.crop)
        self.assertEqual(uploaded_image.notes, 'テストアップロード')