# シフト管理システム機能拡張設計書

## 1. 休み・通院申請機能

### 概要
従業員が休み（有給、病欠等）や通院の申請を行い、管理者が承認・却下できる機能

### 機能要件

#### 1.1 申請機能（従業員側）
- **申請種別選択**
  - 有給休暇
  - 病気休暇
  - 通院
  - その他休暇
- **申請内容入力**
  - 申請日時（範囲選択可能）
  - 理由（任意入力）
  - 緊急度設定
- **申請履歴確認**
  - 申請状況（待機中/承認済み/却下）
  - 申請理由

#### 1.2 承認機能（管理者側）
- **申請一覧表示**
  - 未処理申請の優先表示
  - フィルタリング機能（申請種別、日付等）
- **承認・却下処理**
  - ワンクリック承認
  - 却下理由入力
- **通知機能**
  - 申請者への結果通知
  - 他管理者への情報共有

### データベース設計
```sql
-- 申請テーブル
CREATE TABLE leave_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    request_type VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### UI設計
- **申請フォーム**: モーダルダイアログ
- **申請一覧**: カード形式での表示
- **カレンダー統合**: 申請済み日程の視覚的表示

---

## 2. 管理者による自由割り振り機能

### 概要
管理者が従業員のシフトを直接作成・編集し、従業員に打診できる機能

### 機能要件

#### 2.1 シフト作成機能
- **ドラッグ&ドロップ操作**
  - カレンダー上での直感的操作
  - 時間帯の調整
- **従業員選択**
  - スキル・経験による絞り込み
  - 稼働状況の確認
- **一括割り当て**
  - パターン適用
  - 複数日程の同時設定

#### 2.2 打診機能
- **打診送信**
  - 個別通知
  - 期限設定
- **回答管理**
  - 承諾・拒否の管理
  - 代替案の提示

#### 2.3 制約チェック
- **勤務時間制限**
  - 労働基準法準拠
  - 個人設定の考慮
- **スキルマッチング**
  - 必要スキルの確認
  - 経験レベルの適合性

### データベース設計
```sql
-- シフト打診テーブル
CREATE TABLE shift_proposals (
    id SERIAL PRIMARY KEY,
    proposed_by INTEGER REFERENCES users(id),
    proposed_to INTEGER REFERENCES users(id),
    shift_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    position VARCHAR(100),
    message TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    response_deadline TIMESTAMP,
    responded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3. 人同士のアラート・相性設定機能

### 概要
従業員間の相性や希望を設定し、シフト作成時にアラートを表示する機能

### 機能要件

#### 3.1 相性設定
- **相性レベル設定**
  - 良好（推奨組み合わせ）
  - 普通（制限なし）
  - 注意（要配慮）
  - 避ける（非推奨）
- **理由記録**
  - 設定理由の入力
  - 管理者のみ閲覧可能

#### 3.2 アラート機能
- **シフト作成時警告**
  - 非推奨組み合わせの警告
  - 推奨組み合わせの提案
- **レポート機能**
  - 相性統計の表示
  - 改善提案

### データベース設計
```sql
-- 相性設定テーブル
CREATE TABLE compatibility_settings (
    id SERIAL PRIMARY KEY,
    user1_id INTEGER REFERENCES users(id),
    user2_id INTEGER REFERENCES users(id),
    compatibility_level INTEGER CHECK (compatibility_level BETWEEN 1 AND 4),
    reason TEXT,
    set_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user1_id, user2_id)
);
```

---

## 4. 祝日自動反映機能

### 概要
国民の祝日を自動で取得し、シフト管理システムに反映する機能

### 機能要件

#### 4.1 祝日データ取得
- **外部API連携**
  - 内閣府の祝日API使用
  - 年間データの一括取得
- **手動追加**
  - 会社独自の休日設定
  - 地域固有の休日

#### 4.2 シフトへの反映
- **自動ブロック**
  - 祝日のシフト作成制限
  - 既存シフトの警告表示
- **特別設定**
  - 祝日勤務の設定
  - 割増料金の適用

### 実装方法
```python
# 祝日取得の例
import requests
from datetime import datetime

def fetch_holidays(year):
    url = f"https://holidays-jp.github.io/api/v1/{year}/date.json"
    response = requests.get(url)
    return response.json()
```

---

## 5. カレンダー設定・休み設定機能

### 概要
組織全体や個人のカレンダー設定を管理する機能

### 機能要件

#### 5.1 組織カレンダー設定
- **営業日設定**
  - 定休日の設定
  - 営業時間の設定
- **季節休業**
  - 夏季休業、年末年始等
  - 期間指定での休業設定

#### 5.2 個人カレンダー設定
- **勤務可能時間**
  - 曜日別の設定
  - 時間帯の指定
- **NG日設定**
  - 個人的な予定
  - 継続的な制約

---

## 6. 一括登録時のカレンダー選択機能

### 概要
複数のシフトを一括で登録する際、カレンダー上で視覚的に選択できる機能

### 機能要件

#### 6.1 視覚的選択
- **ドラッグ選択**
  - 期間の範囲選択
  - 複数日の同時選択
- **パターン適用**
  - 週単位のパターン
  - 月単位のパターン

#### 6.2 一括設定
- **共通設定適用**
  - 時間帯の一括設定
  - 担当者の一括割り当て
- **例外処理**
  - 個別調整機能
  - 制約チェック

---

## 7. カレンダー上でのイベント登録機能

### 概要
シフト以外のイベント（会議、研修等）をカレンダー上で管理する機能

### 機能要件

#### 7.1 イベント作成
- **イベント種別**
  - 会議
  - 研修
  - イベント
  - メンテナンス
- **詳細設定**
  - 参加者選択
  - 場所・資料の指定
  - 繰り返し設定

#### 7.2 シフトとの連携
- **競合チェック**
  - シフトとイベントの重複確認
  - 自動調整提案
- **統合表示**
  - カレンダー上での一元表示
  - 色分け表示

### データベース設計
```sql
-- イベントテーブル
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_type VARCHAR(50) NOT NULL,
    start_datetime TIMESTAMP NOT NULL,
    end_datetime TIMESTAMP NOT NULL,
    location VARCHAR(200),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- イベント参加者テーブル
CREATE TABLE event_participants (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'invited',
    UNIQUE(event_id, user_id)
);
```

---

## 実装優先順位

1. **高優先度**
   - 休み・通院申請機能
   - 管理者による自由割り振り機能

2. **中優先度**
   - 祝日自動反映機能
   - カレンダー設定・休み設定機能

3. **低優先度**
   - 人同士のアラート・相性設定機能
   - 一括登録時のカレンダー選択機能
   - カレンダー上でのイベント登録機能

## 技術的考慮事項

### フロントエンド
- **UIライブラリ**: 既存のReact/Vue.js等を活用
- **カレンダーコンポーネント**: FullCalendar等の導入検討
- **通知システム**: WebSocket或いはServer-Sent Events

### バックエンド
- **API設計**: RESTful設計の維持
- **権限管理**: 既存の権限システムとの統合
- **データベース**: 既存スキーマとの整合性保持

### セキュリティ
- **認証・認可**: 機能レベルでの権限制御
- **データ保護**: 個人情報の適切な管理
- **監査ログ**: 管理者操作の記録

## まとめ

この設計書に基づいて段階的な実装を行うことで、ユーザーの要求を満たすシフト管理システムの構築が可能です。各機能は独立性を保ちながらも相互に連携し、より使いやすく効率的なシステムを実現します。