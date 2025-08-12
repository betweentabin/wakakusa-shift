"""
Cultivation アプリケーションのベースビュー
"""
from django.views.generic import (
    CreateView, UpdateView, DeleteView, DetailView, ListView
)
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from .constants import Messages

def is_admin_user(user):
    """管理者ユーザーかどうかを判定"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)

class CultivationPermissionMixin(UserPassesTestMixin):
    """栽培管理の権限チェックミックスイン"""
    
    def test_func(self):
        return is_admin_user(self.request.user)
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, Messages.PERMISSION_DENIED)
        return super().handle_no_permission()

class CultivationBaseView(CultivationPermissionMixin):
    """栽培管理のベースビュー"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_name'] = 'cultivation'
        return context

class CultivationCreateView(CultivationBaseView, CreateView):
    """栽培管理の作成ビュー"""
    template_name_suffix = '_form'
    
    def get_success_message(self):
        return Messages.CREATE_SUCCESS.format(
            model=self.model._meta.verbose_name
        )
    
    def form_valid(self, form):
        # 作成者を設定
        if hasattr(form.instance, 'created_by'):
            form.instance.created_by = self.request.user
        
        messages.success(self.request, self.get_success_message())
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        context['title'] = f"{self.model._meta.verbose_name}の作成"
        return context

class CultivationUpdateView(CultivationBaseView, UpdateView):
    """栽培管理の更新ビュー"""
    template_name_suffix = '_form'
    
    def get_success_message(self):
        return Messages.UPDATE_SUCCESS.format(
            model=self.model._meta.verbose_name
        )
    
    def form_valid(self, form):
        # 更新者を設定
        if hasattr(form.instance, 'updated_by'):
            form.instance.updated_by = self.request.user
        
        messages.success(self.request, self.get_success_message())
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'update'
        context['title'] = f"{self.model._meta.verbose_name}の編集"
        return context

class CultivationDeleteView(CultivationBaseView, DeleteView):
    """栽培管理の削除ビュー"""
    template_name_suffix = '_confirm_delete'
    
    def get_success_message(self):
        return Messages.DELETE_SUCCESS.format(
            model=self.model._meta.verbose_name
        )
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, self.get_success_message())
        return super().delete(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"{self.model._meta.verbose_name}の削除"
        return context

class CultivationDetailView(CultivationBaseView, DetailView):
    """栽培管理の詳細ビュー"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"{self.model._meta.verbose_name}の詳細"
        return context

class CultivationListView(CultivationBaseView, ListView):
    """栽培管理の一覧ビュー"""
    paginate_by = 20
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"{self.model._meta.verbose_name_plural}一覧"
        return context

class CultivationAjaxMixin:
    """Ajax対応ミックスイン"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.is_ajax():
            return super().dispatch(request, *args, **kwargs)
        
        try:
            response = super().dispatch(request, *args, **kwargs)
            
            # Ajax成功レスポンス
            if hasattr(response, 'status_code') and response.status_code == 302:
                return JsonResponse({
                    'success': True,
                    'redirect_url': response.url,
                    'message': self.get_success_message() if hasattr(self, 'get_success_message') else 'Success'
                })
            
            return response
            
        except Exception as e:
            # Ajax エラーレスポンス
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

class CultivationFormView(CultivationAjaxMixin, CultivationCreateView):
    """Ajax対応フォームビュー"""
    
    def form_invalid(self, form):
        if self.request.is_ajax():
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

class CultivationModelViewSet:
    """モデル用のビューセット生成クラス"""
    
    def __init__(self, model, form_class=None, queryset=None):
        self.model = model
        self.form_class = form_class
        self.queryset = queryset or model.objects.all()
    
    def get_list_view(self):
        """一覧ビューを生成"""
        class ListView(CultivationListView):
            model = self.model
            queryset = self.queryset
        
        return ListView.as_view()
    
    def get_detail_view(self):
        """詳細ビューを生成"""
        class DetailView(CultivationDetailView):
            model = self.model
            queryset = self.queryset
        
        return DetailView.as_view()
    
    def get_create_view(self):
        """作成ビューを生成"""
        class CreateView(CultivationCreateView):
            model = self.model
            form_class = self.form_class
        
        return CreateView.as_view()
    
    def get_update_view(self):
        """更新ビューを生成"""
        class UpdateView(CultivationUpdateView):
            model = self.model
            form_class = self.form_class
            queryset = self.queryset
        
        return UpdateView.as_view()
    
    def get_delete_view(self):
        """削除ビューを生成"""
        class DeleteView(CultivationDeleteView):
            model = self.model
            queryset = self.queryset
            success_url = reverse_lazy(f'cultivation:{self.model._meta.model_name}_list')
        
        return DeleteView.as_view()

class CultivationStatsView(CultivationBaseView):
    """統計情報ビュー"""
    
    def get_statistics(self):
        """統計情報を取得（サブクラスで実装）"""
        raise NotImplementedError("Subclass must implement get_statistics method")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statistics'] = self.get_statistics()
        return context

class CultivationBulkActionView(CultivationBaseView):
    """一括操作ビュー"""
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_ids')
        
        if not action or not selected_ids:
            messages.error(request, "操作とアイテムを選択してください。")
            return self.get(request, *args, **kwargs)
        
        try:
            result = self.perform_bulk_action(action, selected_ids)
            messages.success(request, f"{result}件の処理が完了しました。")
        except Exception as e:
            messages.error(request, f"エラーが発生しました: {str(e)}")
        
        return self.get(request, *args, **kwargs)
    
    def perform_bulk_action(self, action, selected_ids):
        """一括操作を実行（サブクラスで実装）"""
        raise NotImplementedError("Subclass must implement perform_bulk_action method")

# 関数ベースビュー用のデコレーター
def cultivation_permission_required(view_func):
    """栽培管理権限が必要なビュー用デコレーター"""
    @method_decorator(user_passes_test(is_admin_user, login_url='/login/'))
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper