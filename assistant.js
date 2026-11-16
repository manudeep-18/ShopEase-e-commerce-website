(function () {
  const authPage = ['/login.html', '/signup.html'].includes(window.location.pathname.toLowerCase());
  if (authPage) return;

  fetch('/api/session')
    .then(response => response.ok ? response.json() : null)
    .then(data => {
      if (data && data.user && data.user.email) startAssistant(data.user);
    })
    .catch(() => {});

  function startAssistant(user) {
    let accountScope = user.email;
    const historyKey = `shopease_assistant_history:${accountScope}`;
    const stateKey = `shopease_assistant_flow:${accountScope}`;
    const greetedKey = `shopease_assistant_greeted:${accountScope}`;
    const styles = document.createElement('link');
    styles.rel = 'stylesheet';
    styles.href = '/assistant.css';
    document.head.appendChild(styles);

    function element(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }

    function formatPrice(price) {
      const amount = Number(price);
      return Number.isFinite(amount)
        ? new Intl.NumberFormat('en-IN', {
          style: 'currency',
          currency: 'INR',
          maximumFractionDigits: 0
        }).format(amount)
        : 'Price not listed';
    }

    function safeDetails(value) {
      if (value === null || value === undefined || value === '') return 'Not listed';
      return typeof value === 'string' ? value : JSON.stringify(value);
    }

    function readHistory() {
      try {
        const saved = JSON.parse(sessionStorage.getItem(historyKey) || '[]');
        if (!Array.isArray(saved)) return [];
        return saved.filter(item =>
          item && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string'
        ).slice(-6);
      } catch {
        return [];
      }
    }

    function readFlow() {
      try {
        const saved = JSON.parse(sessionStorage.getItem(stateKey) || 'null');
        return saved && typeof saved === 'object'
          ? saved
          : { mode: null, step: null, category: null, budgetText: '', selected: [] };
      } catch {
        return { mode: null, step: null, category: null, budgetText: '', selected: [] };
      }
    }

    let history = readHistory();
    let flow = readFlow();
    let busy = false;
    let cartApiPromise = null;

    function ensureCartApi() {
      if (window.ShopEaseCart && typeof window.ShopEaseCart.addItem === 'function') {
        return Promise.resolve(window.ShopEaseCart);
      }
      if (!cartApiPromise) {
        cartApiPromise = new Promise((resolve, reject) => {
          const cartScript = document.createElement('script');
          cartScript.src = '/script.js?v=3';
          cartScript.onload = () => {
            if (window.ShopEaseCart && typeof window.ShopEaseCart.addItem === 'function') {
              resolve(window.ShopEaseCart);
            } else {
              reject(new Error('CART_API_UNAVAILABLE'));
            }
          };
          cartScript.onerror = () => reject(new Error('CART_API_UNAVAILABLE'));
          document.head.appendChild(cartScript);
        });
      }
      return cartApiPromise;
    }

    const launcher = element('button', 'shopease-assistant-launcher', 'Shop with AI');
    launcher.type = 'button';
    launcher.setAttribute('aria-label', 'Open ShopEase shopping assistant');
    const panel = element('section', 'shopease-assistant-panel');
    panel.setAttribute('aria-label', 'ShopEase shopping assistant');
    panel.hidden = true;

    const heading = element('div', 'shopease-assistant-heading');
    const headingText = element('div');
    headingText.append(
      element('strong', '', 'ShopEase assistant'),
      element('span', '', 'Catalogue shopping help')
    );
    const closeButton = element('button', 'shopease-assistant-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close assistant');
    heading.append(headingText, closeButton);

    const messages = element('div', 'shopease-assistant-messages');
    messages.setAttribute('aria-live', 'polite');
    const quickReplies = element('div', 'shopease-assistant-chips');
    const form = element('form', 'shopease-assistant-form');
    const input = element('input', 'shopease-assistant-input');
    input.type = 'text';
    input.maxLength = 500;
    input.autocomplete = 'off';
    input.placeholder = 'Ask about ShopEase products...';
    input.setAttribute('aria-label', 'Message the shopping assistant');
    const sendButton = element('button', 'shopease-assistant-send', 'Send');
    sendButton.type = 'submit';
    form.append(input, sendButton);
    panel.append(heading, messages, quickReplies, form);
    document.body.append(launcher, panel);

    function saveHistory() {
      history = history.slice(-6);
      try {
        sessionStorage.setItem(historyKey, JSON.stringify(history));
      } catch {
        // The chat remains usable when session storage is disabled.
      }
    }

    function saveFlow() {
      try {
        sessionStorage.setItem(stateKey, JSON.stringify(flow));
      } catch {
        // Flow controls remain usable when session storage is disabled.
      }
    }

    function wasGreeted() {
      try {
        return sessionStorage.getItem(greetedKey) === '1';
      } catch {
        return false;
      }
    }

    function scrollToLatest() {
      messages.scrollTop = messages.scrollHeight;
    }

    function appendButtons(parent, buttons) {
      if (!buttons.length) return;
      const group = element('div', 'shopease-assistant-options');
      buttons.forEach(({ label, onClick }) => {
        const button = element('button', 'shopease-assistant-option', label);
        button.type = 'button';
        button.disabled = busy;
        button.addEventListener('click', onClick);
        group.appendChild(button);
      });
      parent.appendChild(group);
    }

    function makeProductUrl(product) {
      const productDetails = {
        name: product.name,
        category: product.category || '',
        price: String(product.price)
      };
      if (product.id) productDetails.id = product.id;
      const params = new URLSearchParams(productDetails);
      return `/product.html?${params.toString()}`;
    }

    function appendAddToCart(buttonRow, feedback, product) {
      const button = element('button', 'shopease-assistant-add', 'Add to cart');
      button.type = 'button';
      let retryButton = null;
      let added = false;

      async function addItem() {
        button.disabled = true;
        if (retryButton) {
          retryButton.remove();
          retryButton = null;
        }
        feedback.hidden = true;
        feedback.textContent = '';
        try {
          const cartApi = await ensureCartApi();
          const result = await cartApi.addItem({
            id: product.id,
            name: product.name,
            price: Number(product.price),
            image: product.image || ''
          });
          if (!result.authenticated) {
            window.location.href = '/login.html';
            return;
          }
          added = true;
          button.textContent = 'Added';
          button.disabled = true;
          feedback.textContent = 'Added to cart ✓';
          feedback.classList.add('is-success');
          feedback.hidden = false;
          if (retryButton) retryButton.remove();
          retryButton = null;
        } catch (error) {
          console.error('Assistant could not add the product to the cart', error);
          feedback.classList.remove('is-success');
          const cartApiUnavailable = error && error.message === 'CART_API_UNAVAILABLE';
          feedback.textContent = cartApiUnavailable
            ? 'Cart service is unavailable. Refresh the page and try again.'
            : 'Could not add this item right now. Please try again.';
          if (!cartApiUnavailable && !retryButton) {
            retryButton = element('button', 'shopease-assistant-retry', 'Try again');
            retryButton.type = 'button';
            retryButton.addEventListener('click', addItem);
            feedback.appendChild(retryButton);
          }
          feedback.hidden = false;
        } finally {
          if (!added) button.disabled = false;
          if (retryButton) retryButton.disabled = false;
          scrollToLatest();
        }
      }

      button.addEventListener('click', addItem);
      buttonRow.appendChild(button);
    }

    function renderProductCards(container, products) {
      if (!Array.isArray(products) || !products.length) return;
      const cards = element('div', 'shopease-assistant-products');
      products.slice(0, 5).forEach(product => {
        if (!product || typeof product.name !== 'string') return;
        const card = element('article', 'shopease-assistant-product');
        if (typeof product.image === 'string' && product.image) {
          try {
            const imageUrl = new URL(product.image, window.location.origin);
            if (['https:', 'http:'].includes(imageUrl.protocol)) {
              const image = element('img', 'shopease-assistant-product-image');
              image.src = imageUrl.href;
              image.alt = product.name;
              image.loading = 'lazy';
              card.appendChild(image);
            }
          } catch {
            // Ignore malformed optional image URLs.
          }
        }
        card.append(
          element('strong', 'shopease-assistant-product-name', product.name),
          element('span', 'shopease-assistant-product-price', formatPrice(product.price))
        );
        const actions = element('div', 'shopease-assistant-product-actions');
        const buttonRow = element('div', 'shopease-assistant-product-button-row');
        const feedback = element('div', 'shopease-assistant-cart-feedback');
        feedback.hidden = true;
        const viewLink = element('a', 'shopease-assistant-view', 'View');
        viewLink.href = makeProductUrl(product);
        viewLink.addEventListener('click', () => {
          try {
            localStorage.setItem('shopease_selected_product', JSON.stringify({
              id: product.id,
              name: product.name,
              price: Number(product.price),
              category: product.category || '',
              image: product.image || ''
            }));
          } catch {
            // The product page can still load from its URL.
          }
        });
        buttonRow.appendChild(viewLink);
        appendAddToCart(buttonRow, feedback, product);
        actions.append(buttonRow, feedback);
        card.appendChild(actions);
        cards.appendChild(card);
      });
      if (cards.childElementCount) container.appendChild(cards);
    }

    function renderComparison(products) {
      const grid = element('div', 'shopease-assistant-comparison');
      products.forEach(product => {
        const card = element('article', 'shopease-assistant-compare-card');
        const title = element('strong', 'shopease-assistant-product-name', product.name);
        card.appendChild(title);
        const highlights = element('div', 'shopease-assistant-highlights');
        if (product.isCheaper) highlights.appendChild(element('span', 'shopease-assistant-highlight', 'Cheaper'));
        if (product.isBetterRated) highlights.appendChild(element('span', 'shopease-assistant-highlight', 'Better rated'));
        if (highlights.childElementCount) card.appendChild(highlights);

        const details = [
          ['Price', formatPrice(product.price)],
          ['Discount', product.discount === null || product.discount === undefined
            ? 'Not listed'
            : `${safeDetails(product.discount)}${typeof product.discount === 'number' ? '%' : ''}`],
          ['Rating', product.rating === null || product.rating === undefined
            ? 'Not rated yet'
            : `${safeDetails(product.rating)} / 5`],
          ['Key specs / description', safeDetails(product.specs || product.description)],
          ['Stock', safeDetails(product.stockStatus)]
        ];
        const list = element('dl', 'shopease-assistant-compare-details');
        details.forEach(([label, value]) => {
          const row = element('div', 'shopease-assistant-compare-row');
          row.append(element('dt', '', label), element('dd', '', value));
          list.appendChild(row);
        });
        card.append(list);
        const actions = element('div', 'shopease-assistant-product-actions');
        const buttonRow = element('div', 'shopease-assistant-product-button-row');
        const feedback = element('div', 'shopease-assistant-cart-feedback');
        feedback.hidden = true;
        const view = element('a', 'shopease-assistant-view', 'View');
        view.href = makeProductUrl(product);
        buttonRow.appendChild(view);
        appendAddToCart(buttonRow, feedback, product);
        actions.append(buttonRow, feedback);
        card.appendChild(actions);
        grid.appendChild(card);
      });
      messages.appendChild(grid);
      appendButtons(messages, [{
        label: 'Compare other products',
        onClick: () => startCompare()
      }]);
      scrollToLatest();
    }

    function appendMessage(role, text, options = {}) {
      const bubble = element(
        'div',
        `shopease-assistant-message ${role === 'user' ? 'is-user' : 'is-assistant'}`,
        text
      );
      messages.appendChild(bubble);
      if (role === 'assistant') {
        renderProductCards(messages, options.products);
        if (options.comparison) renderComparison(options.comparison);
        appendButtons(messages, options.buttons || []);
      }
      if (options.categories) {
        appendButtons(messages, options.categories.map(category => ({
          label: category,
          onClick: () => chooseCategory(category)
        })));
      }
      if (options.selectableProducts) {
        appendButtons(messages, options.selectableProducts.map(product => ({
          label: `${product.name} — ${formatPrice(product.price)}`,
          onClick: () => selectCompareProduct(product)
        })));
      }
      scrollToLatest();
    }

    function addAssistantMessage(text, options = {}) {
      history.push({ role: 'assistant', content: text });
      saveHistory();
      appendMessage('assistant', text, options);
    }

    function addUserMessage(text) {
      history.push({ role: 'user', content: text });
      saveHistory();
      appendMessage('user', text);
    }

    function setBusy(value) {
      busy = value;
      sendButton.disabled = value;
      input.disabled = value;
      quickReplies.querySelectorAll('button').forEach(button => {
        button.disabled = value;
      });
      messages.querySelectorAll(
        '.shopease-assistant-option, .shopease-assistant-add, .shopease-assistant-retry'
      ).forEach(button => {
        button.disabled = value;
      });
    }

    function addTypingIndicator() {
      const typing = element('div', 'shopease-assistant-typing', 'ShopEase is thinking…');
      messages.appendChild(typing);
      scrollToLatest();
      return typing;
    }

    async function runWithTyping(action) {
      setBusy(true);
      const typing = addTypingIndicator();
      try {
        await action();
      } catch (error) {
        addAssistantMessage(error.message || 'Sorry, I could not complete that. Please try again.');
      } finally {
        typing.remove();
        setBusy(false);
        input.focus();
        scrollToLatest();
      }
    }

    async function apiJson(url, options = {}) {
      const response = await fetch(url, {
        credentials: 'same-origin',
        ...options,
        headers: {
          ...(options.headers || {}),
          ...(options.body ? { 'Content-Type': 'application/json' } : {})
        }
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('The server returned an unexpected response. Please try again.');
      }
      if (response.status === 401) {
        window.location.href = '/login.html';
        throw new Error('Please sign in again to continue.');
      }
      if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
      return data;
    }

    async function loadCategories() {
      const data = await apiJson('/api/assistant/categories');
      return Array.isArray(data.categories) ? data.categories : [];
    }

    function resetFlow() {
      flow = { mode: null, step: null, category: null, budgetText: '', selected: [] };
      saveFlow();
    }

    async function beginCategoryBrowse() {
      resetFlow();
      flow = { mode: 'browse', step: 'need_category', category: null, budgetText: '', selected: [] };
      saveFlow();
      const categories = await loadCategories();
      addAssistantMessage(
        categories.length ? 'Choose a category to browse:' : 'There are no product categories available right now.',
        { categories }
      );
    }

    async function startCompare() {
      flow = { mode: 'compare', step: 'need_category', category: null, budgetText: '', selected: [] };
      saveFlow();
      const categories = await loadCategories();
      addAssistantMessage(
        categories.length
          ? 'Which category do you want to compare in?'
          : 'There are no product categories available right now.',
        { categories }
      );
    }

    async function startBudget() {
      flow = { mode: 'budget', step: 'need_budget', category: null, budgetText: '', selected: [] };
      saveFlow();
      addAssistantMessage('What is your budget? Try “under 10,000”, “around 3k”, or “between 2,000 and 5,000”.');
    }

    async function searchBudget(message, category = null) {
      flow.mode = 'budget';
      flow.budgetText = message;
      flow.category = category;
      saveFlow();
      const data = await apiJson('/api/assistant/budget-search', {
        method: 'POST',
        body: JSON.stringify({ message, category })
      });
      if (data.needsCategory) {
        flow.step = 'need_category';
        flow.category = null;
        saveFlow();
        addAssistantMessage(data.reply, { categories: data.categories || [] });
      } else {
        resetFlow();
        addAssistantMessage(data.reply, { products: data.products || [] });
      }
    }

    async function chooseCategory(category, showUserMessage = true) {
      if (showUserMessage) addUserMessage(category);
      flow.category = category;
      saveFlow();
      await runWithTyping(async () => {
        if (flow.mode === 'budget') {
          await searchBudget(flow.budgetText, category);
          return;
        }
        if (flow.mode === 'compare') {
          const data = await apiJson(`/api/assistant/products?category=${encodeURIComponent(category)}`);
          flow.step = 'select_products';
          flow.selected = [];
          saveFlow();
          addAssistantMessage(
            data.products && data.products.length
              ? `Choose two ${category} products to compare:`
              : `No products are listed in ${category} right now.`,
            { selectableProducts: data.products || [] }
          );
          return;
        }
        const data = await apiJson(`/api/assistant/products?category=${encodeURIComponent(category)}`);
        resetFlow();
        addAssistantMessage(`Here are the products in ${category}:`, { products: data.products || [] });
      });
    }

    async function selectCompareProduct(product) {
      if (flow.step !== 'select_products') return;
      addUserMessage(`${product.name} — ${formatPrice(product.price)}`);
      flow.selected = Array.isArray(flow.selected) ? flow.selected : [];
      if (flow.selected.some(item => item.name === product.name && item.price === product.price)) {
        addAssistantMessage('Choose a different second product.');
        return;
      }
      flow.selected.push({ name: product.name, price: Number(product.price) });
      saveFlow();
      if (flow.selected.length < 2) {
        addAssistantMessage('Choose one more product to compare.');
        return;
      }
      await runWithTyping(async () => {
        const data = await apiJson('/api/assistant/compare', {
          method: 'POST',
          body: JSON.stringify({ category: flow.category, products: flow.selected })
        });
        flow.step = 'complete';
        flow.selected = [];
        saveFlow();
        addAssistantMessage(data.reply, { comparison: data.products || [] });
      });
    }

    async function trackLatestOrder() {
      const data = await apiJson('/api/assistant/orders/latest');
      addAssistantMessage(data.reply);
    }

    function normalized(value) {
      return String(value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    }

    async function handleUserMessage(message) {
      const text = message.trim();
      const lower = normalized(text);
      if (['cancel', 'start over', 'reset'].includes(lower)) {
        resetFlow();
        addAssistantMessage('No problem. Your shopping flow has been reset. Choose what you would like to do next.');
        return;
      }
      if (lower === 'shop by category' || lower === 'browse categories') {
        await beginCategoryBrowse();
        return;
      }
      if (lower === 'under my budget' || lower === 'budget search') {
        await startBudget();
        return;
      }
      if (lower.includes('compare')) {
        await startCompare();
        return;
      }
      if (lower.includes('track my order') || lower.includes('track order')) {
        resetFlow();
        await trackLatestOrder();
        return;
      }

      if (flow.mode === 'budget' && flow.step === 'need_category') {
        const categories = await loadCategories();
        const category = categories.find(item => normalized(item) === lower);
        if (category) {
          await chooseCategory(category, false);
          return;
        }
      }
      if (flow.mode === 'compare' && flow.step === 'need_category') {
        const categories = await loadCategories();
        const category = categories.find(item => normalized(item) === lower);
        if (category) {
          await chooseCategory(category, false);
          return;
        }
      }
      if (flow.mode === 'budget' && flow.step === 'need_budget') {
        await searchBudget(text);
        return;
      }
      if (/\d/.test(text) && /\b(under|below|less|within|max|between|around|budget|₹|rs)\b/i.test(text)) {
        await searchBudget(text);
        return;
      }

      const response = await apiJson('/api/assistant/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, history: history.slice(-6) })
      });
      addAssistantMessage(response.reply, { products: response.products || [] });
    }

    const quickRepliesData = [
      ['Shop by category', 'Shop by category'],
      ['Under my budget', 'Under my budget'],
      ['Under 10,000', 'Under 10,000'],
      ['Compare two products', 'Compare two products'],
      ['Track my order', 'Track my order']
    ];
    quickRepliesData.forEach(([label, prompt]) => {
      const chip = element('button', 'shopease-assistant-chip', label);
      chip.type = 'button';
      chip.addEventListener('click', () => sendMessage(prompt));
      quickReplies.appendChild(chip);
    });

    history.forEach(item => appendMessage(item.role, item.content));

    function openPanel() {
      panel.hidden = false;
      launcher.hidden = true;
      if (!wasGreeted()) {
        const firstName = typeof user.name === 'string' ? user.name.trim().split(/\s+/)[0] : '';
        const greeting = firstName
          ? `Hi ${firstName}! 👋 I'm the ShopEase assistant. How can I help you today?`
          : "Hi there! 👋 I'm the ShopEase assistant. How can I help you today?";
        addAssistantMessage(greeting);
        try {
          sessionStorage.setItem(greetedKey, '1');
        } catch {
          // Greeting de-duplication is best-effort if session storage is disabled.
        }
      }
      input.focus();
      scrollToLatest();
    }

    function closePanel() {
      panel.hidden = true;
      launcher.hidden = false;
    }

    async function sendMessage(message) {
      const text = message.trim();
      if (!text || busy) return;
      input.value = '';
      addUserMessage(text);
      await runWithTyping(() => handleUserMessage(text));
    }

    launcher.addEventListener('click', openPanel);
    closeButton.addEventListener('click', closePanel);
    form.addEventListener('submit', event => {
      event.preventDefault();
      sendMessage(input.value);
    });
  }
})();
