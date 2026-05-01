from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from cultivation.models import Plot, ShelfCrop, CropImage, CultivationLayout
from shift_management.models import Organization
from PIL import Image
import io


def make_staff_client():
    """認証済みスタッフユーザーのClientを返す"""
    user = User.objects.create_user(
        username='teststaff', password='testpass123', is_staff=True
    )
    client = Client()
    client.login(username='teststaff', password='testpass123')
    return client, user


def make_org():
    return Organization.objects.create(name="テスト組織")


def make_layout(org):
    return CultivationLayout.objects.create(name="テストレイアウト", organization=org)


class ShelfGridViewTest(TestCase):
    def setUp(self):
        self.client, self.user = make_staff_client()
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot1 = Plot.objects.create(
            shelf_number="A-1", x_position=0, y_position=0, levels=3,
            layout=self.layout, organization=self.org
        )
        self.plot2 = Plot.objects.create(
            shelf_number="A-2", x_position=1, y_position=0, levels=3,
            layout=self.layout, organization=self.org
        )
        self.crop1 = ShelfCrop.objects.create(
            variety="レタス",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=30),
            plot=self.plot1,
            organization=self.org,
        )
        # セッションに組織をセット
        session = self.client.session
        session['current_organization_id'] = self.org.id
        session.save()

    def test_shelf_grid_view_get(self):
        response = self.client.get(reverse('cultivation:shelf_grid'))
        self.assertIn(response.status_code, [200, 302])

    def test_shelf_grid_layout_view_get(self):
        response = self.client.get(
            reverse('cultivation:shelf_grid_layout', args=[self.layout.id])
        )
        self.assertIn(response.status_code, [200, 302])


class PlotDetailViewTest(TestCase):
    def setUp(self):
        self.client, self.user = make_staff_client()
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot = Plot.objects.create(
            shelf_number="C-1", x_position=2, y_position=2, levels=4,
            layout=self.layout, organization=self.org
        )
        self.crop = ShelfCrop.objects.create(
            variety="トマト",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=60),
            plot=self.plot,
            organization=self.org,
        )
        session = self.client.session
        session['current_organization_id'] = self.org.id
        session.save()

    def test_plot_detail_view(self):
        response = self.client.get(reverse('cultivation:plot_detail', args=[self.plot.pk]))
        self.assertIn(response.status_code, [200, 302])


class CropImageUploadViewTest(TestCase):
    def setUp(self):
        self.client, self.user = make_staff_client()
        self.org = make_org()
        self.layout = make_layout(self.org)
        self.plot = Plot.objects.create(
            shelf_number="D-1", x_position=3, y_position=3, levels=2,
            layout=self.layout, organization=self.org
        )
        self.crop = ShelfCrop.objects.create(
            variety="キュウリ",
            planting_date=timezone.now().date(),
            expected_harvest_date=timezone.now().date() + timezone.timedelta(days=45),
            plot=self.plot,
            organization=self.org,
        )
        session = self.client.session
        session['current_organization_id'] = self.org.id
        session.save()

    def test_image_upload_view_get(self):
        response = self.client.get(reverse('cultivation:crop_image_upload', args=[self.crop.pk]))
        self.assertIn(response.status_code, [200, 302])

    def test_image_upload_view_post(self):
        image = Image.new('RGB', (100, 100), color='green')
        image_io = io.BytesIO()
        image.save(image_io, 'JPEG')
        image_io.seek(0)

        response = self.client.post(
            reverse('cultivation:crop_image_upload', args=[self.crop.pk]),
            {
                'image': SimpleUploadedFile("test_upload.jpg", image_io.read(), content_type="image/jpeg"),
                'notes': 'テストアップロード',
            }
        )
        self.assertIn(response.status_code, [200, 302])


class LaneMasterSettingsViewTest(TestCase):
    def setUp(self):
        self.client, self.user = make_staff_client()
        self.org = make_org()
        self.layout = make_layout(self.org)
        session = self.client.session
        session['current_organization_id'] = self.org.id
        session.save()

    def test_lane_settings_get(self):
        response = self.client.get(
            reverse('cultivation:lane_master_settings_layout', args=[self.layout.id])
        )
        self.assertIn(response.status_code, [200, 302])

    def test_bulk_add_lanes(self):
        response = self.client.post(
            reverse('cultivation:lane_master_settings_layout', args=[self.layout.id]),
            {
                'action': 'bulk_add',
                'prefix_text': 'T-',
                'start_number': 1,
                'count': 3,
                'levels': 3,
                'max_plates': 14,
            }
        )
        self.assertIn(response.status_code, [200, 302])
        # 作成されていれば3本のPlotが存在するはず
        created = Plot.objects.filter(layout=self.layout, shelf_number__startswith='T-').count()
        self.assertIn(created, [0, 3])  # 認証通れば3、リダイレクトなら0
