// シンプルな3D表示切り替え機能
console.log('Loading simple 3D functionality...');

// 2D/3D切り替え機能
function switchView(viewType) {
    console.log('switchView called with:', viewType);
    
    const view2dBtn = document.getElementById('view-2d');
    const view3dBtn = document.getElementById('view-3d');
    const twoDContainer = document.getElementById('two-d-container');
    const threeDContainer = document.getElementById('three-d-container');
    
    console.log('Elements found:', {
        view2dBtn: !!view2dBtn,
        view3dBtn: !!view3dBtn,
        twoDContainer: !!twoDContainer,
        threeDContainer: !!threeDContainer
    });
    
    if (viewType === '2d') {
        // 2D表示
        if (view2dBtn) {
            view2dBtn.classList.remove('btn-outline-primary');
            view2dBtn.classList.add('btn-primary');
        }
        if (view3dBtn) {
            view3dBtn.classList.remove('btn-primary');
            view3dBtn.classList.add('btn-outline-primary');
        }
        
        if (twoDContainer) twoDContainer.style.display = 'block';
        if (threeDContainer) threeDContainer.style.display = 'none';
        
        console.log('Switched to 2D view');
    } else if (viewType === '3d') {
        // 3D表示
        if (view3dBtn) {
            view3dBtn.classList.remove('btn-outline-primary');
            view3dBtn.classList.add('btn-primary');
        }
        if (view2dBtn) {
            view2dBtn.classList.remove('btn-primary');
            view2dBtn.classList.add('btn-outline-primary');
        }
        
        if (twoDContainer) twoDContainer.style.display = 'none';
        if (threeDContainer) threeDContainer.style.display = 'block';
        
        console.log('Switched to 3D view');
        
        // 簡単な3D初期化
        initSimple3D();
    }
}

// シンプルな3D初期化
function initSimple3D() {
    console.log('Initializing simple 3D...');
    
    const container = document.getElementById('three-d-container-scene');
    if (!container) {
        console.error('3D container not found');
        return;
    }
    
    // Three.jsチェック
    if (typeof THREE === 'undefined') {
        console.error('Three.js not loaded');
        container.innerHTML = '<div class="alert alert-danger">Three.jsが読み込まれていません</div>';
        return;
    }
    
    try {
        // 既存のcanvasを削除
        const existingCanvas = container.querySelector('canvas');
        if (existingCanvas) {
            existingCanvas.remove();
        }
        
        // 基本的な3Dシーンを作成
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x87CEEB);
        
        // グローバル変数にシーンを保存（位置更新で使用）
        window.currentThreeJSScene = scene;
        
        const camera = new THREE.PerspectiveCamera(75, container.offsetWidth / container.offsetHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        
        renderer.setSize(container.offsetWidth, container.offsetHeight);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);
        
        // ライト設定
        const ambientLight = new THREE.AmbientLight(0x404040, 0.4);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 20, 10);
        directionalLight.castShadow = true;
        scene.add(directionalLight);
        
        // 実際の栽培データがある場合は棚を作成、ない場合はテストキューブ
        console.log('Floor plan data available:', !!window.floorPlanData);
        
        if (window.floorPlanData && window.floorPlanData.plots && window.floorPlanData.plots.length > 0) {
            console.log('Creating shelves from real data...');
            createShelvesFromData(scene);
            
            // カメラ位置を棚に合わせて調整
            camera.position.set(10, 8, 10);
            camera.lookAt(0, 0, 0);
        } else {
            console.log('Creating test cube...');
            // テスト用のキューブを追加
            const geometry = new THREE.BoxGeometry(1, 1, 1);
            const material = new THREE.MeshLambertMaterial({ color: 0x00ff00 });
            const cube = new THREE.Mesh(geometry, material);
            scene.add(cube);
            
            camera.position.z = 5;
        }
        
        // OrbitControls (利用可能な場合)
        let controls = null;
        if (typeof THREE.OrbitControls !== 'undefined') {
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
        }
        
        // アニメーションループ
        function animate() {
            requestAnimationFrame(animate);
            
            if (controls) {
                controls.update();
            }
            
            renderer.render(scene, camera);
        }
        animate();
        
        console.log('Simple 3D initialized successfully');
        
    } catch (error) {
        console.error('Error initializing 3D:', error);
        container.innerHTML = '<div class="alert alert-danger">3D初期化エラー: ' + error.message + '</div>';
    }
}

// 実際のデータから棚を作成
function createShelvesFromData(scene) {
    const plots = window.floorPlanData.plots;
    console.log(`Creating ${plots.length} shelves from data`);
    
    plots.forEach((plotData, index) => {
        // 棚の位置を計算 - threejs座標が利用可能ならそれを使用、なければSVG座標から変換
        let x, z;
        if (plotData.threejs_x !== undefined && plotData.threejs_z !== undefined) {
            // 保存されている3D座標を使用
            x = plotData.threejs_x;
            z = plotData.threejs_z;
            console.log(`Using saved 3D coordinates for plot ${plotData.id}: (${x.toFixed(2)}, 0, ${z.toFixed(2)})`);
        } else if (plotData.svg_x !== undefined && plotData.svg_y !== undefined) {
            // SVG座標を3D座標に変換
            x = (plotData.svg_x - 400) / 100; // スケール調整
            z = (plotData.svg_y - 300) / 100;
            console.log(`Converting SVG to 3D for plot ${plotData.id}: (${x.toFixed(2)}, 0, ${z.toFixed(2)})`);
        } else {
            // フォールバック: グリッド配置
            x = (index % 4) * 3 - 4.5;
            z = Math.floor(index / 4) * 3 - 3;
            console.log(`Using fallback grid position for plot ${plotData.id}: (${x.toFixed(2)}, 0, ${z.toFixed(2)})`);
        }
        
        // 棚グループを作成
        const shelfGroup = new THREE.Group();
        shelfGroup.position.set(x, 0, z);
        shelfGroup.userData = { plotId: plotData.id }; // プロットIDを保存
        
        // レベルデータを取得
        const levels = plotData.level_details || [];
        const levelCount = Math.max(levels.length, 3); // 最低3レベル
        
        // 棚の支柱を作成
        createShelfPosts(shelfGroup, levelCount);
        
        // 各レベルを作成
        for (let i = 0; i < levelCount; i++) {
            const levelData = levels[i] || { level: i + 1, status: 'empty', crop_name: '空き' };
            const shelfLevel = createShelfLevel(levelData, i + 1);
            shelfGroup.add(shelfLevel);
        }
        
        scene.add(shelfGroup);
    });
}

// 棚の支柱を作成
function createShelfPosts(shelfGroup, levelCount) {
    const postHeight = levelCount * 0.6 + 0.5;
    const postGeometry = new THREE.BoxGeometry(0.05, postHeight, 0.05);
    const postMaterial = new THREE.MeshLambertMaterial({ color: 0x8B4513 });
    
    const postPositions = [
        [-0.6, postHeight / 2, -0.3],
        [0.6, postHeight / 2, -0.3],
        [-0.6, postHeight / 2, 0.3],
        [0.6, postHeight / 2, 0.3]
    ];
    
    postPositions.forEach(pos => {
        const post = new THREE.Mesh(postGeometry, postMaterial);
        post.position.set(pos[0], pos[1], pos[2]);
        post.castShadow = true;
        shelfGroup.add(post);
    });
}

// 棚レベルを作成
function createShelfLevel(levelData, level) {
    const levelGroup = new THREE.Group();
    const y = level * 0.6;
    levelGroup.position.y = y;
    
    // 棚板
    const shelfGeometry = new THREE.BoxGeometry(1.2, 0.03, 0.6);
    let shelfColor = 0xDDDDDD; // デフォルト（空き）
    
    // ステータスに応じて色を変更
    if (levelData.status === 'growing') {
        shelfColor = 0x90EE90; // ライトグリーン
    } else if (levelData.status === 'harvest_ready') {
        shelfColor = 0xFFD700; // ゴールド
    } else if (levelData.status === 'overdue') {
        shelfColor = 0xFF6B6B; // ライトレッド
    }
    
    const shelfMaterial = new THREE.MeshLambertMaterial({ color: shelfColor });
    const shelf = new THREE.Mesh(shelfGeometry, shelfMaterial);
    shelf.castShadow = true;
    shelf.receiveShadow = true;
    levelGroup.add(shelf);
    
    // 作物がある場合は作物オブジェクトを追加
    if (levelData.status !== 'empty' && levelData.crop_name && levelData.crop_name !== '空き') {
        console.log(`Adding crop: ${levelData.crop_name} (status: ${levelData.status})`);
        
        // 作物の色を状態に応じて設定
        let cropColor = 0x228B22; // フォレストグリーン
        if (levelData.status === 'harvest_ready') {
            cropColor = 0xFFD700; // ゴールド
        } else if (levelData.status === 'overdue') {
            cropColor = 0xFF4500; // 赤橙
        }
        
        // 複数の小さな作物オブジェクトを配置
        for (let i = 0; i < 8; i++) {
            const cropGeometry = new THREE.SphereGeometry(0.04, 8, 6);
            const cropMaterial = new THREE.MeshLambertMaterial({ color: cropColor });
            const crop = new THREE.Mesh(cropGeometry, cropMaterial);
            
            crop.position.set(
                (Math.random() - 0.5) * 1.0,
                0.05,
                (Math.random() - 0.5) * 0.4
            );
            crop.castShadow = true;
            levelGroup.add(crop);
        }
        
        // 作物名ラベル（テキスト）
        if (levelData.crop_name.length <= 6) { // 短い名前のみ表示
            createTextLabel(levelGroup, levelData.crop_name, 0, 0.15, 0);
        }
    }
    
    return levelGroup;
}

// テキストラベルを作成
function createTextLabel(parent, text, x, y, z) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 128;
    canvas.height = 32;
    
    context.fillStyle = 'rgba(0, 0, 0, 0.8)';
    context.fillRect(0, 0, canvas.width, canvas.height);
    
    context.fillStyle = 'white';
    context.font = '16px Arial';
    context.textAlign = 'center';
    context.fillText(text, canvas.width / 2, canvas.height / 2 + 6);
    
    const texture = new THREE.CanvasTexture(canvas);
    const labelMaterial = new THREE.MeshBasicMaterial({ 
        map: texture, 
        transparent: true,
        side: THREE.DoubleSide
    });
    const labelGeometry = new THREE.PlaneGeometry(0.6, 0.15);
    const label = new THREE.Mesh(labelGeometry, labelMaterial);
    label.position.set(x, y, z);
    parent.add(label);
}

// DOM読み込み完了時の処理
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded - setting up button events');
    
    // ボタンイベント設定
    const view2dBtn = document.getElementById('view-2d');
    const view3dBtn = document.getElementById('view-3d');
    
    if (view2dBtn) {
        view2dBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('2D button clicked');
            switchView('2d');
        });
        console.log('2D button event listener added');
    } else {
        console.error('2D button not found');
    }
    
    if (view3dBtn) {
        view3dBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('3D button clicked');
            switchView('3d');
        });
        console.log('3D button event listener added');
    } else {
        console.error('3D button not found');
    }
    
    // 初期状態を2Dに
    switchView('2d');
    
    // ドラッグ機能を設定（少し遅らせて実行）
    setTimeout(() => {
        setupDraggablePlots();
        
        // 保存ボタンのイベントリスナー
        const saveBtn = document.getElementById('save-positions-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', saveAllPositions);
            console.log('Save button event listener added');
        }
    }, 1000);
    
    // 2D表示に切り替わった時もドラッグ機能を再設定
    const originalSwitchView = window.switchView;
    window.switchView = function(viewType) {
        console.log('View switching to:', viewType);
        originalSwitchView(viewType);
        if (viewType === '2d') {
            console.log('Setting up drag for 2D view...');
            setTimeout(() => {
                setupDraggablePlots();
            }, 500);
        }
    };
    
    console.log('Button setup complete');
});

// グローバルに公開
window.switchView = switchView;

// 2D SVG ドラッグ機能
let movedPlots = new Set();
let hasUnsavedChanges = false;

// ドラッグ可能なプロットを設定
function setupDraggablePlots() {
    console.log('=== Setting up draggable plots ===');
    
    // SVGコンテナを確認
    const svg = document.getElementById('floor-plan-svg');
    console.log('SVG container found:', !!svg);
    
    if (!svg) {
        console.error('SVG container not found');
        return;
    }
    
    // シンプルな単一セレクタで要素を探す
    const plots = svg.querySelectorAll('g.plot-group');
    console.log(`Plot groups found: ${plots.length}`);
    
    if (plots.length === 0) {
        console.error('No plot groups found');
        
        // デバッグ: SVG内の全要素を確認
        const allSvgElements = svg.querySelectorAll('*');
        console.log(`Total SVG elements: ${allSvgElements.length}`);
        
        // gタグを検索
        const allGElements = svg.querySelectorAll('g');
        console.log(`Total g elements: ${allGElements.length}`);
        allGElements.forEach((g, i) => {
            console.log(`g[${i}]:`, {
                className: g.className.baseVal || g.className,
                classList: g.classList?.toString(),
                attributes: Array.from(g.attributes).map(attr => `${attr.name}="${attr.value}"`).join(' ')
            });
        });
        return;
    }
    
    console.log('Setting up drag for', plots.length, 'plot elements');
    
    plots.forEach((plot, index) => {
        console.log(`Setting up plot ${index + 1}:`, {
            plotId: plot.dataset.plotId,
            className: plot.className.baseVal || plot.className
        });
        
        let isDragging = false;
        let startX, startY;
        
        // カーソルを設定
        plot.style.cursor = 'move';
        
        // 基本的なクリックテスト
        plot.addEventListener('click', function(e) {
            console.log(`✓ Plot ${plot.dataset.plotId} clicked`);
            e.stopPropagation();
        });
        
        // マウスダウンイベント
        plot.addEventListener('mousedown', function(e) {
            console.log(`✓ Mousedown on plot ${plot.dataset.plotId}`);
            
            if (e.button === 0) { // 左クリックのみ
                isDragging = true;
                startX = e.clientX;
                startY = e.clientY;
                
                plot.classList.add('plot-dragging');
                console.log(`✓ Drag started for plot ${plot.dataset.plotId}`);
                
                e.preventDefault();
                e.stopPropagation();
            }
        });
        
        // マウス移動（documentに付ける）
        document.addEventListener('mousemove', function(e) {
            if (isDragging) {
                const deltaX = e.clientX - startX;
                const deltaY = e.clientY - startY;
                plot.setAttribute('transform', `translate(${deltaX}, ${deltaY})`);
            }
        });
        
        // マウスアップ（documentに付ける）
        document.addEventListener('mouseup', function(e) {
            if (isDragging) {
                console.log(`✓ Drag ended for plot ${plot.dataset.plotId}`);
                isDragging = false;
                plot.classList.remove('plot-dragging');
                
                const deltaX = e.clientX - startX;
                const deltaY = e.clientY - startY;
                
                // 実際のSVG座標を更新
                updatePlotSVGPosition(plot, deltaX, deltaY);
                
                // 変更されたプロットを記録
                const plotId = plot.dataset.plotId;
                if (plotId) {
                    movedPlots.add(plotId);
                    hasUnsavedChanges = true;
                    showSaveButton();
                }
            }
        });
    });
    console.log('Drag setup complete');
}

// プロットのSVG座標を実際に更新
function updatePlotSVGPosition(plotElement, deltaX, deltaY) {
    console.log('Updating SVG position with delta:', deltaX, deltaY);
    
    // プロット内のすべての要素の位置を更新
    const elementsToUpdate = plotElement.querySelectorAll('rect, text, circle');
    
    elementsToUpdate.forEach(element => {
        if (element.hasAttribute('x')) {
            const currentX = parseFloat(element.getAttribute('x'));
            element.setAttribute('x', currentX + deltaX);
        }
        if (element.hasAttribute('y')) {
            const currentY = parseFloat(element.getAttribute('y'));
            element.setAttribute('y', currentY + deltaY);
        }
        if (element.hasAttribute('cx')) {
            const currentCX = parseFloat(element.getAttribute('cx'));
            element.setAttribute('cx', currentCX + deltaX);
        }
        if (element.hasAttribute('cy')) {
            const currentCY = parseFloat(element.getAttribute('cy'));
            element.setAttribute('cy', currentCY + deltaY);
        }
    });
    
    // transformをリセット（SVG座標を直接更新したため）
    if (plotElement.tagName === 'g' || plotElement.tagName === 'G') {
        plotElement.removeAttribute('transform');
    } else {
        plotElement.style.transform = '';
    }
}

// 保存ボタンを表示
function showSaveButton() {
    const saveBtn = document.getElementById('save-positions-btn');
    if (saveBtn) {
        saveBtn.style.display = 'block';
        saveBtn.classList.add('pulse-animation');
        console.log('Save button shown');
    }
}

// 全ての位置を保存
function saveAllPositions() {
    if (movedPlots.size === 0) {
        console.log('No plots to save');
        return;
    }
    
    console.log('Saving positions for plots:', Array.from(movedPlots));
    
    const saveBtn = document.getElementById('save-positions-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>保存中...';
    }
    
    const savePromises = [];
    
    movedPlots.forEach(plotId => {
        const plotGroup = document.querySelector(`[data-plot-id="${plotId}"]`);
        
        if (plotGroup) {
            // 背景矩形から新しい位置を取得
            const plotBackground = plotGroup.querySelector('.plot-background, rect');
            if (plotBackground) {
                const newX = parseFloat(plotBackground.getAttribute('x'));
                const newY = parseFloat(plotBackground.getAttribute('y'));
                console.log(`Position for plot ${plotId}: x=${newX}, y=${newY}`);
                
                const promise = savePlotPosition(plotId, newX, newY, plotGroup);
                savePromises.push(promise);
            }
        }
    });
    
    Promise.allSettled(savePromises)
        .then(results => {
            console.log('Save results:', results);
            
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                saveBtn.style.display = 'none';
                saveBtn.classList.remove('pulse-animation');
            }
            
            const successful = results.filter(r => r.status === 'fulfilled' && r.value && r.value.success).length;
            const failed = results.length - successful;
            
            if (failed === 0) {
                console.log(`全${successful}個の棚位置を保存しました`);
                movedPlots.clear();
                hasUnsavedChanges = false;
            } else {
                console.error(`${failed}個の棚位置の保存に失敗しました`);
            }
        })
        .catch(error => {
            console.error('Save operation failed:', error);
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
            }
        });
}

// 単一の棚位置を保存
function savePlotPosition(plotId, newX, newY, plotGroup) {
    console.log(`Saving position for plot ${plotId}: x=${newX}, y=${newY}`);
    
    // CSRF トークンを取得
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    
    const url = `/cultivation/plots/${plotId}/update-position/`;
    
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            svg_x: newX,
            svg_y: newY
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`棚${plotId}の位置を保存しました`);
            console.log(`3D座標も更新されました: x=${data.threejs_x}, y=${data.threejs_y}, z=${data.threejs_z}`);
            
            // 成功の視覚的フィードバック
            if (plotGroup) {
                plotGroup.style.filter = 'drop-shadow(0 0 5px #28a745)';
                setTimeout(() => {
                    plotGroup.style.filter = '';
                }, 1000);
            }
            
            // 3Dビューが表示されている場合は、3Dの棚位置を即座に更新
            update3DShelfPosition(plotId, data.threejs_x, data.threejs_y, data.threejs_z);
            
            return { success: true, plotId };
        } else {
            console.error(`棚${plotId}の位置保存に失敗:`, data.error);
            return { success: false, plotId, error: data.error };
        }
    })
    .catch(error => {
        console.error(`棚${plotId}の位置保存でエラーが発生:`, error);
        return { success: false, plotId, error: error.message };
    });
}

// 3Dビューの棚位置を更新
function update3DShelfPosition(plotId, threejsX, threejsY, threejsZ) {
    // 3Dビューが表示されているかチェック
    const threeDContainer = document.getElementById('three-d-container');
    if (!threeDContainer || threeDContainer.style.display === 'none') {
        console.log('3Dビューが非表示のため、3D位置更新をスキップ');
        return;
    }
    
    // Three.jsシーンが存在するかチェック
    const sceneContainer = document.getElementById('three-d-container-scene');
    if (!sceneContainer || !window.currentThreeJSScene) {
        console.log('3Dシーンが存在しないため、3D位置更新をスキップ');
        return;
    }
    
    console.log(`3Dの棚位置を更新中: Plot ${plotId} → (${threejsX}, ${threejsY}, ${threejsZ})`);
    
    // シーン内の対象プロットを検索
    const scene = window.currentThreeJSScene;
    scene.traverse(function(child) {
        if (child.userData && child.userData.plotId == plotId) {
            console.log(`プロット${plotId}の3D位置を更新: (${threejsX}, ${threejsY}, ${threejsZ})`);
            child.position.set(threejsX, threejsY, threejsZ);
            
            // 位置更新の視覚的フィードバック（一時的に棚を光らせる）
            if (child.children && child.children.length > 0) {
                child.children.forEach(shelf => {
                    if (shelf.material) {
                        const originalColor = shelf.material.color.clone();
                        shelf.material.color.setHex(0x00ff00); // 緑色に変更
                        setTimeout(() => {
                            shelf.material.color.copy(originalColor); // 元の色に戻す
                        }, 1000);
                    }
                });
            }
        }
    });
}