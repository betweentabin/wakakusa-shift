# wakakusa-shift-1 と wakakusa-shift-2 統合計画

## 📋 概要
wakakusa-shift-1とwakakusa-shift-2の機能を統合し、両方の機能を使えるシステムを構築します。

## 🎯 統合方針
- wakakusa-shift-1をベースとして使用（Organizationモデルによるマルチテナント対応）
- wakakusa-shift-2の追加機能を移植
- 既存データの互換性を保持

## 📊 機能差分分析

### wakakusa-shift-1の独自機能
1. **Organization（組織）モデル**
   - マルチテナント対応
   - 組織単位でのデータ分離
   
2. **栽培管理システム（cultivation/）**
   - 作物管理機能
   - 3Dレイアウト表示

### wakakusa-shift-2の独自機能
1. **休暇・申請管理**
   - LeaveRequest（休み・通院申請）
   - 承認ワークフロー
   - カレンダーからの休暇申請
   
2. **シフト打診・相性管理**
   - ShiftProposal（シフト打診）
   - StaffCompatibility（スタッフ間相性設定）
   - 打診回答システム
   
3. **高度なシフト操作**
   - ドラッグ&ドロップでシフト編集
   - 一括承認機能
   - カレンダーから一括シフト作成
   - 承認待ちシフト管理
   
4. **カレンダー機能拡張**
   - Holiday（祝日・休日）
   - Event（イベント）
   - EventParticipant（イベント参加者）
   
5. **通知システム**
   - Notification（通知）
   - 各種イベントの通知機能
   - 一括既読機能
   
6. **スタッフ用機能**
   - スタッフ専用ビュー
   - スタッフによるシフト申請
   - 承認システム統合

## 🔧 統合手順

### Phase 1: データベースモデルの統合
1. wakakusa-shift-2の追加モデルを移植
   - LeaveRequest
   - ShiftProposal
   - StaffCompatibility
   - Holiday
   - Event, EventParticipant
   - Notification
   
2. 外部キー関係の調整
   - Organizationとの関連付け追加
   - 既存モデルとの整合性確保

### Phase 2: ビューとURLの統合
1. wakakusa-shift-2の追加ビューを移植
   - 休暇申請関連ビュー
   - シフト打診関連ビュー
   - イベント管理ビュー
   - 通知関連ビュー
   
2. URLパターンの統合
   - 名前空間の調整
   - パスの重複回避

### Phase 3: テンプレートとスタティックファイルの統合
1. テンプレートの移植
   - wakakusa-shift-2の追加テンプレート
   - base.htmlの統合
   
2. スタティックファイルの統合
   - CSS/JSファイルの移植
   - 競合の解決

### Phase 4: 権限とセキュリティの調整
1. 組織単位でのアクセス制御
   - 新機能への組織フィルタ追加
   - 権限チェックの実装
   
2. 承認ワークフローの調整
   - 組織内での承認フロー

### Phase 5: テストと動作確認
1. マイグレーションのテスト
2. 機能テスト
3. 統合テスト

## 📅 実装優先順位
1. **高優先度**
   - LeaveRequest（休暇申請）
   - Notification（通知）
   - Holiday（祝日）
   
2. **中優先度**
   - ShiftProposal（シフト打診）
   - Event/EventParticipant（イベント）
   
3. **低優先度**
   - StaffCompatibility（相性設定）

## ⚠️ 注意事項
- データベースのバックアップを必ず取得
- 段階的な移行を推奨
- 本番環境での作業は慎重に実施

## 🎯 期待される成果
- 両プロジェクトの長所を統合した高機能システム
- マルチテナント対応の休暇・シフト管理
- 栽培管理機能との連携可能性