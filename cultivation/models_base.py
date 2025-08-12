"""
Cultivation アプリケーションのベースモデル
"""
from django.db import models
from django.contrib.auth.models import User
from .constants import Limits

class TimestampedModel(models.Model):
    """タイムスタンプ付きベースモデル"""
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    
    class Meta:
        abstract = True

class NamedModel(models.Model):
    """名前付きベースモデル"""
    name = models.CharField("名前", max_length=Limits.NAME_MAX_LENGTH)
    
    class Meta:
        abstract = True
    
    def __str__(self):
        return self.name

class UserTrackingModel(models.Model):
    """ユーザー追跡ベースモデル"""
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="%(class)s_created",
        verbose_name="作成者"
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="%(class)s_updated",
        verbose_name="更新者"
    )
    
    class Meta:
        abstract = True

class CultivationBaseModel(TimestampedModel, NamedModel, UserTrackingModel):
    """栽培アプリケーションの共通ベースモデル"""
    description = models.TextField(
        "説明", 
        max_length=Limits.DESCRIPTION_MAX_LENGTH, 
        blank=True
    )
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    def get_absolute_url(self):
        """詳細ページのURLを取得"""
        from django.urls import reverse
        return reverse(
            f'cultivation:{self._meta.model_name}_detail',
            kwargs={'pk': self.pk}
        )
    
    def get_edit_url(self):
        """編集ページのURLを取得"""
        from django.urls import reverse
        return reverse(
            f'cultivation:{self._meta.model_name}_edit',
            kwargs={'pk': self.pk}
        )
    
    def get_delete_url(self):
        """削除ページのURLを取得"""
        from django.urls import reverse
        return reverse(
            f'cultivation:{self._meta.model_name}_delete',
            kwargs={'pk': self.pk}
        )