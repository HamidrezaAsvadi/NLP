// Application State
let orders = [];
let uncertainItems = [];
let selectedItem = null;
let selectedOrderContext = null;
let eventSource = null;

// DOM Elements
const elements = {
    // Navigation Tabs
    tabReviewBtn: document.getElementById('tab-review-btn'),
    tabOrdersBtn: document.getElementById('tab-orders-btn'),
    tabConsoleBtn: document.getElementById('tab-console-btn'),
    
    // Sections
    secReview: document.getElementById('section-review'),
    secOrders: document.getElementById('section-orders'),
    secConsole: document.getElementById('section-console'),
    
    // Stats Header
    statTotalOrders: document.getElementById('stat-total-orders'),
    statReviewItems: document.getElementById('stat-review-items'),
    statAccuracy: document.getElementById('stat-accuracy'),
    problematicCountBadge: document.getElementById('problematic-count-badge'),
    
    // Sidebar RL weights
    rlUpdates: document.getElementById('rl-updates'),
    wExact: document.getElementById('w-exact'),
    vExact: document.getElementById('v-exact'),
    wFuzzy: document.getElementById('w-fuzzy'),
    vFuzzy: document.getElementById('v-fuzzy'),
    wTrigram: document.getElementById('w-trigram'),
    vTrigram: document.getElementById('v-trigram'),
    wBlocked: document.getElementById('w-blocked'),
    vBlocked: document.getElementById('v-blocked'),
    
    // Run Pipeline
    runPipelineBtn: document.getElementById('run-pipeline-btn'),
    
    // Problematic pane
    uncertainCount: document.getElementById('uncertain-items-count'),
    uncertainList: document.getElementById('uncertain-items-list'),
    
    // Detail Pane
    detailPanePlaceholder: document.getElementById('pane-placeholder'),
    detailPaneContent: document.getElementById('pane-details-content'),
    detailCustomerCode: document.getElementById('detail-customer-code'),
    detailOrderLabel: document.getElementById('detail-order-label'),
    detailConfBadge: document.getElementById('detail-conf-badge'),
    mediaPreviewBox: document.getElementById('media-preview-box'),
    
    // Comparison fields
    geminiCode: document.getElementById('gemini-code-val'),
    geminiDesc: document.getElementById('gemini-desc-val'),
    geminiPieces: document.getElementById('gemini-pieces-val'),
    matchCode: document.getElementById('match-code-val'),
    matchDesc: document.getElementById('match-desc-val'),
    matchUnit: document.getElementById('match-unit-val'),
    
    // Telemetry fields
    metricFuzzy: document.getElementById('metric-fuzzy'),
    metricTrigram: document.getElementById('metric-trigram'),
    metricMethod: document.getElementById('metric-method'),
    metricRL: document.getElementById('metric-rl'),
    
    // Feedback buttons
    btnFeedbackAccept: document.getElementById('btn-feedback-accept'),
    btnFeedbackReject: document.getElementById('btn-feedback-reject'),
    feedbackComment: document.getElementById('feedback-comment'),
    
    // Orders table
    ordersTableBody: document.getElementById('orders-table-body'),
    
    // Console logs
    consoleOutput: document.getElementById('console-output'),
    consoleStatus: document.getElementById('console-status-indicator'),
    clearConsoleBtn: document.getElementById('clear-console-btn'),
    
    // Modal
    modal: document.getElementById('order-detail-modal'),
    modalTitle: document.getElementById('modal-title'),
    modalBodyContent: document.getElementById('modal-body-content'),
    modalCloseBtn: document.getElementById('modal-close-btn')
};

// ═════════════════════════════════════════════════════════════════════════════
// Initialization & Tab Navigation
// ═════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    setupTabNavigation();
    setupEventListeners();
    
    // Initial fetch of data
    fetchOrders();
    fetchRLWeights();
});

function setupTabNavigation() {
    const tabs = [
        { btn: elements.tabReviewBtn, sec: elements.secReview },
        { btn: elements.tabOrdersBtn, sec: elements.secOrders },
        { btn: elements.tabConsoleBtn, sec: elements.secConsole }
    ];

    tabs.forEach(tab => {
        tab.btn.addEventListener('click', () => {
            tabs.forEach(t => {
                t.btn.classList.remove('active');
                t.sec.classList.remove('active');
            });
            tab.btn.classList.add('active');
            tab.sec.classList.add('active');
        });
    });
}

function setupEventListeners() {
    // Run pipeline click
    elements.runPipelineBtn.addEventListener('click', runPipeline);
    
    // Feedback actions
    elements.btnFeedbackAccept.addEventListener('click', () => submitFeedback(true));
    elements.btnFeedbackReject.addEventListener('click', () => submitFeedback(false));
    
    // Console clear
    elements.clearConsoleBtn.addEventListener('click', () => {
        elements.consoleOutput.innerHTML = '<div class="console-line system-msg">Console cleared.</div>';
    });
    
    // Modal close
    elements.modalCloseBtn.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
        if (e.target === elements.modal) closeModal();
    });
}

// ═════════════════════════════════════════════════════════════════════════════
// Data Retrieval APIs
// ═════════════════════════════════════════════════════════════════════════════

async function fetchOrders() {
    try {
        const response = await fetch('/api/orders');
        if (!response.ok) throw new Error('API error fetching orders');
        
        orders = await response.json();
        processOrdersData();
        renderUncertainItems();
        renderOrdersTable();
    } catch (err) {
        console.error('Error fetching orders:', err);
    }
}

async function fetchRLWeights() {
    try {
        const response = await fetch('/api/rl-summary');
        if (!response.ok) throw new Error('API error fetching RL summary');
        
        const data = await response.json();
        updateRLWeightsUI(data);
    } catch (err) {
        console.error('Error fetching RL weights:', err);
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Data Processing & UI Rendering
// ═════════════════════════════════════════════════════════════════════════════

function processOrdersData() {
    uncertainItems = [];
    let totalItemsCount = 0;
    let perfectItemsCount = 0;
    
    orders.forEach(order => {
        const items = order.items || [];
        items.forEach(item => {
            totalItemsCount++;
            
            // Problematic check: confidence is not 1.00
            // We can enrich the item with order meta to know where it came from
            if (item.confidence < 1.00) {
                uncertainItems.push({
                    ...item,
                    _order_id: `${order.customer_code}_${order.order_number}`,
                    _customer_code: order.customer_code,
                    _order_number: order.order_number,
                    _source_files: order.source_files || []
                });
            } else {
                perfectItemsCount++;
            }
        });
    });
    
    // Update top header metrics
    elements.statTotalOrders.innerText = orders.length;
    elements.statReviewItems.innerText = uncertainItems.length;
    elements.problematicCountBadge.innerText = uncertainItems.length;
    
    if (uncertainItems.length > 0) {
        elements.problematicCountBadge.classList.remove('hidden');
    } else {
        elements.problematicCountBadge.classList.add('hidden');
    }
    
    const accuracy = totalItemsCount > 0 ? Math.round((perfectItemsCount / totalItemsCount) * 100) : 100;
    elements.statAccuracy.innerText = `${accuracy}%`;
}

function renderUncertainItems() {
    elements.uncertainCount.innerText = `${uncertainItems.length} items`;
    
    if (uncertainItems.length === 0) {
        elements.uncertainList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-circle-check"></i>
                <p>All items matched with 100% confidence!</p>
            </div>
        `;
        // Hide detail pane and show placeholder
        elements.detailPanePlaceholder.classList.remove('hidden');
        elements.detailPaneContent.classList.add('hidden');
        return;
    }
    
    elements.uncertainList.innerHTML = '';
    
    uncertainItems.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'review-item';
        if (selectedItem && selectedItem.item_code === item.item_code && selectedItem._order_id === item._order_id) {
            div.classList.add('active');
        }
        
        const confClass = item.confidence < 0.5 ? 'conf-low' : 'conf-med';
        const filesLabel = item._source_files.join(', ');
        
        div.innerHTML = `
            <div class="item-meta">
                <span class="item-cust">${item._order_id}</span>
                <span class="item-conf ${confClass}">conf: ${item.confidence.toFixed(2)}</span>
            </div>
            <div class="item-desc-de" title="${item.description}">${item.description || '(No matched description)'}</div>
            <div class="item-subtext">
                <span>Gemini: ${item.gemini_desc ? item.gemini_desc.substring(0, 20) : 'None'}</span>
                <span>Qty: ${item.ordered_pieces || '?'}</span>
            </div>
        `;
        
        div.addEventListener('click', () => {
            // Remove active from others
            document.querySelectorAll('.review-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');
            selectItem(item);
        });
        
        elements.uncertainList.appendChild(div);
    });
}

function selectItem(item) {
    selectedItem = item;
    
    // Clear comment box
    if (elements.feedbackComment) {
        elements.feedbackComment.value = '';
    }
    
    // Hide placeholder and show content
    elements.detailPanePlaceholder.classList.add('hidden');
    elements.detailPaneContent.classList.remove('hidden');
    
    // Populate header details
    elements.detailCustomerCode.innerText = `Customer: ${item._customer_code}`;
    elements.detailOrderLabel.innerText = `Order Number: ${item._order_number} | Files: ${item._source_files.join(', ')}`;
    
    const confVal = item.confidence;
    elements.detailConfBadge.innerText = confVal.toFixed(2);
    elements.detailConfBadge.className = 'conf-badge ' + (confVal < 0.5 ? 'conf-low' : 'conf-med');
    
    // Comparison Cards
    elements.geminiCode.innerText = item.gemini_code || 'null (Not extracted)';
    elements.geminiDesc.innerText = item.gemini_desc || '(None)';
    elements.geminiPieces.innerText = item.ordered_pieces !== null ? item.ordered_pieces : 'null (Unclear)';
    
    elements.matchCode.innerText = item.item_code || 'null (No match)';
    elements.matchDesc.innerText = item.description || '(None)';
    elements.matchUnit.innerText = item.unit ? `${item.unit} (${item.pc_per_unit} pcs/unit)` : 'null';
    
    // Match Telemetry
    elements.metricFuzzy.innerText = item.fuzzy_score.toFixed(3);
    elements.metricTrigram.innerText = item.trigram_score.toFixed(3);
    elements.metricMethod.innerText = item.match_method || 'Unknown';
    elements.metricRL.innerText = item.rl_recommended || 'Unknown';
    
    // Render media preview (image/audio/text)
    renderMediaPreview(item._source_files[0]); // Preview first file
}

function renderMediaPreview(filename) {
    if (!filename) {
        elements.mediaPreviewBox.innerHTML = '<span class="text-muted">No attachment found</span>';
        return;
    }
    
    const ext = '.' + filename.split('.').pop().toLowerCase();
    const url = `/api/order-file/${filename}`;
    
    if (['.jpg', '.jpeg', '.png'].includes(ext)) {
        elements.mediaPreviewBox.innerHTML = `
            <img src="${url}" class="media-image" alt="Order Image" onclick="window.open('${url}', '_blank')">
        `;
    } else if (['.m4a', '.mp3', '.wav'].includes(ext)) {
        elements.mediaPreviewBox.innerHTML = `
            <div class="media-audio-container">
                <i class="fa-solid fa-microphone-lines"></i>
                <div class="media-audio-title">${filename}</div>
                <audio controls src="${url}"></audio>
            </div>
        `;
    } else if (['.txt'].includes(ext)) {
        elements.mediaPreviewBox.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Loading text order...</p></div>`;
        fetch(url)
            .then(res => res.text())
            .then(text => {
                elements.mediaPreviewBox.innerHTML = `
                    <pre class="media-txt-box">${escapeHTML(text)}</pre>
                `;
            })
            .catch(err => {
                elements.mediaPreviewBox.innerHTML = `<span class="color-red">Failed to load text file contents</span>`;
            });
    } else {
        elements.mediaPreviewBox.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-file-invoice" style="color: var(--text-muted)"></i>
                <p>Unsupported attachment format: ${ext}<br><a href="${url}" target="_blank" style="color: var(--accent); text-decoration: none;">Download File</a></p>
            </div>
        `;
    }
}

function renderOrdersTable() {
    elements.ordersTableBody.innerHTML = '';
    
    if (orders.length === 0) {
        elements.ordersTableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
                    No processed orders found. Please run the NLP pipeline first.
                </td>
            </tr>
        `;
        return;
    }
    
    orders.forEach(order => {
        const tr = document.createElement('tr');
        const orderId = `${order.customer_code}_${order.order_number}`;
        const items = order.items || [];
        const hasProblematic = items.some(item => item.confidence < 1.00);
        
        const statusHTML = hasProblematic 
            ? `<span class="status-badge badge-warning"><i class="fa-solid fa-circle-exclamation"></i> Needs Review</span>`
            : `<span class="status-badge badge-success"><i class="fa-solid fa-circle-check"></i> Passed</span>`;
            
        const filesStr = order.source_files ? order.source_files.join(', ') : 'None';
        
        tr.innerHTML = `
            <td><strong>${order.order_number}</strong></td>
            <td style="font-family: var(--font-mono); font-size: 11px;">${filesStr}</td>
            <td><span class="item-cust">${order.customer_code}</span></td>
            <td>${items.length} items</td>
            <td>${statusHTML}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="viewOrderJson('${order.customer_code}', '${order.order_number}')">
                    <i class="fa-solid fa-brackets-curly"></i> View JSON
                </button>
            </td>
        `;
        elements.ordersTableBody.appendChild(tr);
    });
}

function updateRLWeightsUI(data) {
    const weights = data.weights || {};
    
    // Updates count
    elements.rlUpdates.innerText = `${data.n_updates || 0} updates applied`;
    
    // Scale and update each slider
    updateWeightRow(weights.exact_code, elements.wExact, elements.vExact);
    updateWeightRow(weights.fuzzy_desc, elements.wFuzzy, elements.vFuzzy);
    updateWeightRow(weights.trigram, elements.wTrigram, elements.vTrigram);
    
    // Blocked penalty is negative, handle carefully
    const blockedVal = weights.blocked_penalty || 0;
    elements.vBlocked.innerText = blockedVal.toFixed(2);
    // scale negative value to positive width percentage (max penalty e.g. -1.0 = 100% width)
    const pct = Math.min(100, Math.max(0, Math.abs(blockedVal) * 100));
    elements.wBlocked.style.width = `${pct}%`;
}

function updateWeightRow(val, barEl, valEl) {
    const value = val || 0;
    valEl.innerText = value.toFixed(2);
    const pct = Math.min(100, Math.max(0, value * 100));
    barEl.style.width = `${pct}%`;
}

// ═════════════════════════════════════════════════════════════════════════════
// Action Event Handlers
// ═════════════════════════════════════════════════════════════════════════════

async function submitFeedback(accepted) {
    if (!selectedItem) return;
    
    const confidence = selectedItem.confidence;
    const itemCode = selectedItem.item_code;
    const orderId = selectedItem._order_id;
    const comment = elements.feedbackComment ? elements.feedbackComment.value.trim() : '';
    
    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confidence, accepted, comment })
        });
        
        if (!response.ok) throw new Error('Feedback submission failed');
        
        const data = await response.json();
        
        // Show success notification/toast (console log for now)
        console.log(`RL Feedback processed: ${accepted ? 'accepted' : 'rejected'} for conf=${confidence}`);
        
        // Update model weights immediately
        updateRLWeightsUI(data);
        
        // Remove item from active uncertain list in UI
        const prevIdx = uncertainItems.findIndex(i => i.item_code === itemCode && i._order_id === orderId);
        
        // Refresh orders from local state (we simulate removing the resolved item)
        uncertainItems.splice(prevIdx, 1);
        
        // Update stats count
        elements.statReviewItems.innerText = uncertainItems.length;
        elements.problematicCountBadge.innerText = uncertainItems.length;
        if (uncertainItems.length > 0) {
            elements.problematicCountBadge.classList.remove('hidden');
        } else {
            elements.problematicCountBadge.classList.add('hidden');
        }
        
        // Re-render list
        renderUncertainItems();
        
        // Auto-select the next item or clear details
        if (uncertainItems.length > 0) {
            const nextIdx = Math.min(prevIdx, uncertainItems.length - 1);
            selectItem(uncertainItems[nextIdx]);
        } else {
            selectedItem = null;
            elements.detailPanePlaceholder.classList.remove('hidden');
            elements.detailPaneContent.classList.add('hidden');
        }
        
    } catch (err) {
        alert('Failed to submit feedback: ' + err.message);
    }
}

function runPipeline() {
    // Disable button and add styling
    elements.runPipelineBtn.disabled = true;
    elements.runPipelineBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
    
    // Switch to console view
    elements.tabConsoleBtn.click();
    
    // Clear console and mark status as running
    elements.consoleOutput.innerHTML = '<div class="console-line system-msg">Starting NLP extraction pipeline engine subprocess...</div>';
    elements.consoleStatus.innerText = 'Running';
    elements.consoleStatus.className = 'console-status running';
    
    // Set up SSE EventSource connection
    eventSource = new EventSource('/api/run');
    
    eventSource.onmessage = (event) => {
        const line = event.data;
        
        if (line === '[PROCESS_COMPLETED]') {
            eventSource.close();
            
            elements.runPipelineBtn.disabled = false;
            elements.runPipelineBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run NLP Pipeline';
            
            elements.consoleStatus.innerText = 'Completed';
            elements.consoleStatus.className = 'console-status';
            
            const div = document.createElement('div');
            div.className = 'console-line complete-msg';
            div.innerText = 'NLP Pipeline completed execution successfully. Refreshing results...';
            elements.consoleOutput.appendChild(div);
            
            // Reload all orders & weights
            fetchOrders();
            fetchRLWeights();
            
            // Auto scroll console
            elements.consoleOutput.scrollTop = elements.consoleOutput.scrollHeight;
            return;
        }
        
        const div = document.createElement('div');
        div.className = 'console-line';
        
        // Check if line contains error/warn for highlighting
        if (line.includes('Error') || line.includes('[ERROR]')) {
            div.classList.add('stderr');
        }
        
        div.innerText = line;
        elements.consoleOutput.appendChild(div);
        
        // Scroll to bottom
        elements.consoleOutput.scrollTop = elements.consoleOutput.scrollHeight;
    };
    
    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        eventSource.close();
        
        elements.runPipelineBtn.disabled = false;
        elements.runPipelineBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run NLP Pipeline';
        
        elements.consoleStatus.innerText = 'Error';
        elements.consoleStatus.className = 'console-status';
        
        const div = document.createElement('div');
        div.className = 'console-line stderr';
        div.innerText = 'An error occurred during log streaming. Subprocess terminated.';
        elements.consoleOutput.appendChild(div);
    };
}

// ═════════════════════════════════════════════════════════════════════════════
// Modal handlers
// ═════════════════════════════════════════════════════════════════════════════

window.viewOrderJson = function(customerCode, orderNumber) {
    const order = orders.find(o => o.customer_code === customerCode && o.order_number === orderNumber);
    if (!order) return;
    
    elements.modalTitle.innerText = `JSON Schema Output - Order ${customerCode}_${orderNumber}`;
    elements.modalBodyContent.innerHTML = `
        <pre style="background: #05060b; color: #a5b4fc; padding: 20px; border-radius: 8px; font-family: var(--font-mono); font-size: 12px; overflow-x: auto; max-height: 60vh;">${escapeHTML(JSON.stringify(order, null, 2))}</pre>
    `;
    elements.modal.classList.add('active');
};

function closeModal() {
    elements.modal.classList.remove('active');
}

// Helpers
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}
