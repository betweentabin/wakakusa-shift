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

// ステータス→色マップ（viewのstatus名に合わせる）
const STATUS_COLOR = {
    empty:        0xeeeeee,
    growing:      0xa5d6a7,   // 栽培中（緑）
    harvest_ready:0xffcc80,   // 収穫可能（オレンジ）
    overdue:      0xef9a9a,   // 遅延（赤）
    sowing:       0xd0d8dc,
    pre_planted:  0xfff59d,
    planted:      0xa5d6a7,
    harvested:    0xbdbdbd,
};

// シンプルな3D初期化
function initSimple3D() {
    console.log('Initializing simple 3D...');

    const container = document.getElementById('three-d-container-scene');
    if (!container) { console.error('3D container not found'); return; }

    if (typeof THREE === 'undefined') {
        container.innerHTML = '<div class="alert alert-danger">Three.jsが読み込まれていません</div>';
        return;
    }

    try {
        const existingCanvas = container.querySelector('canvas');
        if (existingCanvas) existingCanvas.remove();

        const plots = (window.floorPlanData && window.floorPlanData.plots) || [];
        console.log('3D init — plots count:', plots.length);

        if (plots.length === 0) {
            container.innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted">'
                + '<div class="text-center"><i class="fas fa-cube fa-3x mb-3 d-block"></i>'
                + '<p>この画面に表示するレーンデータがありません。<br>2D表示でデータを確認してください。</p></div></div>';
            return;
        }

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xd0e8f5);
        window.currentThreeJSScene = scene;

        const w = container.offsetWidth  || 800;
        const h = container.offsetHeight || 500;
        const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 500);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(w, h);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        // 照明
        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const sun = new THREE.DirectionalLight(0xffffff, 0.9);
        sun.position.set(12, 20, 8);
        sun.castShadow = true;
        scene.add(sun);

        // 床
        const floorGeo = new THREE.PlaneGeometry(80, 80);
        const floorMat = new THREE.MeshLambertMaterial({ color: 0xd0cfc8 });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        scene.add(floor);

        createShelvesFromData(scene, plots);

        // カメラをデータ中心に配置
        camera.position.set(0, 10, 16);
        camera.lookAt(0, 2, 0);

        let controls = null;
        if (typeof THREE.OrbitControls !== 'undefined') {
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.target.set(0, 2, 0);
        }

        function animate() {
            requestAnimationFrame(animate);
            if (controls) controls.update();
            renderer.render(scene, camera);
        }
        animate();

        console.log('Simple 3D initialized successfully');

    } catch (error) {
        console.error('Error initializing 3D:', error);
        container.innerHTML = '<div class="alert alert-danger">3D初期化エラー: ' + error.message + '</div>';
    }
}

// ラック定数
const LEVEL_H  = 0.50;  // 段の高さ
const SHELF_T  = 0.05;  // 棚板厚み
const RACK_W   = 1.6;   // 棚幅
const RACK_D   = 0.7;   // 棚奥行
const RACK_GAP = 3.5;   // 棚間隔

// 実際のデータから棚を作成
function createShelvesFromData(scene, plots) {
    console.log(`Creating ${plots.length} shelves from data`);

    // 中心を求めて全体をセンタリング
    let cx = 0, cz = 0;
    plots.forEach((p, i) => {
        cx += (p.threejs_x !== undefined ? p.threejs_x : (i % 5) * RACK_GAP);
        cz += (p.threejs_z !== undefined ? p.threejs_z : Math.floor(i / 5) * RACK_GAP);
    });
    cx /= plots.length; cz /= plots.length;

    plots.forEach((plotData, index) => {
        let x, z;
        if (plotData.threejs_x !== undefined && plotData.threejs_z !== undefined
            && !(plotData.threejs_x === 0 && plotData.threejs_z === 0 && index > 0)) {
            x = plotData.threejs_x - cx;
            z = plotData.threejs_z - cz;
        } else {
            x = (index % 5) * RACK_GAP - (Math.min(plots.length, 5) - 1) * RACK_GAP / 2;
            z = Math.floor(index / 5) * RACK_GAP;
        }

        const shelfGroup = new THREE.Group();
        shelfGroup.position.set(x, 0, z);
        shelfGroup.userData = { plotId: plotData.id };

        const levels = plotData.level_details || [];
        const levelCount = Math.max(levels.length, 2);

        // 支柱（4本 / 鉄パイプ色）
        const poleH = levelCount * LEVEL_H + 0.6;
        const poleMat = new THREE.MeshLambertMaterial({ color: 0x546e7a });
        [[-RACK_W/2, -RACK_D/2], [RACK_W/2, -RACK_D/2],
         [-RACK_W/2,  RACK_D/2], [RACK_W/2,  RACK_D/2]].forEach(([px, pz]) => {
            const pole = new THREE.Mesh(
                new THREE.BoxGeometry(0.06, poleH, 0.06), poleMat);
            pole.position.set(px, poleH / 2, pz);
            pole.castShadow = true;
            shelfGroup.add(pole);
        });

        // 各段
        for (let i = 0; i < levelCount; i++) {
            const levelData = levels[i] || { level: i + 1, status: 'empty', crop_name: '空き' };
            const boardY = 0.3 + i * LEVEL_H;

            // 棚板
            const slotColor = STATUS_COLOR[levelData.status] || STATUS_COLOR.empty;
            const board = new THREE.Mesh(
                new THREE.BoxGeometry(RACK_W, SHELF_T, RACK_D),
                new THREE.MeshLambertMaterial({ color: slotColor })
            );
            board.position.set(0, boardY, 0);
            board.receiveShadow = true;
            shelfGroup.add(board);

            // 作物
            if (levelData.status !== 'empty' && levelData.crop_name && levelData.crop_name !== '空き') {
                addCropObjects(shelfGroup, levelData.status, boardY + SHELF_T);
            }
        }

        // ビルボードラベル
        const topY = 0.3 + levelCount * LEVEL_H + 0.25;
        const lbl = makeBillboard(plotData.shelf_number || ('棚' + (index + 1)));
        lbl.position.set(0, topY, 0);
        lbl.scale.set(1.4, 0.55, 1);
        shelfGroup.add(lbl);

        scene.add(shelfGroup);
    });
}

// 作物オブジェクトを棚板の上に配置
function addCropObjects(group, status, baseY) {
    const cfg = {
        growing:       { stems: 5, spread: 0.55, sh: 0.28, leafR: 0.10, lc: 0x43a047, sc: 0x2e7d32 },
        harvest_ready: { stems: 7, spread: 0.58, sh: 0.34, leafR: 0.13, lc: 0x2e7d32, sc: 0x1b5e20 },
        overdue:       { stems: 7, spread: 0.58, sh: 0.34, leafR: 0.13, lc: 0xe53935, sc: 0xb71c1c },
        sowing:        { stems: 3, spread: 0.40, sh: 0.14, leafR: 0.06, lc: 0xaed581, sc: 0x558b2f },
        pre_planted:   { stems: 4, spread: 0.50, sh: 0.20, leafR: 0.08, lc: 0x66bb6a, sc: 0x388e3c },
        planted:       { stems: 5, spread: 0.55, sh: 0.28, leafR: 0.10, lc: 0x43a047, sc: 0x2e7d32 },
    };
    const c = cfg[status] || cfg.growing;
    const leafMat = new THREE.MeshLambertMaterial({ color: c.lc });
    const stemMat = new THREE.MeshLambertMaterial({ color: c.sc });

    for (let i = 0; i < c.stems; i++) {
        const sx = (Math.random() - 0.5) * (RACK_W - 0.2) * c.spread / 0.6;
        const sz = (Math.random() - 0.5) * (RACK_D - 0.1) * c.spread / 0.7;
        // 茎
        const stem = new THREE.Mesh(
            new THREE.CylinderGeometry(0.015, 0.02, c.sh, 5),
            stemMat
        );
        stem.position.set(sx, baseY + c.sh / 2, sz);
        group.add(stem);
        // 葉（楕円球）
        const leaf = new THREE.Mesh(
            new THREE.SphereGeometry(c.leafR, 8, 6),
            leafMat
        );
        leaf.scale.set(1.4, 0.7, 1.4);
        leaf.position.set(sx, baseY + c.sh, sz);
        group.add(leaf);
    }
}

// ビルボードラベル（カメラに常に正対）
function makeBillboard(text) {
    const cv = document.createElement('canvas');
    cv.width = 192; cv.height = 64;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = 'rgba(30,30,30,0.82)';
    ctx.fillRect(2, 2, cv.width - 4, cv.height - 4);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, cv.width / 2, cv.height / 2);
    const tex = new THREE.CanvasTexture(cv);
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true });
    return new THREE.Sprite(mat);
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