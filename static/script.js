/* ══════════════════════════════════════════
   Aura Skincare — Homepage script.js v2
   ══════════════════════════════════════════
   Same-origin API; set window.AURA_API_BASE before this script if
   the frontend is hosted separately from the FastAPI backend.
*/
(() => {
  'use strict';

  const API = (window.AURA_API_BASE || '').replace(/\/$/, '');
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  let toastTimer;

  // ── DOM refs ──────────────────────────────
  const menuToggle  = $('#menuToggle');
  const mainNav     = $('#mainNav');
  const cartToggle  = $('#cartToggle');
  const cartCount   = $('#cartCount');
  const cartOverlay = $('#cartOverlay');
  const cartDrawer  = $('#cartDrawer');
  const closeCart   = $('#closeCart');
  const cartBody    = $('#cartBody');
  const cartEmpty   = $('#cartEmpty');
  const cartItems   = $('#cartItems');
  const cartFooter  = $('#cartFooter');
  const cartShippingNote = $('#cartShippingNote');
  const cartSubtotal = $('#cartSubtotal');
  const cartTotal   = $('#cartTotal');
  const cartHeaderCount = $('#cartHeaderCount');
  const productGrid = $('#productGrid');
  const bestsellersGrid = $('#bestsellersGrid');
  const productsLoading = $('#productsLoading');
  const productModal = $('#productModal');
  const closeModal  = $('#closeModal');
  const modalImg    = $('#modalImg');
  const modalProductTitle = $('#modalProductTitle');
  const modalSize   = $('#modalSize');
  const modalPrice  = $('#modalPrice');
  const modalDesc   = $('#modalDesc');
  const modalAddToCart = $('#modalAddToCart');
  const toast       = $('#toast');
  const yearEl      = $('#year');

  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // ── Catalog (loaded from API) ─────────────
  let catalog = {};

  // ── Cart (localStorage) ───────────────────
  const CART_KEY = 'aura_cart_v2';
  let cart = [];
  try {
    const saved = localStorage.getItem(CART_KEY);
    if (saved) cart = JSON.parse(saved);
    if (!Array.isArray(cart)) cart = [];
  } catch { cart = []; }

  function saveCart() {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch {}
  }

  // ── Toast ─────────────────────────────────
  function showToast(msg, duration = 2800) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), duration);
  }

  // ── Header scroll shadow ──────────────────
  const header = $('#siteHeader');
  window.addEventListener('scroll', () => {
    header?.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });

  // ── Mobile nav ────────────────────────────
  menuToggle?.addEventListener('click', () => {
    const open = mainNav.classList.toggle('open');
    menuToggle.classList.toggle('open', open);
    menuToggle.setAttribute('aria-expanded', String(open));
    menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  });
  $$('#mainNav a').forEach(a => a.addEventListener('click', () => {
    mainNav.classList.remove('open');
    menuToggle.classList.remove('open');
    menuToggle.setAttribute('aria-expanded', 'false');
  }));

  // ── Cart open/close ───────────────────────
  function openCart() {
    cartOverlay.hidden = false; cartOverlay.setAttribute('aria-hidden', 'false');
    cartDrawer.classList.add('open'); cartDrawer.setAttribute('aria-hidden', 'false');
    cartToggle.setAttribute('aria-expanded', 'true');
    closeCart.focus();
    document.body.style.overflow = 'hidden';
  }
  function closeCartDrawer() {
    cartOverlay.hidden = true; cartOverlay.setAttribute('aria-hidden', 'true');
    cartDrawer.classList.remove('open'); cartDrawer.setAttribute('aria-hidden', 'true');
    cartToggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    cartToggle.focus();
  }
  cartToggle?.addEventListener('click', () => cartDrawer.classList.contains('open') ? closeCartDrawer() : openCart());
  closeCart?.addEventListener('click', closeCartDrawer);
  cartOverlay?.addEventListener('click', closeCartDrawer);
  $('#cartShopLink')?.addEventListener('click', closeCartDrawer);

  // ── Cart logic ────────────────────────────
  function addToCart(productId, qty = 1) {
    const p = catalog[productId];
    if (!p) { showToast('Product not found.'); return; }
    const existing = cart.find(i => i.id === productId);
    if (existing) {
      existing.qty += qty;
    } else {
      cart.push({ id: productId, name: p.name, size: p.size, price: p.price, image: p.image, qty });
    }
    saveCart();
    renderCart();
    updateCartBadge();
    showToast(`${p.name} added to cart!`);
    openCart();
  }

  function removeFromCart(productId) {
    cart = cart.filter(i => i.id !== productId);
    saveCart(); renderCart(); updateCartBadge();
  }

  function changeQty(productId, delta) {
    const item = cart.find(i => i.id === productId);
    if (!item) return;
    item.qty = Math.max(1, item.qty + delta);
    if (item.qty === 0) { removeFromCart(productId); return; }
    saveCart(); renderCart(); updateCartBadge();
  }

  function updateCartBadge() {
    const total = cart.reduce((s, i) => s + i.qty, 0);
    if (cartCount) {
      cartCount.textContent = total;
      cartCount.hidden = total === 0;
    }
  }

  function renderCart() {
    const hasItems = cart.length > 0;
    cartEmpty.hidden = hasItems;
    cartItems.hidden = !hasItems;
    cartFooter.hidden = !hasItems;

    if (!hasItems) { cartHeaderCount.textContent = ''; return; }

    const count = cart.reduce((s, i) => s + i.qty, 0);
    cartHeaderCount.textContent = `(${count} item${count !== 1 ? 's' : ''})`;

    cartItems.innerHTML = cart.map(item => `
      <li class="cart-item" data-id="${item.id}">
        <img class="cart-item-img" src="${item.image}" alt="${item.name}" loading="lazy"
          onerror="this.style.background='#ede9fe'">
        <div class="cart-item-info">
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-size">${item.size || ''}</div>
          <div class="cart-item-price">₹${(item.price * item.qty).toLocaleString('en-IN')}</div>
          <div class="qty-controls">
            <button class="qty-btn" data-action="dec" data-id="${item.id}" aria-label="Decrease quantity">−</button>
            <span class="qty-display">${item.qty}</span>
            <button class="qty-btn" data-action="inc" data-id="${item.id}" aria-label="Increase quantity">+</button>
          </div>
        </div>
        <button class="cart-item-remove" data-id="${item.id}" aria-label="Remove ${item.name}">×</button>
      </li>
    `).join('');

    // Subtotal
    const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
    const shipping = subtotal >= 499 ? 0 : 50;
    const totalAmt = subtotal + shipping;

    cartSubtotal.textContent = `₹${subtotal.toLocaleString('en-IN')}`;
    cartTotal.textContent = `₹${totalAmt.toLocaleString('en-IN')}`;

    if (subtotal >= 499) {
      cartShippingNote.textContent = '🎉 You qualify for free shipping!';
    } else {
      cartShippingNote.textContent = `Add ₹${(499 - subtotal).toLocaleString('en-IN')} more for free shipping (₹50 fee applied).`;
    }

    // Bind qty buttons
    cartItems.querySelectorAll('.qty-btn').forEach(btn => {
      btn.addEventListener('click', () => changeQty(btn.dataset.id, btn.dataset.action === 'inc' ? 1 : -1));
    });
    cartItems.querySelectorAll('.cart-item-remove').forEach(btn => {
      btn.addEventListener('click', () => removeFromCart(btn.dataset.id));
    });
  }

  $('#checkoutBtn')?.addEventListener('click', () => {
    showToast('Demo checkout — no real payment is processed. 🛍️', 3500);
  });

  // ── Products ──────────────────────────────
  async function fetchProducts() {
    try {
      const res = await fetch(`${API}/api/products`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      data.products.forEach(p => { catalog[p.product_id] = p; });
      renderProducts('all', 'all');
      renderBestsellers();
    } catch (err) {
      if (productsLoading) productsLoading.textContent = 'Products could not be loaded. Please ensure the backend is running.';
      console.error('Product load failed:', err);
    }
  }

  function renderProducts(categoryFilter, prefFilter) {
    if (!productGrid) return;
    productGrid.innerHTML = '';

    const allProducts = Object.entries(catalog);
    if (allProducts.length === 0) { productGrid.innerHTML = '<p class="catalog-note" style="grid-column:1/-1;text-align:center;padding:40px">No products available.</p>'; return; }

    let shown = 0;
    allProducts.forEach(([id, p]) => {
      const catMatch = categoryFilter === 'all' || p.category === categoryFilter;
      const prefMatch = prefFilter === 'all' || (p.preference || []).includes(prefFilter);
      const card = buildProductCard(id, p);
      card.hidden = !(catMatch && prefMatch);
      if (!card.hidden) shown++;
      productGrid.appendChild(card);
    });

    if (shown === 0) {
      const empty = document.createElement('p');
      empty.className = 'catalog-note';
      empty.style.cssText = 'grid-column:1/-1;text-align:center;padding:40px';
      empty.textContent = 'No products match the selected filters.';
      productGrid.appendChild(empty);
    }
  }

  function buildProductCard(id, p) {
    const art = document.createElement('article');
    art.className = 'product-card reveal';
    art.dataset.category = p.category;
    art.dataset.prefs = (p.preference || []).join(' ');
    art.innerHTML = `
      <div class="pc-img-wrap">
        ${p.kicker ? `<span class="pc-kicker">${p.kicker}</span>` : ''}
        <img src="${p.image}" alt="${p.image_alt || p.name}" loading="lazy"
          onerror="this.style.display='none'">
      </div>
      <div class="pc-body">
        <div class="pc-name">${p.name}</div>
        <div class="pc-size">${p.size || ''}</div>
        <div class="pc-price">₹${(p.price || 0).toLocaleString('en-IN')}</div>
        <div class="pc-desc">${p.description || ''}</div>
        <div class="pc-actions">
          <button class="btn pc-view" data-product-id="${id}">View Details</button>
          <button class="btn pc-cart" data-cart-id="${id}">Add to Cart</button>
        </div>
      </div>
    `;
    art.querySelector('.pc-view').addEventListener('click', () => openProductModal(id));
    art.querySelector('.pc-cart').addEventListener('click', () => addToCart(id));

    // Observe for reveal animation
    revealObserver.observe(art);
    return art;
  }

  function renderBestsellers() {
    if (!bestsellersGrid) return;
    // Pick top 3: Vitamin C serum, Sunscreen, HA serum (P-001, P-002, P-005)
    const bestIds = ['P-001', 'P-002', 'P-005'];
    bestsellersGrid.innerHTML = bestIds.map(id => {
      const p = catalog[id];
      if (!p) return '';
      return `
        <div class="bestseller-card">
          <img class="bs-img" src="${p.image}" alt="${p.image_alt || p.name}" loading="lazy" onerror="this.style.background='#ede9fe'">
          <div class="bs-info">
            <div class="bs-name">${p.name}</div>
            <div class="bs-price">₹${p.price.toLocaleString('en-IN')}</div>
            <button class="btn btn-primary bs-add" data-cart-id="${id}">Add to Cart</button>
          </div>
        </div>
      `;
    }).join('');
    bestsellersGrid.querySelectorAll('[data-cart-id]').forEach(btn => {
      btn.addEventListener('click', () => addToCart(btn.dataset.cartId));
    });
  }

  // ── Product modal ─────────────────────────
  let currentModalId = null;

  function openProductModal(productId) {
    const p = catalog[productId];
    if (!p) return;
    currentModalId = productId;
    modalImg.src = p.image; modalImg.alt = p.image_alt || p.name;
    modalProductTitle.textContent = p.name;
    modalSize.textContent = p.size || '';
    modalPrice.textContent = `₹${(p.price || 0).toLocaleString('en-IN')}`;
    modalDesc.textContent = p.description || '';
    productModal.hidden = false;
    document.body.style.overflow = 'hidden';
    closeModal.focus();
  }

  function closeProductModal() {
    productModal.hidden = true;
    document.body.style.overflow = '';
    currentModalId = null;
  }

  closeModal?.addEventListener('click', closeProductModal);
  productModal?.addEventListener('click', e => { if (e.target === productModal) closeProductModal(); });
  modalAddToCart?.addEventListener('click', () => { if (currentModalId) { addToCart(currentModalId); closeProductModal(); } });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeProductModal(); closeCartDrawer(); }
  });

  // ── Filters ───────────────────────────────
  let currentCategory = 'all';
  let currentPref = 'all';

  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentCategory = btn.dataset.filter;
      applyFilters();
    });
  });

  $('#skinPref')?.addEventListener('change', e => {
    currentPref = e.target.value;
    applyFilters();
  });

  function applyFilters() {
    $$('.product-card').forEach(card => {
      const catMatch = currentCategory === 'all' || card.dataset.category === currentCategory;
      const prefMatch = currentPref === 'all' || (card.dataset.prefs || '').split(' ').includes(currentPref);
      card.hidden = !(catMatch && prefMatch);
    });
  }

  // ── Scroll reveal ─────────────────────────
  const revealObserver = ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches)
    ? new IntersectionObserver(entries => {
        entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); revealObserver.unobserve(e.target); } });
      }, { threshold: 0.1 })
    : { observe: el => el.classList.add('visible') };

  $$('.reveal, .reveal-right').forEach(el => revealObserver.observe(el));

  // ── Init ──────────────────────────────────
  renderCart();
  updateCartBadge();
  fetchProducts();
})();
